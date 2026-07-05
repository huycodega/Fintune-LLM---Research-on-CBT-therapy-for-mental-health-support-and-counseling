"""
Modal "brain" service — ONE vLLM engine serving all three LLM roles.

cbt-llm / cbt-safety / cbt-agent each load the SAME Huysun29/cbt-qwen2.5-7b-v2
weights in separate containers — three cold starts and 3× GPU for one model.
This app collapses them into a single engine with three endpoints whose
request/response contracts are byte-compatible with the old services, so the
backend needs ZERO code changes — only env vars:

    POST /generate  { messages, n_responses, temperature, top_p,
                       max_new_tokens }            → { responses, timing, … }
    POST /assess    { messages }                    → { level, severity,
                                                        reason, confidence, … }
    POST /chat      { messages, tools, temperature,
                       max_new_tokens,
                       force_tool_call }            → { content, tool_calls,
                                                        raw, forced, … }
    GET  /health    → { status, model, engine, roles }

Parsing logic (safety triage tiers, agent tool-call extraction, forced
<tool_call> prefill + stop) is ported VERBATIM from safety_service.py and
agent_service.py — same model, same prompts, same parsing ⇒ same quality.

Deploy (any workspace; A10G default → no credit-card gate):
    modal profile activate <workspace>
    modal secret create huggingface HF_TOKEN=hf_xxx    # once per workspace
    modal deploy modal/brain_service.py

Point Railway at it (explicit env beats MODAL_WORKSPACE-derived URLs):
    MODAL_LLM_ENDPOINT=https://<ws>--cbt-brain-generate.modal.run
    MODAL_HEALTH_ENDPOINT=https://<ws>--cbt-brain-health.modal.run
    MODAL_SAFETY_ENDPOINT=https://<ws>--cbt-brain-assess.modal.run
    MODAL_SAFETY_HEALTH_ENDPOINT=https://<ws>--cbt-brain-health.modal.run
    MODAL_AGENT_ENDPOINT=https://<ws>--cbt-brain-chat.modal.run
    MODAL_AGENT_HEALTH_ENDPOINT=https://<ws>--cbt-brain-health.modal.run
    MODAL_EMBEDDER_ENDPOINT=https://<ws>--cbt-brain-embed.modal.run
    MODAL_RERANKER_ENDPOINT=https://<ws>--cbt-brain-rerank.modal.run
Rollback = delete those vars (falls back to the per-service apps on
MODAL_WORKSPACE).

Keep-warm for demos: MIN_CONTAINERS=1 env at deploy time (A10G ≈ $1.1/h —
affordable, unlike keeping three A100s hot).
"""
import json
import os
import re
import threading
import time

import modal

# ─────────────────────────────────────────────────────────────────────────────
# Image: vLLM wheels bundle their own CUDA-enabled torch.
# ─────────────────────────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.9.1",
        "sentence-transformers==4.1.0",
        "huggingface-hub==0.33.0",
        "hf_transfer==0.1.9",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1",
          # Bake the DEPLOY-TIME model choice into the container env. The
          # module is re-imported inside the container, where a bare
          # os.environ.get would silently fall back to the default — so
          # `HF_MODEL_REPO=...v3 modal deploy` wouldn't actually serve v3
          # without this line (staging flip for the DPO gate relies on it).
          "HF_MODEL_REPO": os.environ.get("HF_MODEL_REPO",
                                          "Huysun29/cbt-qwen2.5-7b-v2")})
)

app = modal.App("cbt-brain")

HF_REPO = os.environ.get("HF_MODEL_REPO", "Huysun29/cbt-qwen2.5-7b-v2")
# A100-80GB to match the legacy services (fastest decode; NB: fresh Modal
# workspaces require a payment method for A100 — set MODAL_GPU=A10G to run on
# the card-free tier instead).
GPU = os.environ.get("MODAL_GPU", "A100-80GB")
# eager = no CUDA-graph capture: boots faster, decodes slightly slower.
ENFORCE_EAGER = os.environ.get("VLLM_EAGER", "1").lower() not in ("0", "false")
# Agent prompts run up to 6144 tokens (see agent_service.py truncation).
MAX_MODEL_LEN = int(os.environ.get("VLLM_MAX_LEN", "8192"))
MIN_CONTAINERS = int(os.environ.get("MIN_CONTAINERS", "0"))

