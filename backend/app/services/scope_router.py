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


# ─────────────────────────────────────────────────────────────────────────────
# Factual self-data intents — questions a user asks about THEIR OWN records or
# the app's catalogue ("who am I", "my appointments", "what lessons are there",
# "which psychologists can I see"). These deserve a DIRECT data answer, not a CBT
# draft + clinician review. Patterns are tight and explicit; the caller also
# guards with the distress check below + the safety regex, so an emotional
# message is never short-circuited.
# ─────────────────────────────────────────────────────────────────────────────
_DATA_PATS = [
    ("profile", re.compile(
        r"\bwho am i\b|what'?s my (name|username|profile|account)|"
        r"what do you know about me\b|my (account|profile) (info|details)", re.I)),
    ("appointments", re.compile(
        r"\b(my )?appointments?\b|my booking|upcoming (appointment|booking|session)|"
        r"when (is|are) my (appointment|session|consultation)|my consultation", re.I)),
    ("psychologists", re.compile(
        r"\bpsychologists?\b|\bcounsell?ors?\b|"
        r"(list|which|available|any|book a?) (psychologist|expert|counsell?or|therapist)|"
        r"\bexperts?\b.*(available|list|book|see)|therapists? available", re.I)),
    ("lessons", re.compile(
        r"\b(what|which|list|available|any) lessons?\b|do you have (any )?lessons|"
        r"\bcourses?\b.*(available|list|have)|lessons? (are there|do you have)", re.I)),
    ("mood", re.compile(
        r"\bmy mood\b|mood (score|history|trend|chart)|how (has )?my mood", re.I)),
    ("screening", re.compile(
        r"\bmy (phq|gad|screening)\b|\bphq[- ]?9\b|\bgad[- ]?7\b|"
        r"screening (results?|scores?|history)|my (results?|scores?) (on|from) (the )?"
        r"(phq|gad|screening)", re.I)),
]


# Distress / risk veto for the DATA intents. Deliberately WIDE: over-vetoing a
# data query is safe (it just falls through to the normal flow), while
# under-vetoing would answer a distressed person with a data dump. Used instead
# of _PERSONAL_PAT here because that pattern flags "my mood"/"my feelings" — the
# exact phrasing of a legitimate data question ("show my mood history").
_DISTRESS_VETO = re.compile(
    r"\b(feel|feeling|felt|emotion\w*|anxious|anxiety|nervous|panic|"
    r"sad|sadness|depress\w*|unhappy|miserable|down|low|hopeless|worthless|"
    r"lonely|alone|isolated|empty|numb|overwhelm\w*|stress\w*|struggl\w*|"
    r"cope|coping|exhaust\w*|tired|drained|burn(ed|t)? ?out|cry\w*|tears?|"
    r"upset|angry|anger|frustrat\w*|scared|afraid|fear|worried|worry|"
    r"overthink\w*|ruminat\w*|spiral\w*|hurt\w*|pain\w*|suffer\w*|"
    r"die|death|suicid\w*|kill|end (it|my life|things)|self[- ]?harm|"
    r"harm myself|give up|hate myself|no point|terrible|awful|worse|rough|"
    r"can'?t (sleep|stop|cope|go on|take|handle))\b", re.I)


def info_intent(text: str):
    """Return a factual-info label to answer DIRECTLY, or None.

    One of: 'profile' | 'appointments' | 'lessons' | 'psychologists' | 'mood' |
    'screening' | 'meta' | 'offtopic'. Returns None when the message carries any
    distress/risk signal (a real support message must never be intercepted) or
    matches no explicit info pattern.
    """
    low = (text or "").strip().lower()
    if not low:
        return None
    # Explicit self-data intents — checked first, vetoed by any distress signal.
    for label, pat in _DATA_PATS:
        if pat.search(low):
            return None if _DISTRESS_VETO.search(low) else label
    # Meta / off-topic — keyword only (safe on L2); never intercept wellbeing.
    if _PERSONAL_PAT.search(low):
        return None
    if _META_PAT.search(low):
        return "meta"
    if _OFFTOPIC_PAT.search(low):
        return "offtopic"
    return None


# Semantic fallback for info_intent: a message that LOOKS like an info/data
# question (a question cue, or "my …") but matched no keyword pattern — the novel
# phrasings keywords can't enumerate. We only spend an LLM call on these.
_INFO_LOOKS = re.compile(
    r"\?|^\s*(who|what|which|when|where|how|can|could|do|does|is|are|list|show|"
    r"tell me|remind me)\b|\bmy \w", re.I)

_INFO_LABELS = {"profile", "appointments", "lessons", "psychologists",
                "mood", "screening", "meta", "offtopic"}

_INFO_SYS = (
    "You route a user message in MindCare, a student mental-health app, to ONE "
    "label. Reply with EXACTLY one word:\n"
    "profile = asks about their own account/identity (who am I, my name).\n"
    "appointments = asks about their own bookings / consultation schedule.\n"
    "lessons = asks what CBT lessons or courses are available.\n"
    "psychologists = asks which experts/counsellors they can see or book.\n"
    "mood = asks about their own recorded mood history or scores.\n"
    "screening = asks about their own PHQ-9 / GAD-7 results.\n"
    "meta = asks ABOUT MindCare itself (how it works, privacy, is it human).\n"
    "offtopic = an unrelated request (coding, math, trivia, weather, translation).\n"
    "none = anything else — ESPECIALLY any feelings, distress, or request for "
    "emotional support. When unsure, answer none.\n"
    "Answer with one word only."
)


def _llm_info(text: str):
    """Ask the LLM for an info label. Returns a label in _INFO_LABELS or None on
    any problem (caller treats None as 'not an info query'). Never raises."""
    import re as _re
    try:
        from app.services import llm_client, pii_scrubber
        safe = pii_scrubber.scrub(text or "")[:500]
        gen = llm_client.generate(
            [{"role": "system", "content": _INFO_SYS},
             {"role": "user", "content": safe}],
            n=1, temperature=0.0)
        if not gen or gen.get("degraded"):
            return None
        out = (gen.get("responses") or [""])[0].lower()
        clean = _re.sub(r"[^a-z]", "", out)
        for lab in _INFO_LABELS:
            if lab in clean:
                return lab
        return None
    except Exception:
        return None


def info_intent_smart(text: str):
    """Keyword-first info detection; for the AMBIGUOUS remainder that still looks
    like an info question (and carries NO distress), ask the LLM. Best-effort —
    PII-scrubbed, and any failure/uncertainty falls back to None, so a real
    support message is never intercepted and latency is paid only on the tail."""
    kw = info_intent(text)
    if kw:
        return kw
    low = (text or "").strip().lower()
    if not low or _DISTRESS_VETO.search(low) or _PERSONAL_PAT.search(low):
        return None
    if not _INFO_LOOKS.search(low):
        return None
    return _llm_info(text)


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
