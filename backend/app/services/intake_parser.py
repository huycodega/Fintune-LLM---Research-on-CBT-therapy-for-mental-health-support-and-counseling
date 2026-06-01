"""
Intake-form parser (pipeline v4 layer "Intake form parser").

Input is the free-form 6-section intake text (Brooke-Davis style example
in the project README). Output is structured data routed simultaneously
to four downstream consumers:

  1. Safety triage      ← section ② (presenting problem)
  2. PostgreSQL         ← all sections, encrypted/structured per schema
  3. Qdrant session_mem ← sections ② ③ embedded for retrieval
  4. Prompt builder     ← all 6 sections injected verbatim

We use deterministic regex/rule parsing (no LLM call needed for first
session) because the intake-form template is fixed. parse_confidence
quantifies how many sections we recognized.
"""
import re
from typing import Dict, Optional


PARSER_VERSION = "v4-intake-en-1.0"


# Regex to split the document by section headers like
# "2. Presenting Problem" or "5. Academic/occupational functioning level:"
_SECTION_HEADERS = [
    (1, r"(?:^|(?<=\s))(?:1[.)]\s*(?:Demographics|Personal\s+Info)|"
        r"(?=Name\s*:))", "demographics"),
    (2, r"(?:^|(?<=\s))2[.)]\s*Presenting\s+Problem", "presenting"),
    (3, r"(?:^|(?<=\s))3[.)]\s*Reason\s+for\s+(?:Seeking\s+)?Counseling",
        "reason"),
    (4, r"(?:^|(?<=\s))4[.)]\s*Past\s+History", "past_history"),
    (5, r"(?:^|(?<=\s))5[.)]\s*Academic/?\s*[Oo]ccupational\s+"
        r"[Ff]unctioning(?:\s+level)?\s*:?", "functioning"),
    (6, r"(?:^|(?<=\s))6[.)]\s*Social\s+Support(?:\s+System)?",
        "social_support"),
]

_DEMOGRAPHIC_FIELDS = [
    ("name",           r"Name\s*:\s*([^\n]+?)(?=\s+Age\s*:|$)"),
    ("age",            r"Age\s*:\s*(\d+)"),
    ("gender",         r"Gender\s*:\s*([^\n]+?)(?=\s+Occupation\s*:|$)"),
    ("occupation",     r"Occupation\s*:\s*([^\n]+?)(?=\s+Education\s*:|$)"),
    ("education",      r"Education\s*:\s*([^\n]+?)(?=\s+Marital\s+Status\s*:|$)"),
    ("marital_status", r"Marital\s+Status\s*:\s*([^\n]+?)"
                       r"(?=\s+Family\s+Details\s*:|$)"),
    ("family_details", r"Family\s+Details\s*:\s*([^\n]+?)"
                       r"(?=\s*\d[.)]|$)"),
]


def _slice_sections(text: str) -> Dict[str, str]:
    """Find header positions, slice text between them."""
    positions = []
    for _num, pattern, key in _SECTION_HEADERS:
        m = re.search(pattern, text, re.I)
        if m:
            positions.append((m.start(), m.end(), key))
    positions.sort()
    out = {}
    for i, (_start, header_end, key) in enumerate(positions):
        next_start = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        out[key] = text[header_end:next_start].strip()
    return out


def _extract_demographics(block: str) -> Dict[str, Optional[str]]:
    res = {}
    for key, pattern in _DEMOGRAPHIC_FIELDS:
        m = re.search(pattern, block, re.I)
        res[key] = m.group(1).strip().rstrip(",.") if m else None
    # coerce age
    if res.get("age"):
        try:
            res["age"] = int(res["age"])
        except (ValueError, TypeError):
            pass
    return res


def _extract_functioning(block: str) -> Dict[str, Optional[str]]:
    """§5 has 3 sub-areas: occupational, interpersonal, daily."""
    sub = {}
    patterns = [
        ("occupational",
         r"(?:Academic/?\s*)?[Oo]ccupational[^:]*:\s*(.+?)"
         r"(?=Interpersonal|Daily|$)"),
        ("interpersonal",
         r"Interpersonal[^:]*:\s*(.+?)(?=Daily|$)"),
        ("daily",
         r"Daily\s+life\s*:\s*(.+?)$"),
    ]
    for key, pattern in patterns:
        m = re.search(pattern, block, re.I | re.S)
        sub[key] = m.group(1).strip().rstrip(",.") if m else None
    return sub


def parse_intake(text: str) -> Dict:
    """
    Returns the routed payload:
      {
        "demographics": {...},                # § 1, JSONB to Postgres
        "presenting":   "...",                 # § 2, PHI → encrypt → Postgres
        "reason":       "...",                 # § 3, plain → Postgres
        "past_history": {...},                 # § 4, JSONB
        "functioning":  {...},                 # § 5, JSONB
        "social_support": "...",               # § 6, plain
        "for_safety_triage":   "<§2 text>",    # route → safety_gate.assess()
        "for_embedding":       "<§2+§3 text>", # route → Qdrant session_memory
        "for_prompt_builder":  "<all 6 verbatim>",
        "parser_version":      PARSER_VERSION,
        "parse_confidence":    float,
      }
    """
    sections = _slice_sections(text)
    n_found = len(sections)
    confidence = round(n_found / 6.0, 2)

    demographics = _extract_demographics(text if "demographics" not in sections
                                          else sections["demographics"])
    functioning = _extract_functioning(sections.get("functioning", ""))

    past_history = {
        "raw": sections.get("past_history", ""),
        "prior_similar": bool(
            re.search(r"have\s+(?:not\s+)?experienced\s+similar",
                      sections.get("past_history", ""), re.I)),
        "prior_treatment": bool(
            re.search(r"received\s+(?:treatment|counseling)",
                      sections.get("past_history", ""), re.I)),
    }

    # Routes
    safety_text = sections.get("presenting", "") or text
    embedding_text = (
        f"Presenting problem: {sections.get('presenting','')}\n"
        f"Reason for counseling: {sections.get('reason','')}"
    ).strip()

    return {
        "demographics": demographics,
        "presenting": sections.get("presenting", ""),
        "reason": sections.get("reason", ""),
        "past_history": past_history,
        "functioning": functioning,
        "social_support": sections.get("social_support", ""),
        "for_safety_triage": safety_text,
        "for_embedding": embedding_text,
        "for_prompt_builder": text,
        "parser_version": PARSER_VERSION,
        "parse_confidence": confidence,
    }
