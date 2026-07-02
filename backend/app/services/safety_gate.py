"""
Safety triage gate — Huysun29/cbt-qwen2.5-7b-v2 (Qwen2.5-7B fine-tuned v2).

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
    r"take\s+my\s+(own\s+)?life|"
    # active planning / preparation behaviour. "looked up methods" must be
    # adjacent — a topic noun in between ("study methods", "research methods")
    # is benign and must NOT trip the crisis net.
    r"look(ed|ing)?\s+up\s+(a\s+|some\s+)?methods?\b(?!\s+(to|for|of|on|about)\s+\w)|"
    r"(method|way)s?\s+to\s+(die|kill\s+my|end\s+(it|my)|hurt\s+my|harm\s+my)|"
    r"how\s+to\s+(kill\s+my|end\s+my\s+life|end\s+it))\b", re.I)

# Overdose / means-with-intent preparation behaviour the keyword net misses.
# High precision: needs an explicit "overdose", OR a medication noun AND a
# "take/swallow all/whole" phrase in close proximity (either order) — so it
# catches "looked at the pills … thought about taking all of them" and
# "swallow the whole bottle of pills" without tripping on ordinary
# medication talk ("I take my pills every morning").
_L0_MEANS_PAT = re.compile(
    r"overdos\w*"
    r"|\b(?:pills?|tablets?|sleeping\s+pills?|medication|meds)\b"
    r"[^.?!]{0,60}\b(?:tak(?:e|ing)|took|swallow\w*)\s+"
    r"(?:all|the\s+whole|the\s+entire|a\s+whole)\b"
    r"|\b(?:tak(?:e|ing)|took|swallow\w*)\s+"
    r"(?:all|the\s+whole|the\s+entire|a\s+whole|a\s+handful)\b"
    r"[^.?!]{0,40}\b(?:pills?|tablets?|sleeping\s+pills?|medication|meds)\b",
    re.I)

_L1_PAT = re.compile(
    r"\b(self.?harm|cut\s+my\s*self|hurt\s+my\s*self|hurt\s+(someone|him|her|them)|"
    r"hopeless|worthless|can'?t\s+go\s+on|burden\s+(to|on)\s+\w+|"
    r"better\s+off\s+(dead|without\s+me))\b", re.I)

_L2_PAT = re.compile(
    r"\b(depress\w*|anxi\w*|panic\w*|ptsd|insomnia|lonely|"
    r"overwhelm\w*|out\s+of\s+control|haunting\s+thought|"
    r"can't\s+(function|cope|sleep)|numb\w*)\b", re.I)

# Third-party crisis: someone ELSE (a friend/relative) is at risk. The user
# isn't in their own crisis, but we still escalate (share resources / involve
# support) rather than hand out a casual reply. Handles "wants" (third-person).
_THIRD_PARTY_RISK_PAT = re.compile(
    r"\b(my\s+(friend|mate|roommate|room-?mate|sister|brother|mom|mother|dad|"
    r"father|partner|girlfriend|boyfriend|classmate|cousin|colleague)|"
    r"a\s+friend|someone\s+i\s+know|somebody)\b[^.?!]{0,45}\b"
    r"(wants?\s+to\s+die|wants?\s+to\s+(kill|hurt|harm)\s+(her|him|them)sel(f|ves)|"
    r"is\s+suicidal|talking\s+about\s+(suicide|killing\s+(her|him|them)sel)|"
    r"going\s+to\s+kill\s+(her|him|them)sel|end\s+(her|his|their)\s+life)\b", re.I)

# Violence toward OTHERS. Person-object required so idioms ("kill the exam",
# "beat the game") don't trip it.
_VIOLENCE_PAT = re.compile(
    r"\b(going\s+to|gonna|will|want\s+to|planning\s+to|about\s+to)\b"
    r"[^.?!]{0,25}\b(hurt|kill|attack|beat|stab|shoot|harm|strangle)\b"
    r"[^.?!]{0,20}\b(him|her|them|someone|somebody|people|everyone|"
    r"my\s+(roommate|room-?mate|friend|partner|classmate|sister|brother|mom|"
    r"dad|family|neighbou?r|ex)|that\s+(guy|girl|person))\b|"
    r"\bhurt\s+(my\s+(roommate|room-?mate|friend|partner|classmate|sister|"
    r"brother|family|neighbou?r)|someone\s+else)\b", re.I)


def _heuristic(text: str) -> Dict:
    if _L0_PAT.search(text) or _L0_MEANS_PAT.search(text):
        return {"triage_level": "L0", "severity": "critical",
                "confidence": 0.95, "reason": "Crisis language detected",
                "source": "heuristic"}
    if _VIOLENCE_PAT.search(text):
        return {"triage_level": "L1", "severity": "high",
                "confidence": 0.80, "reason": "Possible risk of harm to others",
                "source": "heuristic"}
    if _THIRD_PARTY_RISK_PAT.search(text):
        return {"triage_level": "L1", "severity": "high",
                "confidence": 0.72, "reason": "Third-party crisis disclosed",
                "source": "heuristic"}
    if _L1_PAT.search(text):
        return {"triage_level": "L1", "severity": "high",
                "confidence": 0.78, "reason": "High-risk language detected",
                "source": "heuristic"}
    if _PASSIVE_RISK_PAT.search(text):
        return {"triage_level": "L1", "severity": "high",
                "confidence": 0.72,
                "reason": "Passive ideation / self-erasure language detected",
                "source": "heuristic"}
    if _L2_PAT.search(text):
        return {"triage_level": "L2", "severity": "moderate",
                "confidence": 0.55, "reason": "Moderate distress markers",
                "source": "heuristic"}
    return {"triage_level": "L3", "severity": "low",
            "confidence": 0.30, "reason": "No acute risk markers",
            "source": "heuristic"}


# Passive / indirect ideation markers the L0/L1 keyword patterns miss: self-
# erasure ("disappeared for a while"), burdensomeness ("less disappointed if I
# was gone"), exhaustion-of-being ("tired of existing"), and the "pretending
# I'm okay" mask. These are genuine passive suicidal-ideation signals, so they
# now feed the PRIMARY gate (_heuristic → L1 hard override), not just the
# agent's defense-in-depth re-check. Patterns require a self-referential context
# so value/meaning distress ("what's the point of this degree?") stays L2.
_PASSIVE_RISK_PAT = re.compile(
    r"\b("
    r"no\s+point\s+(anymore|in\s+(living|trying|going\s+on))|"
    r"what'?s\s+the\s+point\s+(anymore|of\s+(it\s+all|living|trying|going\s+on|even\s+being\s+here))|"
    r"done\s+trying|giving\s+away\s+my\s+(things|stuff|belongings|possessions)|"
    r"better\s+off\s+(without\s+me|if\s+i\s+(was|were)\s+(gone|dead|not\s+here))|"
    r"nothing\s+(will|is\s+going\s+to)\s+get\s+better|"
    r"(no|don'?t\s+see\s+a|can'?t\s+see\s+a|there'?s\s+no)\s+way\s+out|"
    r"tired\s+of\s+(it\s+all|living|everything|all\s+of\s+this|existing|"
    r"being\s+(alive|here|around))|"
    r"(disappear|disappeared)\s+for\s+(a\s+while|good)|"
    r"if\s+i\s+(?:\w+\s+){0,2}(disappeared|was\s+gone|were\s+gone|"
    r"wasn'?t\s+(here|around)|weren'?t\s+here)|"
    r"(less\s+disappointed|happier|better\s+off)\s+if\s+i\s+"
    r"(?:\w+\s+){0,2}(disappeared|was\s+gone|wasn'?t\s+here)|"
    r"pretending\s+(i'?m|to\s+be)\s+(ok|okay|fine|alright|all\s+right)"
    r")\b", re.I)


def has_acute_risk(text: str) -> bool:
    """True if the text carries acute-risk language (crisis, high-risk, or
    passive ideation). Reusable, zero-dependency — the agent uses this as a
    defense-in-depth re-check before letting an L2/L3 turn auto-generate."""
    if not text:
        return False
    return bool(_L0_PAT.search(text) or _L0_MEANS_PAT.search(text)
                or _L1_PAT.search(text) or _PASSIVE_RISK_PAT.search(text)
                or _THIRD_PARTY_RISK_PAT.search(text)
                or _VIOLENCE_PAT.search(text))


# ─────────────────────────────────────────────────────────────────────────────
# Second-pass VENT-vs-CONCERN screen (L2 release valve)
# ─────────────────────────────────────────────────────────────────────────────
# The triage model reads much ordinary venting as L2, which pre-holds every
# such turn for a clinician. This dedicated binary check lets a turn through
# ONLY when the model affirmatively rules it everyday venting; any hint of
# masked crisis, any parse failure, mock mode, or timeout → CONCERN → the turn
# waits for review exactly like before. Strictly fail-closed.
_VENT_SYSTEM = (
    "You screen messages in a mental-health support chat that a first-pass "
    "triage rated MODERATE. Choose exactly one label:\n"
    "VENT — ordinary everyday venting (exam or work stress, tiredness, family "
    "friction, self-doubt, relationship annoyances) with no sign of danger; a "
    "warm supportive reply can safely be sent right away.\n"
    "CONCERN — ANY hint, however small or indirect, of hopelessness, self-harm, "
    "suicide, harm to others, abuse, psychosis, a farewell or 'at peace' tone, "
    "giving things away, or distress that feels much heavier than the words "
    "used — including signals from the earlier conversation.\n"
    "If you are unsure in any way, answer CONCERN.\n"
    "Reply with ONE word only: VENT or CONCERN.")


def vent_check(text: str, history: Optional[list] = None) -> bool:
    """True ONLY on an unambiguous VENT verdict from the model. Every failure
    mode (mock, degraded, exception, ambiguous output) returns False so the
    caller falls back to clinician pre-approval."""
    try:
        from app.services import llm_client
        if history:
            convo = "\n".join(f"Client (earlier): {h}" for h in history)
            user = (f"[CONVERSATION SO FAR]\n{convo}\n\n"
                    f"[CURRENT CLIENT MESSAGE]\n{text}")
        else:
            user = text
        gen = llm_client.generate(
            [{"role": "system", "content": _VENT_SYSTEM},
             {"role": "user", "content": user}],
            n=1, temperature=0.0)
        if not gen or gen.get("degraded") or gen.get("mode") == "mock":
            return False
        out = (gen.get("responses") or [""])[0].strip().upper()
        return "VENT" in out and "CONCERN" not in out
    except Exception:
        return False


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


# Appended to the system prompt when conversation context is supplied. Verified
# (scripts/triage_context_experiment.py) to fix isolated-message over-triage
# while still escalating a real, regex-evading crisis to L0.
_CONTEXT_HINT = (
    "\n\nYou are given the prior turns of the conversation for CONTEXT only. "
    "Classify ONLY the latest message marked [CURRENT CLIENT MESSAGE], using "
    "the earlier turns to understand its meaning (e.g. a client reasoning "
    "themselves OUT of a fear is not high risk). Never downgrade genuine "
    "suicidal intent because earlier turns were calm."
)


def _build_messages(text: str, history: Optional[list]) -> list:
    """System+user messages for the safety model. With history present, prepend
    the prior client turns and switch to the context-aware system prompt."""
    if history:
        convo = "\n".join(f"Client (earlier): {h}" for h in history)
        return [
            {"role": "system", "content": _SAFETY_SYSTEM_PROMPT + _CONTEXT_HINT},
            {"role": "user",
             "content": f"[CONVERSATION SO FAR]\n{convo}\n\n"
                        f"[CURRENT CLIENT MESSAGE]\n{text}"},
        ]
    return [
        {"role": "system", "content": _SAFETY_SYSTEM_PROMPT},
        {"role": "user", "content": f"[CLIENT MESSAGE]\n{text}"},
    ]


def _call_modal(text: str, history: Optional[list] = None,
                timeout: int = 600) -> Optional[Dict]:
    """Call Modal-hosted cbt-qwen2.5-7b-v2 safety endpoint. Returns None on failure."""
    url = settings.modal_safety_endpoint
    if not url:
        return None

    body = json.dumps({
        "messages": _build_messages(text, history),
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

        # Modal safety_service.py returns the triage dict directly:
        # {"level":"L2","severity":"moderate","reason":"...","confidence":0.7,...}
        level = raw.get("level", "")
        if level in ("L0", "L1", "L2", "L3"):
            return {
                "triage_level": level,
                "severity": raw.get("severity", _level_to_severity(level)),
                "confidence": float(raw.get("confidence", 0.7)),
                "reason": raw.get("reason", "QWen safety model"),
                "source": "cbt-qwen2.5-7b-v2",
                "latency_ms": round(latency * 1000),
                # keep the model's structured output verbatim for the eval log
                "raw_model": json.dumps(raw, ensure_ascii=False)[:600],
            }

        log.warning("Safety model unexpected response: %r", str(raw)[:200])
        return None
    except Exception as e:
        log.warning("Safety Modal call failed (%s) — heuristic fallback", e)
        return None


def _level_to_severity(level: str) -> str:
    return {"L0": "critical", "L1": "high", "L2": "moderate"}.get(level, "low")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def _annotate(out: Dict, heuristic_level: str, model: Optional[Dict]) -> Dict:
    """Attach shadow fields so triage_log can measure regex-vs-model
    disagreement. Does NOT change `triage_level` — purely observational."""
    out["heuristic_level"] = heuristic_level
    if model is not None:
        out["model_level"] = model["triage_level"]
        out["model_confidence"] = model.get("confidence")
        out["raw_model"] = model.get("raw_model")
        # the signal we care about: did the regex and the model disagree on
        # level? (e.g. heuristic forced L1 but the model would have said L3)
        out["disagreement"] = (model["triage_level"] != heuristic_level)
    else:
        out["model_level"] = None
        out["disagreement"] = None
    return out


def assess(text: str, history: Optional[list] = None) -> Dict:
    """
    Assess safety level of client message.

    `history` (optional): prior client turns of this thread, most recent last.
    When present, the model judges the current message WITH that context, which
    fixes isolated-message over-triage. The heuristic regex still runs on the
    current message only, so the crisis hard-override is unaffected.

    Priority logic (safety-first — UNCHANGED behavior):
        1. Heuristic L0/L1 → ALWAYS wins (never soften a crisis classification)
        2. Modal cbt-qwen2.5-7b-v2 → for L2/L3 nuanced assessment
        3. Heuristic fallback → when Modal unavailable

    On an L0/L1 hard override we OPTIONALLY still call the model in shadow mode
    to record what it would have said. The override always stands; the shadow
    result never changes the returned level.
    """
    # Heuristic first — crisis keywords are hard overrides
    heuristic = _heuristic(text)
    hlevel = heuristic["triage_level"]

    if hlevel in ("L0", "L1"):
        log.info("Safety heuristic hard override: %s", hlevel)
        shadow = None
        if settings.triage_shadow_model_on_override and not settings.mock_llm:
            # best-effort; the override stands regardless of what this returns
            shadow = _call_modal(text, history)
        return _annotate(dict(heuristic), hlevel, shadow)

    # In mock/dev mode skip the network call entirely
    if settings.mock_llm:
        return _annotate(dict(heuristic), hlevel, None)

    # For L2/L3: call Modal model for nuanced assessment
    result = _call_modal(text, history)
    if result is not None:
        # Never let model downgrade a heuristic L2 to L3 if keywords match
        if hlevel == "L2" and result["triage_level"] == "L3":
            result["triage_level"] = "L2"
            result["severity"] = "moderate"
            result["reason"] += " (upgraded by heuristic)"
        return _annotate(result, hlevel, result)

    log.info("Safety triage heuristic fallback: level=%s", hlevel)
    return _annotate(dict(heuristic), hlevel, None)


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