# RAG sidecars (small models riding the same GPU — was 2 extra CPU services).
EMBEDDER_REPO = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
RERANKER_REPO = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
EMBED_DIM = 1024
# NLI grounding scorer (~184M) — ran on the Railway CPU before, where a single
# turn's (sentences × chunks) batch took 10+ MINUTES; on this GPU it's <1s.
NLI_MODEL_ID = os.environ.get("NLI_MODEL", "cross-encoder/nli-deberta-v3-base")

hf_secret = modal.Secret.from_name("huggingface", required_keys=["HF_TOKEN"])
model_cache = modal.Volume.from_name("cbt-model-cache", create_if_missing=True)


# ─────────────────────────────────────────────────────────────────────────────
# Safety triage parsing — ported verbatim from safety_service.py
# ─────────────────────────────────────────────────────────────────────────────
def _infer_level(text: str) -> str:
    """Infer triage level from free-text model output."""
    if any(w in text for w in ("suicid", "end my life", "want to die",
                                "kill myself", "immediate danger", "crisis",
                                "emergency", "life-threatening")):
        return "L0"
    if any(w in text for w in ("self-harm", "harm", "hopeless", "passive ideation",
                                "high risk", "significant risk", "urgent")):
        return "L1"
    if any(w in text for w in ("depress", "anxi", "ptsd", "trauma", "distress",
                                "moderate", "specialist", "professional",
                                "further evaluation", "mental health")):
        return "L2"
    return "L3"


def _risk_to_level(rl: str) -> str:
    """Map the fine-tuned model's risk_level → triage level (safety-first)."""
    return {"crisis": "L0", "moderate": "L2",
            "out_of_scope": "L2", "normal": "L3"}.get(rl, "L3")


def _lv_to_sev(lv: str) -> str:
    return {"L0": "critical", "L1": "high", "L2": "moderate"}.get(lv, "low")


def _parse_triage(raw: str, t0: float) -> dict:
    """The 4-tier parser from safety_service.assess — plus one hardening: the
    model sometimes emits a lowercase level ("l0"), which the original
    case-sensitive regex silently DOWNGRADED to L3. Match case-insensitively
    and normalise upward."""
    m = re.search(r'\{[^{}]*"level"\s*:\s*"[Ll][0-3]"[^{}]*\}', raw, re.S)
    if m:
        try:
            result = json.loads(m.group())
            return {
                "level": str(result.get("level", "L3")).upper(),
                "severity": result.get("severity", "low"),
                "reason": result.get("reason", ""),
                "confidence": float(result.get("confidence", 0.7)),
                "latency_ms": round((time.time() - t0) * 1000),
                "mode": "modal", "model": HF_REPO,
            }
        except (json.JSONDecodeError, ValueError):
            pass

    m2 = re.search(r'"risk_level"\s*:\s*"([a-z_]+)"', raw)
    if m2:
        level = _risk_to_level(m2.group(1))
        reason = ""
        try:
            obj = json.loads(re.search(r'\{.*\}', raw, re.S).group())
            reason = str(obj.get("rationale") or obj.get("reason")
                         or obj.get("response") or "")[:150]
        except Exception:
            pass
        return {
            "level": level, "severity": _lv_to_sev(level),
            "reason": reason, "confidence": 0.8,
            "latency_ms": round((time.time() - t0) * 1000),
            "mode": "modal", "model": HF_REPO,
        }

    try:
        data = json.loads(raw)
        assessment = (data.get("assessment", "") + " " +
                      data.get("next_steps", "")).lower()
        level = _infer_level(assessment)
        return {
            "level": level,
            "severity": _lv_to_sev(level),
            "reason": data.get("assessment", "")[:150],
            "confidence": 0.72,
            "latency_ms": round((time.time() - t0) * 1000),
            "mode": "modal", "model": HF_REPO,
        }
    except (json.JSONDecodeError, ValueError):
        pass

    low = raw.lower()
    level = _infer_level(low)
    return {"level": level, "severity": _lv_to_sev(level),
            "reason": "inferred from model text",
            "confidence": 0.5, "mode": "modal_text"}


# ─────────────────────────────────────────────────────────────────────────────
# Agent tool-call parsing — ported verbatim from agent_service.py
# ─────────────────────────────────────────────────────────────────────────────
def _iter_balanced_objects(text: str):
    """Yield each top-level {...} substring with BALANCED braces (string-aware)."""
    i, n = 0, len(text)
    while i < n:
        if text[i] == "{":
            depth, j, in_str, esc = 0, i, False, False
            while j < n:
                c = text[j]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                else:
                    if c == '"':
                        in_str = True
                    elif c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            yield text[i:j + 1]
                            i = j
                            break
                j += 1
        i += 1


