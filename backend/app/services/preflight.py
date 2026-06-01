"""
Pre-flight clinical validity check.

Rule-based gate that fires BEFORE drafts go to the clinician queue. It
flags drafts where the AI's chosen technique is clinically inappropriate
for the assessed severity, or where the response touches a known
contraindication / boundary issue.

Returns (pass: bool, reasons: list[str]) for each draft. A failing draft
is still stored (we don't drop content silently) but marked
`preflight_pass=False` and routed harder to clinician attention.
"""
from typing import Dict, List, Tuple


# Techniques that should NOT be used at severity=critical.
# Critical cases require crisis referral, not exposure-style techniques.
_TECH_BANNED_AT_CRITICAL = {
    "behavior experiment",
    "exposure therapy",
    "behavioral activation",
    "exposure",
    "thought experiment",
    "self-assertiveness training",
}

# Phrases that should never appear in a response to a client.
_FORBIDDEN_PHRASES = [
    "i am a doctor",
    "you should stop taking",        # never advise medication change
    "diagnose you with",
    "i guarantee",
    "you will definitely",            # over-confident clinical claim
]

# Crisis-required referral language when severity=critical.
_CRISIS_REQUIRED_HINTS = [
    "hotline", "988", "emergency", "crisis", "trusted person",
    "professional", "go to the nearest",
]


def check_draft(draft: Dict, severity: str) -> Tuple[bool, List[str]]:
    """
    Args:
      draft: {"technique": str, "rationale": str, "plan": str, "response": str}
      severity: triage severity ("critical","high","moderate","low")
    """
    reasons: List[str] = []
    tech = (draft.get("technique") or "").strip().lower()
    resp = (draft.get("response") or "").lower()

    # Rule 1: dangerous technique at crisis severity
    if severity == "critical" and tech in _TECH_BANNED_AT_CRITICAL:
        reasons.append(
            f"Technique '{tech}' is contraindicated at critical severity")

    # Rule 2: forbidden phrases anywhere in the response
    for phrase in _FORBIDDEN_PHRASES:
        if phrase in resp:
            reasons.append(f"Forbidden phrase in response: '{phrase}'")

    # Rule 3: at critical severity, response MUST contain crisis-referral
    if severity == "critical":
        if not any(h in resp for h in _CRISIS_REQUIRED_HINTS):
            reasons.append(
                "Critical severity but response missing crisis-referral "
                "language (hotline / 988 / professional / trusted person)")

    # Rule 4: technique must be present + non-empty
    if not tech or tech in ("(unparsed)", "unknown"):
        reasons.append("Technique field empty or unparsed")

    return (len(reasons) == 0, reasons)


def check_all(drafts: List[Dict], severity: str) -> List[Tuple[bool, List[str]]]:
    return [check_draft(d, severity) for d in drafts]
