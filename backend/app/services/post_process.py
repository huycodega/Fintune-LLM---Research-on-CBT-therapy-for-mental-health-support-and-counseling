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
    # The model sometimes emits its own markdown bold — often unbalanced
    # ("…do well this time?**"), which renders as junk AND let a trailing
    # ?** evade the question counters live. The emphasis pass is the only
    # sanctioned bolder, so drafts are stripped of ** entirely.
    resp = resp.replace("**", "").strip()
    # Unwrap a fully-quoted reply ("...") — a generation artifact that reads
    # oddly to users AND let trailing ?" evade the question counters.
    if len(resp) >= 2 and resp[0] == '"' and resp[-1] == '"' \
            and '"' not in resp[1:-1]:
        resp = resp[1:-1].strip()
    return {
        "technique": tech or "(unparsed)",
        "rationale": rat,
        "plan": plan,
        "response": resp,
        "well_formed": well,
    }


_EMPH_SYS = (
    "You add emphasis to a therapy message. Return it EXACTLY as given, but wrap "
    "the 1-2 words or short phrases that carry the most THERAPEUTIC meaning in "
    "markdown **bold**: the key idea, the cognitive pattern (a thought, belief, "
    "assumption, or feeling), the reframe, or the concrete next action. Do NOT "
    "bold reassurance or connective filler such as 'together', 'we can work on "
    "this', \"we'll get through it\", 'I'm here', or 'you're not alone'. Do NOT "
    "change, add, remove, or reorder any other words, and never bold whole "
    "sentences. Output ONLY the message.")


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
        # Guard: the ONLY permitted change is inserting ** markers. Strip them
        # and the result must be the exact original text (whitespace-normalised)
        # — anything else is a rewrite/instruction leak ("Failing the exam: the
        # thought, belief, assumption, or feeling | …") and gets discarded.
        def _norm(s: str) -> str:
            return re.sub(r"\s+", " ", s).strip()
        if "**" in out and _norm(out.replace("**", "")) == _norm(text):
            return out
        return text
    except Exception:
        return text


# Vocatives like ", Ryan." (trailing) AND "Ryan, thank you…" (sentence-
# initial) — the responder borrows a client name from RAG reference
# transcripts, and once it slips into history it self-reinforces. Never-scrub
# words that look like vocatives but aren't names (discourse markers, days…).
_VOCATIVE = re.compile(r",\s+([A-Z][a-z]{1,20})(?=[.!?,;:])")
_VOCATIVE_LEAD = re.compile(r"(^|(?<=[.!?])\s)([A-Z][a-z]{1,20}),\s+(\w)")
# Greeting form: "Hi Faith," / "Hello Ryan." — the name hides behind the
# greeting word, so neither pattern above sees it.
_VOCATIVE_GREET = re.compile(
    r"\b(Hi|Hello|Hey|Dear)\s+([A-Z][a-z]{1,20})(?=[,.!?;:])")
_NOT_NAMES = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december", "ok", "okay",
    "god", "ai",
    # sentence-initial discourse markers that match the leading pattern
    "however", "also", "first", "second", "third", "meanwhile", "remember",
    "overall", "instead", "together", "sometimes", "often", "now", "next",
    "again", "finally", "additionally", "moreover", "furthermore", "still",
    "well", "yes", "no", "alright", "actually", "honestly", "importantly",
    "lastly", "otherwise", "thankfully", "unfortunately", "naturally",
    "clearly", "ideally", "similarly", "likewise", "besides", "anyway",
    "plus", "so", "then", "there", "here", "that", "this", "these", "those",
    "when", "whenever", "while", "once", "perhaps", "maybe", "today",
    "tonight", "tomorrow", "yesterday", "please", "granted", "look",
    "listen", "breathe", "notice", "start", "meantime", "great", "good",
    # greeting-vocative non-names ("Hi There," / "Hello Everyone,")
    "everyone", "friend", "friends", "all", "team", "folks", "again",
    # greeting words themselves — "Hi, it sounds tough." must keep its Hi
    "hi", "hello", "hey", "dear", "thanks", "welcome", "sorry", "sure",
    "right", "absolutely", "understood",
}


def scrub_unknown_names(text: str, allowed: set) -> str:
    """Drop a vocative name the client never gave us ("Ryan, …" / ", Ryan.")
    — names leak in from reference counselling transcripts. `allowed` is a
    lowercase set of names the client actually provided (intake, profile, or
    typed in chat)."""
    def _tail(m):
        name = m.group(1).lower()
        if name in allowed or name in _NOT_NAMES:
            return m.group(0)
        return ""
    out = _VOCATIVE.sub(_tail, text or "")

    def _lead(m):
        name = m.group(2).lower()
        if name in allowed or name in _NOT_NAMES:
            return m.group(0)
        # drop the name, keep the sentence boundary, re-capitalise what follows
        return m.group(1) + m.group(3).upper()
    out = _VOCATIVE_LEAD.sub(_lead, out)

    def _greet(m):
        name = m.group(2).lower()
        if name in allowed or name in _NOT_NAMES:
            return m.group(0)
        return m.group(1)          # "Hi Faith," → "Hi,"
    return _VOCATIVE_GREET.sub(_greet, out)


# Safety check-ins are the ONE kind of question that must survive every
# question-stripping context (listen mode, delivery turns): a well-being probe
# is never a dodge.
_SAFETY_Q = re.compile(
    r"are you (safe|okay|ok|alright)( right now)?|do you feel safe|"
    r"is there (someone|anyone) (with you|around|you can (call|talk to|reach))|"
    r"do you have (someone|anyone|support)|can you (stay|keep yourself) safe",
    re.I)


