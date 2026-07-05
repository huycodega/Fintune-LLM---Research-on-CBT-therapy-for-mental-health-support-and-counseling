"""
Align DPO training prompts with the PRODUCTION prompt format.

v3.1 trained on short blocks ("[CURRENT CLIENT MESSAGE]\\n...") while eval —
and production — wrap every turn in the full prompt_builder.build_messages
output (system prompt + intake/session/task blocks). Preferences learned
under one prompt distribution under-fire when sampled under another; the
stubborn held-out classes (reask, borrowed_name) are consistent with that.

This converter rewrites dpo_all.jsonl rows with `prompt_messages` = the
exact production messages for the same client turn (thread history parsed
back into session_ctx where present), producing dpo_all_aligned.jsonl.

    python scripts/align_dpo_prompts.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.prompt_builder import build_messages    # noqa: E402

OUT_DIR = Path(__file__).parent / "dpo_data"

_CUR = re.compile(r"\[CURRENT CLIENT MESSAGE\]\n(.*?)(?:\n\[CLINICAL TASK\]|\Z)",
                  re.S)
_TURN = re.compile(r"Client: (.*?)\nYou: (.*?)(?=\nClient: |\n\[CURRENT|\Z)",
                   re.S)


def _to_messages(prompt_text: str):
    m = _CUR.search(prompt_text)
    if not m:
        return None
    current = m.group(1).strip()
    hist = [{"user": c.strip(), "reply": y.strip()}
            for c, y in _TURN.findall(prompt_text)]
    ctx = None
    if hist:
        ctx = {"prior_count": len(hist), "last_technique": None,
               "summary": "(no summary yet)", "memory": "",
               "history": hist, "style_prefs": []}
    try:
        return build_messages(current, intake=None, analysis=None,
                              session_ctx=ctx, retrieved=[])
    except Exception:
        return build_messages(current, intake=None, analysis=None,
                              session_ctx=None, retrieved=[])


def main() -> None:
    src = OUT_DIR / "dpo_all.jsonl"
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    out, skipped = [], 0
    for r in rows:
        msgs = _to_messages(r["prompt"])
        if msgs is None:
            skipped += 1
            out.append(r)                      # keep as-is (bare-prompt path)
            continue
        r["prompt_messages"] = msgs
        out.append(r)
    dst = OUT_DIR / "dpo_all_aligned.jsonl"
    with open(dst, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"dpo_all_aligned.jsonl : {len(out)} pairs "
          f"({len(out) - skipped} aligned, {skipped} kept bare)")


if __name__ == "__main__":
    main()
