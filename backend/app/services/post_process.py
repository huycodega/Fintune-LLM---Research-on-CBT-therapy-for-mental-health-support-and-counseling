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


def parse_draft(raw: str) -> Dict:
    tech = _grab("Technique", raw)
    rat = _grab("Rationale", raw)
    plan = _grab("Plan", raw)
    resp = _grab("Response", raw)
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