def strip_questions(text: str) -> str:
    """Listen-only / delivery-turn safety net: drop interrogative sentences so
    the reply stays pure validation or delivered analysis — EXCEPT safety
    check-ins, which always survive. Falls back to the original when too
    little would remain, so we never return an empty or butchered reply."""
    t = (text or "").strip()
    if "?" not in t:
        return t
    parts = re.split(r"(?<=[.!?])\s+", t)
    kept = " ".join(
        p for p in parts
        if not p.strip().rstrip('"\'”’»)]*_`').endswith("?")
        or _SAFETY_Q.search(p)).strip()
    return kept if len(kept) >= 20 else t


# Second-person biography claims ("You've completed coding courses…") — the
# model INVENTS client accomplishments when asked to reflect evidence the
# client never gave (observed live: fabricated Python/JavaScript courses and
# a weather app for a client who said "I haven't achieved any success yet").
_CLAIM_PAT = re.compile(
    r"\byou(?:'ve| have)(?: also)? (?:completed|built|created|made|done|"
    r"achieved|earned|finished|shown|demonstrated|learned|studied|taken|"
    r"passed|developed|gained|mastered|worked on)\b|"
    r"\byour (?:experience|skills?|projects?|courses?|background|training|"
    r"achievements?|accomplishments?|track record)\b", re.I)
_DANGLING_PAT = re.compile(
    r"^\s*(these|those|such) (achievements?|accomplishments?|successes|"
    r"facts|experiences?|skills?|projects?)\b", re.I)
_FACT_WORD = re.compile(r"\b[a-zA-Z][a-zA-Z\-']{3,}\b")
_FACT_STOP = {
    "have", "your", "this", "that", "with", "like", "also", "been", "will",
    "youve", "sound", "sounds", "really", "these", "those", "show", "shows",
    "which", "into", "from", "them", "they", "there", "were", "when", "what",
}


def scrub_unclaimed_facts(text: str, user_texts: list) -> str:
    """Drop sentences that assert client accomplishments/biography whose
    content words never appeared in anything the client actually wrote.
    Reflections of things they DID say survive (their words overlap)."""
    known = set()
    for t in user_texts:
        known |= {w.lower() for w in _FACT_WORD.findall(t or "")}
    if not known:
        return text
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    kept, dropped_prev = [], False
    for p in parts:
        if dropped_prev and _DANGLING_PAT.search(p):
            dropped_prev = True
            continue
        if _CLAIM_PAT.search(p):
            words = {w.lower() for w in _FACT_WORD.findall(p)} - _FACT_STOP
            if words and len(words & known) / len(words) < 0.3:
                dropped_prev = True
                continue
        dropped_prev = False
        kept.append(p)
    out = " ".join(kept).strip()
    return out if len(out) >= 40 else (text or "").strip()


def dedupe_sentences(text: str) -> str:
    """Drop a sentence that near-duplicates an EARLIER sentence in the same
    reply — the model sometimes glues two takes of the same move ("Let's
    start by looking at the evidence… Let's begin by gathering evidence…").
    Only long sentences are compared (short empathic beats repeat licitly),
    and the original wins if too little would remain."""
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    kept, seen = [], []
    for p in parts:
        words = {w.lower() for w in _WORD.findall(p)}
        if (len(words) >= 6
                and any(len(words & s) / len(words | s) >= 0.55
                        for s in seen)):
            continue
        if len(words) >= 6:
            seen.append(words)
        kept.append(p)
    out = " ".join(kept).strip()
    return out if len(out) >= 40 else (text or "").strip()


# Rewrite pass for delivery turns ("just lay it out for me") whose best draft
# STILL dodges with questions — one bounded revision call. Strictly guarded:
# the result must contain zero question marks and a sane length, and the
# caller re-runs preflight; any failure keeps the original draft.
_DELIVER_SYS = (
    "You revise a therapy reply. The client explicitly asked for a direct "
    "analysis with NO more questions. Rewrite the reply so it: keeps the warm, "
    "first-person tone; NEVER uses the '?' character; asks the client for "
    "NOTHING; directly delivers the concrete breakdown the client asked for "
    "(e.g. evidence for and against the stated thought), using ONLY facts "
    "already present in the client's message; ends with a supportive "
    "statement. Output ONLY the revised reply, under 150 words.")


def deliver_rewrite(text: str, client_msg: str) -> str:
    """Return a question-free revision of `text`, or "" when the model is
    unavailable or the revision fails any guard (caller keeps the original).
    A revision that still slips in a question gets its question sentences
    stripped before the guard, so a mostly-good rewrite is salvaged."""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        from app.services import llm_client
        gen = llm_client.generate(
            [{"role": "system", "content": _DELIVER_SYS},
             {"role": "user",
              "content": f"[CLIENT'S REQUEST]\n{client_msg}\n\n"
                         f"[REPLY TO REVISE]\n{text}"}],
            n=1, temperature=0.2)
        if not gen or gen.get("degraded") or gen.get("mode") == "mock":
            return ""
        out = (gen.get("responses") or [""])[0].strip()
        if "?" in out:                       # salvage: drop question sentences
            out = strip_questions(out)
        if out and "?" not in out and 40 <= len(out) <= 1200:
            return out
        return ""
    except Exception:
        return ""


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
