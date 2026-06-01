"""
Safety triage gate — Huysun29/cbt-qwen-7b (QWen2.5-7B + LoRA).

Two-tier architecture
─────────────────────
Tier 1 (preferred): Call the Modal-hosted QWen model via
  MODAL_SAFETY_ENDPOINT.  The model is prompted with a structured
  classification task and returns JSON: {level, severity, reason, confidence}.

Tier 2 (fallback): Local regex heuristic — zero-dependency, runs in < 1 ms,
  used when Modal endpoint is unset or unreachable, or during dev with
  MOCK_LLM=true.

4-level triage mapping
───────────────────────
  L0  CRISIS    — active suicidal / homicidal ideation, immediate danger
  L1  HIGH      — passive ideation, significant self-harm risk
  L2  MODERATE  — clinical distress (depression / anxiety / ptsd) without
                   imminent risk; AI proceeds + mandatory clinician review
  L3  ROUTINE   — general CBT concern; full pipeline, spot-check audit only
"""
import json
import logging
import re
import time
import urllib.request
from typing import Dict, Optional

from app.core.config import settings


log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Heuristic fallback — zero-dependency, instant
# ─────────────────────────────────────────────────────────────────────────────
_L0_PAT = re.compile(
    r"\b(kill\s+my\s*self|end\s+(it\s+all|my\s+life)|want\s+to\s+die|"
    r"suicid\w*|no\s+reason\s+to\s+live|disappear\s+forever|"
    r"take\s+my\s+(own\s+)?life)\b", re.I)

_L1_PAT = re.compile(
    r"\b(self.?harm|cut\s+my\s*self|hurt\s+my\s*self|hurt\s+(someone|him|her|them)|"
    r"hopeless|worthless|can'?t\s+go\s+on|burden\s+(to|on)\s+\w+|"
    r"better\s+off\s+(dead|without\s+me))\b", re.I)

_L2_PAT = re.compile(
    r"\b(depress\w*|anxi\w*|panic\w*|ptsd|insomnia|lonely|"
    r"overwhelm\w*|out\s+of\s+control|haunting\s+thought|"
    r"can't\s+(function|cope|sleep)|numb\w*)\b", re.I)


def _heuristic(text: str) -> Dict:
    if _L0_PAT.search(text):
        return {"triage_level": "L0", "severity": "critical",
                "confidence": 0.95, "reason": "Crisis language detected",
                "source": "heuristic"}
    if _L1_PAT.search(text):
        return {"triage_level": "L1", "severity": "high",
                "confidence": 0.78, "reason": "High-risk language detected",
                "source": "heuristic"}
    if _L2_PAT.search(text):
        return {"triage_level": "L2", "severity": "moderate",
                "confidence": 0.55, "reason": "Moderate distress markers",
                "source": "heuristic"}
    return {"triage_level": "L3", "severity": "low",
            "confidence": 0.30, "reason": "No acute risk markers",
            "source": "heuristic"}


# ─────────────────────────────────────────────────────────────────────────────
# Modal-hosted QWen safety model
# ─────────────────────────────────────────────────────────────────────────────
_SAFETY_SYSTEM_PROMPT = (
    "You are a mental health safety triage system trained as a clinical CBT "
    "specialist. Your ONLY task is to classify the client message into exactly "
    "one safety level and return structured JSON.\n\n"
    "Safety levels:\n"
    "  L0 CRISIS   — active suicidal or homicidal ideation, immediate danger\n"
    "  L1 HIGH     — passive ideation or significant self-harm risk\n"
    "  L2 MODERATE — clinical distress (depression/anxiety/ptsd) without "
    "imminent danger\n"
    "  L3 ROUTINE  — general mental-health concern, standard CBT response\n\n"
    "Respond ONLY with valid JSON:\n"
    '{"level":"<L0|L1|L2|L3>","severity":"<critical|high|moderate|low>",'
    '"reason":"<one sentence>","confidence":<0.0-1.0>}'
)


def _call_modal(text: str, timeout: int = 15) -> Optional[Dict]:
    """Call Modal-hosted cbt-qwen-7b safety endpoint. Returns None on failure."""
    url = settings.modal_safety_endpoint
    if not url:
        return None

    body = json.dumps({
        "messages": [
            {"role": "system", "content": _SAFETY_SYSTEM_PROMPT},
            {"role": "user", "content": f"[CLIENT MESSAGE]\n{text}"},
        ],
        "max_new_tokens": 120,
        "temperature": 0.1,   # nearly deterministic for triage
    }).encode()

    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST")
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = json.loads(r.read().decode())
        latency = time.time() - t0
        # Modal returns {"response": "...<json>..."} or {"responses": [...]}
        text_out = (raw.get("response") or
                    (raw.get("responses") or [""])[0])
        # Extract JSON from model output
        m = re.search(r'\{[^{}]*"level"\s*:\s*"L[0-3]"[^{}]*\}', text_out, re.S)
        if not m:
            log.warning("Safety model: no valid JSON in output: %s", text_out[:200])
            return None
        result = json.loads(m.group())
        level = result.get("level", "")
        if level not in ("L0", "L1", "L2", "L3"):
            log.warning("Safety model: unexpected level=%s", level)
            return None
        return {
            "triage_level": level,
            "severity": result.get("severity", _level_to_severity(level)),
            "confidence": float(result.get("confidence", 0.7)),
            "reason": result.get("reason", "QWen safety model"),
            "source": "cbt-qwen-7b",
            "latency_ms": round(latency * 1000),
        }
    except Exception as e:
        log.warning("Safety Modal call failed (%s) — heuristic fallback", e)
        return None


def _level_to_severity(level: str) -> str:
    return {"L0": "critical", "L1": "high", "L2": "moderate"}.get(level, "low")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def assess(text: str) -> Dict:
    """
    Assess safety level of client message.

    Returns:
        {triage_level, severity, confidence, reason, source,
         optionally latency_ms}

    Priority:
        1. Modal endpoint (cbt-qwen-7b) when MODAL_SAFETY_ENDPOINT is set
        2. Heuristic regex fallback (always fast, always available)
    """
    # In mock/dev mode skip the network call entirely
    if settings.mock_llm:
        return _heuristic(text)

    result = _call_modal(text)
    if result is not None:
        return result

    # Heuristic covers endpoint-down / unset / parse-failure cases
    out = _heuristic(text)
    log.info("Safety triage heuristic fallback: level=%s", out["triage_level"])
    return out


def health() -> Dict:
    """Returns health status of the safety gate."""
    if settings.mock_llm:
        return {"reachable": True, "mode": "heuristic",
                "model": settings.safety_hf_model_repo}
    url = settings.modal_safety_health_endpoint
    if not url:
        return {"reachable": True, "mode": "heuristic",
                "note": "MODAL_SAFETY_HEALTH_ENDPOINT not set — using heuristic"}
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return {"reachable": True, "mode": "modal",
                    **json.loads(r.read().decode())}
    except Exception as e:
        return {"reachable": False, "mode": "modal", "error": str(e)}