def _coerce_call(obj: dict):
    """{"name", "arguments"|"parameters"} → normalized call, or None."""
    if not isinstance(obj, dict):
        return None
    name = obj.get("name")
    if not name:
        return None
    args = obj.get("arguments", obj.get("parameters", {}))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {"_raw": args}
    return {"name": name, "arguments": args or {}}


def _parse_tool_calls(raw: str):
    """Extract tool calls; returns (content, tool_calls). Tolerant of the
    <tool_call> wrapper, bare JSON, arrays, and prose — same as cbt-agent."""
    text = raw.strip().replace("<|python_tag|>", "").strip()
    calls = []
    for cand in _iter_balanced_objects(text):
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        call = _coerce_call(obj)
        if call:
            calls.append(call)
    if calls:
        return "", calls

    try:
        obj = json.loads(text)
        for it in (obj if isinstance(obj, list) else [obj]):
            call = _coerce_call(it)
            if call:
                calls.append(call)
        if calls:
            return "", calls
    except json.JSONDecodeError:
        pass

    return text, []


# ─────────────────────────────────────────────────────────────────────────────
# One engine, three roles
# ─────────────────────────────────────────────────────────────────────────────
@app.cls(
    gpu=GPU,
    image=image,
    secrets=[hf_secret],
    scaledown_window=300,
    timeout=900,
    min_containers=MIN_CONTAINERS,
    # ONE engine only. A chat turn is 5-15 SEQUENTIAL brain calls; without
    # these two knobs Modal treats each call that lands while the container
    # is busy as demand for a NEW container → every call waits on a ~2-min
    # cold boot → 10-minute turns. Queue into the warm engine instead.
    max_containers=1,
    volumes={"/root/.cache/huggingface": model_cache},
)
@modal.concurrent(max_inputs=16)
class CBTBrainService:
    @modal.enter()
    def load(self):
        from huggingface_hub import login
        from vllm import LLM

        if os.environ.get("HF_TOKEN"):
            login(os.environ["HF_TOKEN"])

        t0 = time.time()
        # RAG sidecars FIRST (small, ~4.5 GB together) so vLLM's memory budget
        # is measured against what's actually free.
        from sentence_transformers import CrossEncoder, SentenceTransformer
        self.embedder = SentenceTransformer(EMBEDDER_REPO, device="cuda")
        self.reranker = CrossEncoder(RERANKER_REPO, device="cuda",
                                     max_length=512)
        # NLI grounding scorer + entailment-index autodetect (same logic as
        # backend/app/services/hallucination_nli.py).
        self.nli = CrossEncoder(NLI_MODEL_ID, device="cuda", max_length=384)
        try:
            id2label = self.nli.model.config.id2label
            self.nli_entail_idx = next(
                i for i, label in id2label.items()
                if str(label).lower().startswith("entail"))
        except (AttributeError, StopIteration):
            self.nli_entail_idx = 1
        print(f"RAG sidecars ready ({EMBEDDER_REPO}, {RERANKER_REPO}, "
              f"{NLI_MODEL_ID}) in {time.time() - t0:.1f}s")

        self.llm = LLM(
            model=HF_REPO,
            dtype="bfloat16",
            max_model_len=MAX_MODEL_LEN,
            gpu_memory_utilization=0.85,   # leave headroom for the sidecars
            enforce_eager=ENFORCE_EAGER,
        )
        self.tokenizer = self.llm.get_tokenizer()
        # The sync vLLM engine (and the sentence-transformers models) are not
        # thread-safe: with @modal.concurrent the container ACCEPTS calls in
        # parallel, and this lock lines them up on the GPU one by one. Each
        # sub-call is 0.3-3 s, so the queue drains fast — far cheaper than a
        # 2-minute cold boot per call.
        self._gpu_lock = threading.Lock()
        print(f"cbt-brain ready ({HF_REPO}, gpu={GPU}, eager={ENFORCE_EAGER}) "
              f"in {time.time() - t0:.1f}s")

    def _run(self, prompt: str, *, n=1, temperature=0.0, top_p=0.9,
             max_tokens=400, stop=None, truncate=None):
        from vllm import SamplingParams
        params = SamplingParams(
            n=max(1, int(n)),
            temperature=float(temperature),
            top_p=float(top_p),
            max_tokens=int(max_tokens),
            stop=stop,
            truncate_prompt_tokens=truncate,
        )
        with self._gpu_lock:
            outs = self.llm.generate([prompt], params)
        return [o.text for o in outs[0].outputs]

    # ── Role 1: responder (cbt-llm /generate contract) ──────────────────────
    @modal.method()
    def generate(self, messages: list, n_responses: int = 3,
                  temperature: float = 0.8, top_p: float = 0.9,
                  max_new_tokens: int = 400) -> dict:
        t0 = time.time()
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
        responses = [t.strip() for t in self._run(
            prompt, n=n_responses, temperature=temperature, top_p=top_p,
            max_tokens=max_new_tokens, truncate=4096)]
        total = time.time() - t0
        return {
            "responses": responses,
            "timing": {"total_seconds": total,
                       "per_response_seconds": total / max(len(responses), 1)},
            "mode": "modal",
            "model": HF_REPO,
        }

    # ── Role 2: safety triage (cbt-safety /assess contract) ─────────────────
    @modal.method()
    def assess(self, messages: list) -> dict:
        t0 = time.time()
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
        raw = self._run(prompt, n=1, temperature=0.05, top_p=0.9,
                        max_tokens=120, truncate=1024)[0].strip()
        print(f"[SAFETY RAW OUTPUT]: {repr(raw[:300])}")
        return _parse_triage(raw, t0)

    # ── Role 4: embedder (cbt-embedder /embed contract) ─────────────────────
    @modal.method()
    def embed(self, texts: list) -> dict:
        t0 = time.time()
        if not texts:
            return {"vectors": [], "dim": EMBED_DIM, "latency_ms": 0}
        with self._gpu_lock:
            vecs = self.embedder.encode(
                texts, normalize_embeddings=True, convert_to_numpy=True)
        return {
            "vectors": [[float(x) for x in row] for row in vecs.tolist()],
            "dim": int(vecs.shape[1]),
            "latency_ms": round((time.time() - t0) * 1000),
            "model": EMBEDDER_REPO,
        }

    # ── Role 5: reranker (cbt-reranker /rerank contract) ────────────────────
    @modal.method()
    def rerank(self, query: str, candidates: list) -> dict:
        t0 = time.time()
        if not candidates:
            return {"scores": [], "latency_ms": 0}
        pairs = [(query, c) for c in candidates]
        with self._gpu_lock:
            scores = self.reranker.predict(pairs)   # raw logits
        return {
            "scores": [float(s) for s in scores],   # same order as candidates
            "latency_ms": round((time.time() - t0) * 1000),
            "model": RERANKER_REPO,
        }

    # ── Role 6: NLI grounding scorer (raw logits; backend does the math) ────
    @modal.method()
    def score(self, pairs: list) -> dict:
        t0 = time.time()
        if not pairs:
            return {"scores": [], "entail_idx": self.nli_entail_idx,
                    "latency_ms": 0, "model": NLI_MODEL_ID}
        tuples = [(p[0], p[1]) for p in pairs]
        with self._gpu_lock:
            logits = self.nli.predict(tuples, batch_size=32,
                                      convert_to_numpy=True,
                                      show_progress_bar=False)
        return {
            "scores": [[float(x) for x in row] for row in logits.tolist()],
            "entail_idx": self.nli_entail_idx,
            "latency_ms": round((time.time() - t0) * 1000),
            "model": NLI_MODEL_ID,
        }

    # ── Role 3: agent orchestrator (cbt-agent /chat contract) ───────────────
    @modal.method()
    def chat(self, messages: list, tools: list = None,
             temperature: float = 0.3, max_new_tokens: int = 512,
             force_tool_call: bool = False) -> dict:
        t0 = time.time()
        norm = [{"role": m.get("role"), "content": m.get("content", "")}
                for m in messages]
        try:
            prompt = self.tokenizer.apply_chat_template(
                norm, tools=tools or None,
                tokenize=False, add_generation_prompt=True)
        except Exception as e:
            print(f"[AGENT] template with tools failed ({e}); retrying plain")
            prompt = self.tokenizer.apply_chat_template(
                norm, tokenize=False, add_generation_prompt=True)

        # Same constrained-decoding trick as cbt-agent: prefill the Qwen2.5
        # tool-call opener and stop at the closing tag. vLLM handles the stop
        # string natively.
        forced_prefix = ""
        stop = None
        if force_tool_call and tools:
            forced_prefix = "<tool_call>\n"
            prompt = prompt + forced_prefix
            stop = ["</tool_call>"]

        raw = self._run(prompt, n=1, temperature=temperature, top_p=0.9,
                        max_tokens=max_new_tokens, stop=stop,
                        truncate=6144)[0].strip()
        if forced_prefix:
            raw = forced_prefix + raw
        print(f"[AGENT RAW]: {repr(raw[:400])}")

        content, tool_calls = _parse_tool_calls(raw)
        return {
            "content": content,
            "tool_calls": tool_calls,
            "raw": raw,
            "forced": bool(forced_prefix),
            "latency_ms": round((time.time() - t0) * 1000),
            "model": HF_REPO,
        }


