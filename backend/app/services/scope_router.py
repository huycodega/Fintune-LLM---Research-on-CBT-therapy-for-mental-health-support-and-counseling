"""
Scope router — keep the CBT chat on-topic, safely.

Runs AFTER the safety gate, and ONLY on L3 (routine, already-safe) messages.
It sorts a message into:
  • personal  — wellbeing content; the normal CBT path (agent/pipeline).
  • meta      — a question ABOUT MindCare itself → a short FYI reply.
  • offtopic  — a non-wellbeing request (coding, homework, general knowledge,
                weather…) → a warm redirect back to scope.

Design rules (so it never harms support or safety):
  • Deterministic keyword matching — no LLM, no PHI leaves the backend.
  • Conservative: ANY first-person feeling / wellbeing signal short-circuits to
    "personal", and the default is "personal". A real support message is never
    redirected.
  • Safety is untouched — L0/L1/L2 never reach this router; it only ever sees
    safe, routine (L3) turns.
"""
import re

# Genuine wellbeing / emotion language → always personal (bias to support).
# Deliberately does NOT use bare pronouns (i/me/my) — those are too weak and
# appear in off-topic requests too ("write me a script").
_PERSONAL_PAT = re.compile(
    r"\b(i feel|i'?m feeling|feeling|feelings|stressed?|stress|anxious|anxiety|"
    r"worried|worry|sad|depress\w*|unhappy|down|lonely|alone|tired|exhaust\w*|"
    r"overwhelm\w*|cope|coping|struggl\w*|upset|angry|scared|afraid|nervous|"
    r"panic|hopeless|insomnia|can'?t sleep|burn(ed|t)? ?out|emotional|cry\w*|"
    r"my (mind|head|thoughts|mood|feelings|emotions)|"
    r"help me (cope|deal|manage|feel|calm|relax)|mental health|self[- ]?care)\b",
    re.I)

# Questions ABOUT MindCare / the assistant itself.
_META_PAT = re.compile(
    r"\b(mindcare|this app|this (ai|bot|chat|system|tool|service|website)|"
    r"are you (a )?(real ?|human|therapist|bot|ai|robot|person|machine)|"
    r"who (made|built|created|designed|are) you|what (are|r) you\b|"
    r"how (do|does) (you|this|the (ai|app|system|bot)) work|"
    r"what can you do|what do you do|how (are|were) you (trained|built)|"
    r"which model|what model|is (this|my data|my info) (confidential|private|"
    r"safe|secure|anonymous)|do you (store|save|keep) (my )?(data|messages)|"
    r"privacy|how (do|does) (the )?screening work)\b", re.I)

# Clearly out-of-scope, non-wellbeing requests.
_OFFTOPIC_PAT = re.compile(
    r"\b(write (me )?(a |some )?(code|program|function|script|essay|poem|"
    r"email|letter|story)|"
    r"python|javascript|\bjava\b|\bsql\b|\bhtml\b|\bcss\b|\bc\+\+|"
    r"debug|compile|algorithm|"
    r"solve (this )?(equation|math|problem|sum)|calculate|"
    r"capital of|who (is|was) the (president|king|queen|ceo|prime minister)|"
    r"weather|temperature (in|today|tomorrow)|recipe|how to cook|"
    r"translate (this|to|into)|stock (price|market)|bitcoin|crypto|"
    r"score of|who won|football|world cup|premier league|"
    r"what time is it|what'?s the date|do my homework|my assignment)\b", re.I)


def classify(text: str) -> str:
    """Return 'personal' | 'meta' | 'offtopic'. Biased toward 'personal'."""
    low = (text or "").strip().lower()
    if not low:
        return "personal"
    if _PERSONAL_PAT.search(low):      # any wellbeing signal wins
        return "personal"
    if _META_PAT.search(low):
        return "meta"
    if _OFFTOPIC_PAT.search(low):
        return "offtopic"
    return "personal"                  # default: keep in scope, never block support


_META_REPLY = (
    "Good question! I'm MindCare AI — a CBT-based wellbeing companion for "
    "students. I listen, and help you work through stress, anxiety, and low "
    "mood using evidence-based techniques, while a real clinician reviews "
    "anything sensitive. Your messages stay private. Whenever you're ready, "
    "just tell me what's been on your mind. 💚"
)

_OFFTOPIC_REPLY = (
    "That's a little outside what I can help with — I'm here as a mental-health "
    "support companion, not a general assistant. But I'm always glad to talk "
    "about how you're feeling or anything that's weighing on you lately. "
    "What's on your mind today? 💚"
)


def reply_for(scope: str) -> str:
    return _META_REPLY if scope == "meta" else _OFFTOPIC_REPLY


# ─────────────────────────────────────────────────────────────────────────────
# Semantic layer — for the AMBIGUOUS remainder only.
#
# classify() (keywords) already nails the obvious cases and every message with a
# wellbeing signal. classify_smart() trusts those, and ONLY asks the LLM about a
# message that keywords left as a *default* "personal" (no signal at all) — the
# novel off-topic phrasings keywords can't enumerate. Best-effort: the LLM is
# fed PII-scrubbed text, and ANY failure/timeout/ambiguity falls back to
# "personal", so a real support message is never redirected and latency is only
# paid on the genuinely-ambiguous minority.
# ─────────────────────────────────────────────────────────────────────────────
_CLASSIFY_SYS = (
    "You route messages for MindCare, a student mental-health chat assistant. "
    "Reply with EXACTLY ONE word — the label:\n"
    "personal = the person shares feelings, stress, mood, or a personal "
    "situation, or wants emotional/coping support. When unsure, choose personal.\n"
    "meta = a question ABOUT MindCare itself (what it is, how it works, privacy, "
    "is it human).\n"
    "offtopic = a request unrelated to wellbeing (coding, math, homework, general "
    "knowledge, weather, translation, trivia, shopping, trip planning, etc.).\n"
    "Answer with one word only: personal, meta, or offtopic."
)


def _llm_classify(text: str):
    """Ask the LLM for a label. Returns 'personal'|'meta'|'offtopic' or None on
    any problem (caller treats None as personal). Never raises."""
    import re as _re
    try:
        from app.services import llm_client, pii_scrubber
        safe = pii_scrubber.scrub(text or "")[:500]
        gen = llm_client.generate(
            [{"role": "system", "content": _CLASSIFY_SYS},
             {"role": "user", "content": safe}],
            n=1, temperature=0.0)
        if not gen or gen.get("degraded"):
            return None
        out = (gen.get("responses") or [""])[0].lower()
        clean = _re.sub(r"[^a-z]", "", out)
        if "offtopic" in clean:
            return "offtopic"
        if "meta" in clean:
            return "meta"
        if "personal" in clean:
            return "personal"
        return None
    except Exception:
        return None


def classify_smart(text: str) -> str:
    """Keyword-first, LLM only for the ambiguous default-personal remainder."""
    kw = classify(text)
    if kw != "personal":
        return kw                                  # keyword caught meta/offtopic
    if _PERSONAL_PAT.search((text or "").lower()):
        return "personal"                          # wellbeing signal — never override
    return _llm_classify(text or "") or "personal"  # ambiguous → ask LLM, default safe
