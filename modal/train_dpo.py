"""
QLoRA-DPO fine-tune: cbt-qwen2.5-7b-v2  →  v3.

Nudges HABITS observed failing in production (re-ask loops, technique
name-dropping, borrowed names, fabricated continuity, thin advice) using
preference pairs harvested from clinician decisions + authored seeds.
It does NOT retrain knowledge — v2's SFT stays the foundation.

Run on the TRAINING account (never the inference brain account):

    modal profile activate <train-account>
    # 1. cheap config smoke (~$1, ~10 min):
    modal run modal/train_dpo.py --data backend/scripts/dpo_data/dpo_all.jsonl --smoke
    # 2. real run (~$5, ~45 min):
    modal run modal/train_dpo.py --data backend/scripts/dpo_data/dpo_all.jsonl
    # 3. merge adapter + push private HF repo (~$2):
    modal run modal/train_dpo.py --merge-only --run-name <name printed by step 2>

Discipline rules baked in: adapter checkpoints every 50 steps to a volume
(crash loses minutes, not the run); hard 2-epoch cap (500-pair sets overfit
beyond that); smoke mode trains 30 steps on 20 pairs to catch config errors
before they cost real money.
"""
import json
import os

import modal

BASE_MODEL = os.environ.get("DPO_BASE", "Huysun29/cbt-qwen2.5-7b-v2")
OUT_REPO = os.environ.get("DPO_OUT_REPO", "Huysun29/cbt-qwen2.5-7b-v3")
GPU = os.environ.get("MODAL_GPU", "H100")

app = modal.App("cbt-dpo-train")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # Modern stack — the v2 repo's tokenizer.json is serialized by a new
        # `tokenizers` and the 4.44-era stack can't parse it ("untagged enum
        # ModelWrapper"). These match the era the brain image resolves to.
        "torch==2.7.0",
        "transformers==4.52.4",
        "trl==0.19.0",
        "peft==0.15.2",
        "bitsandbytes==0.46.0",
        "datasets==3.6.0",
        "accelerate==1.7.0",
        "huggingface-hub==0.33.0",
        "hf-transfer==0.1.9",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1",
          # bake deploy-time knobs into the container env — the module is
          # re-imported remotely, where bare os.environ reads would fall
          # back to defaults and silently ignore DPO_BASE/DPO_OUT_REPO
          "DPO_BASE": BASE_MODEL,
          "DPO_OUT_REPO": OUT_REPO})
)

hf_secret = modal.Secret.from_name("huggingface", required_keys=["HF_TOKEN"])
# Reuse the brain's HF cache volume — v2 weights are already sitting there
# from the staging deploy, so training skips the 15GB re-download.
cache_vol = modal.Volume.from_name("cbt-model-cache", create_if_missing=True)
out_vol = modal.Volume.from_name("cbt-dpo-out", create_if_missing=True)


@app.function(
    gpu=GPU, image=image, secrets=[hf_secret], timeout=3 * 3600,
    volumes={"/root/.cache/huggingface": cache_vol, "/out": out_vol},
)
def train(pairs: list, smoke: bool = False, run_name: str = "v3") -> str:
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import DPOConfig, DPOTrainer

    if smoke:
        pairs = pairs[:20]
    print(f"[dpo] {len(pairs)} pairs | base={BASE_MODEL} | smoke={smoke}")

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    # Same chat template the brain serves with — behaviour must transfer.
    def fmt(p):
        return {
            "prompt": tok.apply_chat_template(
                [{"role": "user", "content": p["prompt"]}],
                tokenize=False, add_generation_prompt=True),
            "chosen": p["chosen"],
            "rejected": p["rejected"],
        }

    ds = Dataset.from_list([fmt(p) for p in pairs])

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True),
        torch_dtype=torch.bfloat16, device_map="auto",
    )
    model.config.use_cache = False

    out_dir = f"/out/{run_name}"
    args = DPOConfig(
        output_dir=out_dir,
        beta=0.1,
        learning_rate=5e-6,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        num_train_epochs=2,                 # hard cap — small sets overfit fast
        max_steps=30 if smoke else -1,
        per_device_train_batch_size=2,
        # effective batch 8: ~150-pair sets need the extra update steps
        # (batch 16 x 2 epochs would be only ~18 optimizer steps)
        gradient_accumulation_steps=4,
        gradient_checkpointing=True,
        max_length=2048,
        max_prompt_length=1536,
        bf16=True,
        logging_steps=10,
        save_steps=50,
        save_total_limit=2,
        report_to=[],
    )
    trainer = DPOTrainer(
        model,
        ref_model=None,                     # PEFT → implicit frozen reference
        args=args,
        train_dataset=ds,
        processing_class=tok,               # trl>=0.12 renamed `tokenizer`
        peft_config=LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"]),
    )
    trainer.train()
    trainer.save_model(out_dir + "/adapter")
    tok.save_pretrained(out_dir + "/adapter")
    out_vol.commit()
    print(f"[dpo] adapter saved → {out_dir}/adapter"
          + (" (SMOKE — do not merge)" if smoke else ""))
    return run_name


@app.function(
    gpu="A100-80GB", image=image, secrets=[hf_secret], timeout=3600,
    volumes={"/root/.cache/huggingface": cache_vol, "/out": out_vol},
)
def merge_push(run_name: str = "v3") -> str:
    """Reload base in bf16, merge the adapter, push to a PRIVATE HF repo."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    adapter = f"/out/{run_name}/adapter"
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, torch_dtype=torch.bfloat16, device_map="auto")
    merged = PeftModel.from_pretrained(base, adapter).merge_and_unload()
    tok = AutoTokenizer.from_pretrained(adapter)
    merged.push_to_hub(OUT_REPO, private=True)
    tok.push_to_hub(OUT_REPO, private=True)
    print(f"[dpo] merged + pushed → {OUT_REPO} (private)")
    return OUT_REPO


@app.local_entrypoint()
def main(data: str = "", smoke: bool = False,
         merge_only: bool = False, run_name: str = "v3"):
    if merge_only:
        print(merge_push.remote(run_name))
        return
    if not data:
        raise SystemExit("--data path/to/dpo_all.jsonl required")
    pairs = []
    with open(data, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                assert {"prompt", "chosen", "rejected"} <= set(row), row.keys()
                pairs.append({k: row[k] for k in ("prompt", "chosen", "rejected")})
    name = train.remote(pairs, smoke=smoke, run_name=run_name)
    if smoke:
        print(f"[dpo] smoke OK (run={name}) — rerun WITHOUT --smoke to train")
    else:
        print(f"[dpo] done (run={name}) — next: modal run modal/train_dpo.py "
              f"--merge-only --run-name {name}")