# ─────────────────────────────────────────────────────────────────────────────
# HTTP endpoints — same shapes as the three legacy services
# ─────────────────────────────────────────────────────────────────────────────
@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def generate(body: dict):
    """POST /generate — responder (cbt-llm contract)."""
    svc = CBTBrainService()
    return svc.generate.remote(
        messages=body.get("messages", []),
        n_responses=int(body.get("n_responses", 3)),
        temperature=float(body.get("temperature", 0.8)),
        top_p=float(body.get("top_p", 0.9)),
        max_new_tokens=int(body.get("max_new_tokens", 400)),
    )


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def assess(body: dict):
    """POST /assess — safety triage (cbt-safety contract)."""
    svc = CBTBrainService()
    return svc.assess.remote(messages=body.get("messages", []))


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def chat(body: dict):
    """POST /chat — one orchestrator step (cbt-agent contract)."""
    svc = CBTBrainService()
    return svc.chat.remote(
        messages=body.get("messages", []),
        tools=body.get("tools", []),
        temperature=float(body.get("temperature", 0.3)),
        max_new_tokens=int(body.get("max_new_tokens", 512)),
        force_tool_call=bool(body.get("force_tool_call", False)),
    )


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def embed(body: dict):
    """POST /embed — { texts } → { vectors } (cbt-embedder contract)."""
    svc = CBTBrainService()
    return svc.embed.remote(texts=body.get("texts", []))


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def rerank(body: dict):
    """POST /rerank — { query, candidates } → { scores } (cbt-reranker contract)."""
    svc = CBTBrainService()
    return svc.rerank.remote(
        query=body.get("query", ""),
        candidates=body.get("candidates", []),
    )


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def score(body: dict):
    """POST /score — { pairs: [[premise, hypothesis], …] } → { scores,
    entail_idx } (raw NLI logits; the backend keeps its own softmax/mean)."""
    svc = CBTBrainService()
    return svc.score.remote(pairs=body.get("pairs", []))


