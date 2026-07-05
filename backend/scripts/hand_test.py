"""
Qualitative hand-test: 5 out-of-training prompts, 3 drafts each, scored by
the production detectors and saved per tag for side-by-side reading.

    MODAL_BRAIN_WORKSPACE=<ws> python scripts/hand_test.py --tag v31
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from app.services.prompt_builder import build_messages    # noqa: E402
from app.services.post_process import parse_draft         # noqa: E402
from gen_onpolicy_dpo import _score                       # noqa: E402

OUT_DIR = Path(__file__).parent / "dpo_data"

PROMPTS = [
    "Deep down I believe I'll never be good at public speaking no matter "
    "how much I practice.",
    "Be honest with me: am I wasting my time retaking this class?",
    "rough week. everything piling up.",
    "I told my mom about my grades and it went better than I expected.",
    "Three things are crushing me: rent, finals, and my breakup. Pick "
    "where we start.",
]


def main(workspace: str, tag: str):
    url = f"https://{workspace}--cbt-brain-generate.modal.run"
    results = []
    for text in PROMPTS:
        msgs = build_messages(text, intake=None, analysis=None,
                              session_ctx=None, retrieved=[])
        body = json.dumps({"messages": msgs, "n_responses": 3,
                           "temperature": 0.7}).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=300) as r:
            out = json.loads(r.read().decode())
        drafts = []
        print("=" * 72)
        print("INPUT:", text)
        for i, raw in enumerate(out.get("responses") or []):
            d = parse_draft(raw)
            s = _score(d["response"], text)
            drafts.append({"response": d["response"], "score": s})
            flag = " | ".join(s["why"]) if s["why"] else "clean"
            print(f"--- draft {i} [{flag}] ---")
            print(d["response"])
        results.append({"input": text, "drafts": drafts})
    out_file = OUT_DIR / f"handtest_{tag}.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\nsaved -> {out_file}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default="nguyenhieu3603")
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    main(a.workspace, a.tag)
