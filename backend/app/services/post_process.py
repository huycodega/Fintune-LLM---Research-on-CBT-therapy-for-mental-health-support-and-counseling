"""
Post-processing for LLM output:

  1. parse_draft   : extract Technique / Rationale / Plan / Response
                     from a raw generation
  2. parse_all     : parse + dedupe (same technique + similar opening
                     fold into one)
  3. grounding     : NLI-based hallucination check via
                     `hallucination_nli.grounding_nli` (DeBERTa NLI
                     cross-encoder); falls back to lexical overlap
                     automatically when the NLI model is unavailable.
"""
import re
from typing import Dict, List

from app.services import hallucination_nli


# ============================================================
# Parser
# ============================================================
def _grab(field: str, text: str) -> str:
    m = re.search(
        rf"{field}\s*:\s*(.+?)(?=\n(?:Technique|Rationale|Plan|Response)\s*:|\Z)",
        text, re.S | re.I)
    return m.group(1).strip() if m else ""


def _trim_runaway(resp: str) -> str:
    """Cut a self-continued dialogue. The model sometimes answers, then keeps
    going and SIMULATES the client's next turn(s) on new lines — fabricating
    words the client never said. A client-facing CBT reply is one short
    paragraph, so once the first line is a complete sentence and more text
    follows, drop the remainder."""
    resp = (resp or "").strip()
    if "\n" not in resp:
        return resp
    first, rest = resp.split("\n", 1)
    first = first.strip()
    if first and first[-1] in ".!?" and rest.strip():
        return first
    return resp


def parse_draft(raw: str) -> Dict:
    tech = _grab("Technique", raw)
    rat = _grab("Rationale", raw)
    plan = _grab("Plan", raw)
    resp = _trim_runaway(_grab("Response", raw))
    well = bool(tech and resp)
    if not resp:
        resp = raw.strip()
    return {
        "technique": tech or "(unparsed)",
        "rationale": rat,
        "plan": plan,
        "response": resp,
        "well_formed": well,
    }


_EMPH_SYS = (
    "You add emphasis to a message. Return the message EXACTLY as given, but "
    "wrap the 1-2 words or short phrases that carry the most meaning (the key "
    "insight or next action) in markdown **bold**. Do NOT change, add, remove, "
    "or reorder any other words, and never bold whole sentences. Output ONLY the "
    "message.")


def emphasize_llm(text: str) -> str:
    """Ask the model to bold the naturally-important part of ITS OWN reply — so
    the emphasis is contextual, not a fixed word list. Best-effort: returns the
    text unchanged when the model is mock/unavailable, already bolded, or the
    output looks tampered (length drift / no bold)."""
    text = (text or "").strip()
    if not text or "**" in text:
        return text
    try:
        from app.services import llm_client
        gen = llm_client.generate(
            [{"role": "system", "content": _EMPH_SYS},
             {"role": "user", "content": text}],
            n=1, temperature=0.0)
        if not gen or gen.get("degraded") or gen.get("mode") == "mock":
            return text
        out = (gen.get("responses") or [""])[0].strip()
        # Guard: must have added bold and stayed the same reply (no rewrite).
        if "**" in out and 0.7 <= len(out) / max(1, len(text)) <= 1.4:
            return out
        return text
    except Exception:
        return text


def parse_all(raws: List[str]) -> List[Dict]:
    parsed = [parse_draft(r) for r in raws]
    seen, out = set(), []
    for p in parsed:
        key = (p["technique"].lower().strip(),
               p["response"][:60].lower().strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out or parsed


# ============================================================
# Grounding (cheap lexical-overlap baseline)
# ============================================================
_WORD = re.compile(r"\b[a-zA-Z][a-zA-Z\-']{2,}\b")


def _tokens(s: str) -> set:
    return {w.lower() for w in _WORD.findall(s)}


def grounding_score(response: str, retrieved: List[Dict]) -> float:
    """NLI-based grounding (DeBERTa cross-encoder) with automatic
    lexical-overlap fallback if the NLI model can't load."""
    return hallucination_nli.grounding_nli(response, retrieved)