@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
def health():
    """GET /health — shared by all six roles."""
    return {
        "status": "ok",
        "model": HF_REPO,
        "engine": "vllm",
        "gpu": GPU,
        "roles": ["primary_responder", "safety_crisis_gate",
                  "agent_orchestrator", "embedder", "reranker",
                  "nli_grounding"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test: modal run modal/brain_service.py
# ─────────────────────────────────────────────────────────────────────────────
@app.local_entrypoint()
def debug():
    svc = CBTBrainService()

    print("== 1/3 responder ==")
    out = svc.generate.remote(
        messages=[{"role": "system", "content": "You are a CBT assistant."},
                  {"role": "user", "content": "I always fail at everything."}],
        n_responses=2, temperature=0.7, max_new_tokens=120)
    print("timing:", out["timing"])
    print(out["responses"][0][:200], "\n")

    print("== 2/3 safety ==")
    tri = svc.assess.remote(messages=[
        {"role": "system", "content":
            "Classify the client message into L0/L1/L2/L3 and answer ONLY "
            'JSON: {"level":"..","severity":"..","reason":"..","confidence":0.0}'},
        {"role": "user", "content": "I can't sleep before exams lately."}])
    print(tri, "\n")

    print("== 3/3 agent tool-call ==")
    tools = [{"type": "function", "function": {
        "name": "retrieve_cbt_knowledge",
        "description": "Search the CBT knowledge base.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}}]
    step = svc.chat.remote(
        messages=[{"role": "system", "content":
                   "You are an orchestrator. ALWAYS answer with one tool call."},
                  {"role": "user", "content": "Client: exam stress is crushing me."}],
        tools=tools, temperature=0.0, force_tool_call=True)
    print("tool_calls:", step["tool_calls"])
    print("latency_ms:", step["latency_ms"], "\n")

    print("== 4/5 embedder ==")
    emb = svc.embed.remote(texts=["exam stress", "sleep problems"])
    print("dim:", emb["dim"], "| n:", len(emb["vectors"]),
          "| latency_ms:", emb["latency_ms"], "\n")

    print("== 5/5 reranker ==")
    rr = svc.rerank.remote(
        query="how to handle exam stress",
        candidates=["Decatastrophizing for exam anxiety",
                    "Cooking recipes for students"])
    print("scores:", rr["scores"], "| latency_ms:", rr["latency_ms"])
