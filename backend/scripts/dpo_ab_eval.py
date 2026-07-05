"""
A/B eval: v2 (prod brain) vs v3 (staging brain) on HELD-OUT inputs.

Measures GENERALIZATION of the DPO fine-tune: the held-out file shares no
inputs (topics or phrasings) with any training source, so any improvement
here is learned behaviour, not memorization. Scoring reuses the exact
production failure detectors (gen_onpolicy_dpo._score).

    # baseline (prod model, v2):
    python scripts/dpo_ab_eval.py --workspace nbhklbv        --tag v2
    # candidate (staging brain serving v3):
    python scripts/dpo_ab_eval.py --workspace nguyenhieu3603 --tag v3
    # then compare the two saved summaries:
    python scripts/dpo_ab_eval.py --compare v2 v3

Writes dpo_data/ab_<tag>.json with per-class failure rates. The comparison
table is the before/after evidence for the report — and the GATE input:
v3 must beat v2 on the habit classes WITHOUT new failure classes appearing.
"""
import argparse
import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from app.services.prompt_builder import build_messages     # noqa: E402
from app.services.post_process import parse_draft          # noqa: E402
from gen_onpolicy_dpo import _score                        # noqa: E402

OUT_DIR = Path(__file__).parent / "dpo_data"
OUT_DIR.mkdir(exist_ok=True)
DEFAULT_INPUTS = Path(__file__).parent / "dpo_holdout_inputs.txt"


def run(workspace: str, tag: str, inputs_path: str, n: int, temp: float):
    url = f"https://{workspace}--cbt-brain-generate.modal.run"
    inputs = [l.strip() for l in Path(inputs_path).read_text(encoding="utf-8")
              .splitlines() if l.strip() and not l.startswith("#")]
    print(f"[{tag}] {len(inputs)} held-out inputs x {n} drafts -> {url}")

    total, clean, fail_counts = 0, 0, Counter()
    lengths, failed_calls = [], 0
    for i, text in enumerate(inputs):
        msgs = build_messages(text, intake=None, analysis=None,
                              session_ctx=None, retrieved=[])
        body = json.dumps({"messages": msgs, "n_responses": n,
                           "temperature": temp}).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                out = json.loads(r.read().decode())
        except Exception as e:
            failed_calls += 1
            print(f"  [{i}] call failed: {e}")
            continue
        for raw in out.get("responses") or []:
            d = parse_draft(raw)
            s = _score(d["response"], text)
            total += 1
            lengths.append(len(d["response"]))
            if s["fails"] == 0:
                clean += 1
            for w in s["why"]:
                fail_counts[w] += 1
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(inputs)} — clean {clean}/{total}")

    summary = {
        "tag": tag, "workspace": workspace, "inputs": len(inputs),
        "drafts_scored": total, "clean": clean,
        "clean_rate": round(clean / total, 3) if total else None,
        "failure_counts": dict(fail_counts),
        "failure_rates": {k: round(v / total, 3)
                          for k, v in fail_counts.items()} if total else {},
        "avg_len": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "failed_calls": failed_calls, "n": n, "temperature": temp,
    }
    out_file = OUT_DIR / f"ab_{tag}.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"saved -> {out_file}")


def compare(tag_a: str, tag_b: str):
    a = json.loads((OUT_DIR / f"ab_{tag_a}.json").read_text(encoding="utf-8"))
    b = json.loads((OUT_DIR / f"ab_{tag_b}.json").read_text(encoding="utf-8"))
    keys = sorted(set(a["failure_rates"]) | set(b["failure_rates"]))
    w = max([len(k) for k in keys] + [12])
    print(f"{'metric'.ljust(w)}  {tag_a:>8}  {tag_b:>8}  delta")
    print("-" * (w + 30))
    ar, br = a["clean_rate"] or 0, b["clean_rate"] or 0
    print(f"{'clean_rate'.ljust(w)}  {ar:>8.3f}  {br:>8.3f}  "
          f"{'+' if br >= ar else ''}{br - ar:.3f}")
    for k in keys:
        av = a["failure_rates"].get(k, 0.0)
        bv = b["failure_rates"].get(k, 0.0)
        flag = "  <-- NEW FAILURE CLASS" if av == 0 and bv > 0 else ""
        print(f"{k.ljust(w)}  {av:>8.3f}  {bv:>8.3f}  "
              f"{'+' if bv >= av else ''}{bv - av:.3f}{flag}")
    print(f"{'avg_len'.ljust(w)}  {a['avg_len']:>8}  {b['avg_len']:>8}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace")
    ap.add_argument("--tag", default="run")
    ap.add_argument("--inputs", default=str(DEFAULT_INPUTS))
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--compare", nargs=2, metavar=("TAG_A", "TAG_B"))
    args = ap.parse_args()
    if args.compare:
        compare(*args.compare)
    elif args.workspace:
        run(args.workspace, args.tag, args.inputs, args.n, args.temp)
    else:
        print(__doc__)
