"""
Prompt builder v4.

Assembles the LLM input from:
  - SYSTEM_PROMPT (CBT clinician identity, 4-field contract, English)
  - intake context (all 6 sections, parsed)
  - session context (prior session summaries if any)
  - psychological analysis (emotion / distortion / technique hint)
  - retrieved context (top-k after hybrid rerank — rag-data-fixed.ipynb)
  - current user message (PII-scrubbed)

PII scrubber is applied to any free-text PHI before assembly. Final
text is hashed (SHA-256) for audit trail (sessions.prompt_hash).

Model: Huysun29/cbt-qwen2.5-7b-v2 (Qwen2.5-7B full-merged CBT model)
Safety gate: Huysun29/cbt-qwen2.5-7b-v2 (run prior to this builder)
"""
import hashlib
import re
from typing import Dict, List, Optional

from app.core.config import settings
from app.services.preflight import CANONICAL_TECHNIQUES, canonical_technique

_TECH_LIST = ", ".join(CANONICAL_TECHNIQUES)


# ─────────────────────────────────────────────────────────────────────────────
# Technique scaffolding — the concrete, clinically-conventional micro-steps for
# each CBT technique. The responder scores well on empathy but weakly on
# TECHNIQUE CORRECTNESS (eval tech-correct ≈ 1.8/5): it names a technique but
# doesn't actually execute its steps. Injecting the canonical step sequence for
# the chosen technique gives the model a recipe to follow, so the reply applies
# the method properly. Keyed by canonical technique name (preflight set).
# ─────────────────────────────────────────────────────────────────────────────
TECHNIQUE_STEPS = {
    "Cognitive restructuring": [
        "Pinpoint the specific automatic/hot thought",
        "Name the cognitive distortion in it",
        "Weigh the evidence for and against the thought",
        "Build a fairer, balanced alternative thought",
        "Agree one small step to practise the new thought",
    ],
    "Thought record": [
        "Name the situation and the feeling (rate 0–100)",
        "Capture the automatic thought",
        "List evidence for and against it",
        "Write a balanced thought and re-rate the feeling",
    ],
    "Decatastrophizing": [
        "Name the feared worst case",
        "Estimate how likely it realistically is",
        "Identify the most likely outcome instead",
        "Plan how you'd cope even if the worst happened",
    ],
    "Behavioral activation": [
        "Validate low motivation and pick one valued activity",
        "Break it into a tiny first step",
        "Schedule exactly when to do it",
        "Plan a brief review of how it felt",
    ],
    "Problem-solving": [
        "Define the problem concretely",
        "Brainstorm several options without judging",
        "Weigh pros and cons of each",
        "Pick one and plan the first action",
    ],
    "Socratic questioning": [
        "Ask what the evidence for the belief is",
        "Explore alternative explanations",
        "Examine the real consequences if it were true",
        "Guide the client to a more balanced conclusion",
    ],
    "Cognitive reframing": [
        "Reflect the current interpretation back",
        "Offer a fairer, more flexible way to see it",
        "Check how the reframe changes the feeling",
    ],
    "Reality testing": [
        "State the belief as a testable prediction",
        "Gather the evidence for and against it",
        "Compare belief to the evidence and revise",
    ],
    "Psychoeducation": [
        "Normalise the experience",
        "Explain the relevant CBT concept simply",
        "Link it back to what the client described",
    ],
    "Relaxation training": [
        "Introduce one technique (e.g. paced breathing)",
        "Walk through it step by step, concretely",
        "Suggest when to practise it",
    ],
    "Mindfulness": [
        "Invite attention to the present moment",
        "Guide noticing thoughts/feelings without judging",
        "Suggest a short daily practice",
    ],
    "Worry postponement": [
        "Acknowledge the worry without engaging it now",
        "Set a fixed daily 'worry time'",
        "Refocus on the present until then",
    ],
    "Self-compassion": [
        "Notice the self-critical voice",
        "Reframe it as you'd speak to a friend",
        "Offer one kind, realistic statement",
    ],
    "Pros and cons analysis": [
        "List the pros of the option/belief",
        "List the cons",
        "Weigh them and draw a balanced conclusion",
    ],
    "Graded exposure": [
        "Build a small ladder of feared steps",
        "Start with the easiest manageable step",
        "Plan to stay with it until anxiety eases, then step up",
    ],
    "Behavioral experiment": [
        "State the belief as a prediction to test",
        "Design a small real-world test",
        "Plan what to observe and how to review it",
    ],
    "Activity scheduling": [
        "Identify valued/pleasant activities",
        "Schedule them into specific time slots",
        "Plan to rate mood before and after",
    ],
    "Grounding techniques": [
        "Bring attention to the body and surroundings",
        "Guide a concrete exercise (e.g. 5-4-3-2-1 senses)",
        "Check in on how grounded the client feels",
    ],
}


def _technique_scaffold(technique_hint: Optional[str]) -> str:
    """Render the canonical micro-steps for the hinted technique, or '' when the
    technique isn't recognised / has no scaffold (then the model just gets the
    hint as before — no behaviour change)."""
    canon = canonical_technique(technique_hint or "")
    steps = TECHNIQUE_STEPS.get(canon or "")
    if not steps:
        return ""
    numbered = "; ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))
    return (f"\n- How to APPLY {canon} correctly (work these steps in your "
            f"Plan/Response, adapt wording to the client): {numbered}")


SYSTEM_PROMPT = (
    "You are a licensed CBT clinician — combining the expertise of a "
    "clinical psychologist with the warmth of a skilled therapist. "
    "You are both the primary CBT assistant AND the clinician who guides "
    "the therapeutic process.\n\n"

    "Your clinical responsibilities:\n"
    "  • Identify cognitive distortions and maladaptive patterns accurately\n"
    "  • Select evidence-based CBT techniques matched to presenting severity\n"
    "  • Maintain therapeutic alliance through empathy and validation\n"
    "  • Document clinical reasoning clearly for supervisor review\n"
    "  • Recognize crisis signals and escalate appropriately\n\n"

    "You serve two audiences simultaneously in ONE structured response:\n"
    "  1. CLINICIAN VIEW — Technique, Rationale, Plan: supports clinical "
    "oversight, documentation, and human-in-the-loop review.\n"
    "  2. CLIENT VIEW — Response: the empathetic, plain-language reply "
    "delivered directly to the client.\n\n"

    "Output EXACTLY these four labeled fields in order:\n\n"
    "Technique: <choose EXACTLY ONE from this canonical list, written "
    "verbatim — do NOT invent a new technique name>\n"
    f"   Allowed techniques: {_TECH_LIST}\n"
    "Rationale: <1-2 sentences: clinical justification for this technique>\n"
    "Plan: <2-3 concrete therapeutic micro-steps for this session>\n"
    "Response: <warm, empathetic, clinically grounded reply to the client "
    "— avoid jargon, speak directly to their experience. Write ONLY your "
    "single reply. Do NOT continue the conversation, simulate the client's "
    "next message, or write any further turns.>\n\n"

    "FAITHFULNESS — do NOT fabricate (most important rule):\n"
    "  • NEVER invent, assume, or embellish facts about the client. Do not "
    "mention symptoms, behaviours, events, diagnoses, relationships, habits, "
    "or feelings the client did not explicitly state in [CURRENT CLIENT "
    "MESSAGE], [CLIENT INTAKE], or [CONVERSATION SO FAR].\n"
    "  • Every factual claim about the client must be traceable to their own "
    "words. When you reflect their experience, paraphrase what they ACTUALLY "
    "said — never add new specifics (e.g. do not name a symptom or cause they "
    "didn't mention).\n"
    "  • [REFERENCE MATERIAL] is general clinical knowledge ONLY. Never state "
    "or imply it describes this client.\n"
    "  • Do not exaggerate severity or attribute intentions/thoughts the "
    "client did not express.\n"
    "  • Do NOT claim you previously discussed or worked on something with the "
    "client (no 'our talks about…', 'as we discussed', 'last time we…') unless "
    "it actually appears in [CONVERSATION SO FAR]. [USER MEMORY] is background "
    "knowledge ABOUT the client, NOT a transcript of past conversations — never "
    "narrate it as a shared therapeutic history.\n"
    "  • If a key fact is genuinely missing AND you cannot proceed without it, "
    "ask ONE gentle clarifying question. But do NOT use clarifying questions to "
    "stall: if the client has described their concern OR asked you to help work "
    "on a thought or feeling, DELIVER a concrete CBT technique now instead of "
    "asking another question.\n\n"

    "CONTINUITY — build on the conversation, never restart it:\n"
    "  • Read [CONVERSATION SO FAR] and [Last technique used]. If you already "
    "began a technique (e.g. a thought record), CONTINUE to the NEXT step — do "
    "NOT re-introduce it, re-explain it, or repeat a step the client already "
    "did.\n"
    "  • If the client already gave the evidence, answers, or examples you "
    "asked for, USE them and move forward (e.g. toward a balanced/alternative "
    "thought, or a concrete action step) — never ask them to redo a step.\n"
    "  • NEVER claim the client DID something unless they explicitly said so "
    "in the conversation. YOU proposing an exercise earlier (\"let's write "
    "those down\") does NOT mean they did it — never say \"the thought record "
    "you filled out\" or \"what you wrote\" unless the client reported doing "
    "it. If unsure, invite: \"if you'd like, we can fill one out now\".\n"
    "  • NEVER imply a prior exercise or discussion happened unless it is in "
    "the conversation history — no \"again\", \"as we discussed\", \"let's "
    "continue the thought record\" on a first pass. Name a technique ONLY "
    "when you actually do it in THIS reply, step by step — naming it and "
    "then asking another question instead is a failure.\n"
    "  • NEVER repeat or closely paraphrase your own previous reply (see the "
    "conversation history). Every turn must ADD something new: the next step "
    "of the exercise, a new angle, or a response to what the client just "
    "added. If the client answered your question, USE the answer.\n"
    "  • Quotation marks are ONLY for the client's EXACT words, or for a "
    "balanced thought you clearly offer as a suggestion. NEVER present your "
    "paraphrase as something the client said — no invented quotes.\n"
    "  • NEVER ask the client to share something they already told you. If "
    "they named a thought, feeling, or belief (e.g. \"I'm never enough\"), "
    "quote it back and work on THAT directly — asking \"what thoughts come "
    "up?\" after they just told you is a failure. Same when the client points "
    "out you missed something (\"that's what I just said\"): briefly own it, "
    "then use what they gave you.\n"
    "  • Every turn must ADVANCE the therapeutic work, not reset it. Track where "
    "you are in the technique and take the logical next step.\n\n"

    "Clinical guidelines:\n"
    "  • Use retrieved CBT knowledge as background — ALWAYS respond to what the client actually said in [CURRENT CLIENT MESSAGE], never to retrieved examples\n"
    "  • Address the client by name ONLY if that name appears in [CLIENT "
    "INTAKE] or they told you themselves. NEVER borrow a name from reference "
    "material — if you don't know their name, just don't use one\n"
    "  • Match technique to the client's distortion type and severity level\n"
    "  • For L2 severity (moderate): prioritise validation before challenging\n"
    "  • If any crisis signals appear: set Technique to CRISIS_REFERRAL and "
    "recommend immediate escalation — do NOT provide standard CBT\n"
    "  • Keep Response under 200 words — concise, human, therapeutic"
)


# ── Lean prompt for a frontier brain (LLM_PROVIDER=claude) ────────────────────
# The big FAITHFULNESS/CONTINUITY rule-blocks above exist to tame the 7B's
# habits (re-asking, fabricated continuity, self-repeat, invented quotes,
# borrowed names). A frontier model does none of that, and those rules only
# over-constrain it into thin, validation-only replies. This keeps ONLY what
# is genuinely model-independent — the 4-field contract, the safety floor,
# and a one-line faithfulness/name guard — and otherwise TRUSTS the model to
# be a warm, engaged therapist. The runtime choke-point nets still run as a
# backstop for both providers.
SYSTEM_PROMPT_CLAUDE = (
    "You are a warm, highly skilled CBT therapist supporting a client in a "
    "private mental-health chat. Combine real clinical expertise with genuine "
    "human warmth.\n\n"

    "Output EXACTLY these four labeled fields, in order:\n"
    "Technique: <choose EXACTLY ONE, verbatim, from this list — do not invent "
    f"one>\n   Allowed techniques: {_TECH_LIST}\n"
    "Rationale: <1-2 sentences of clinical reasoning>\n"
    "Plan: <2-3 concrete micro-steps for this session>\n"
    "Response: <your reply to the client — this is the ONLY part they see>\n\n"

    "Every Response has TWO parts, both required:\n"
    "  (1) VALIDATE — warmly reflect how they feel, in their own terms.\n"
    "  (2) MOVE FORWARD — in the SAME reply, take one real therapeutic step: "
    "reframe a thought, offer a small doable action, ask one caring question, "
    "or give realistic hope. A reply that only validates and stops is "
    "INCOMPLETE and feels dismissive — always do (2) as well. (Not permission "
    "to interrogate: at most one question.)\n\n"

    "Also in the Response:\n"
    "  • Use ONLY facts the client actually gave you. Never invent symptoms, "
    "events, a name, or a shared past. Retrieved knowledge is background — "
    "never imply it describes this client.\n"
    "  • Use the client's name only if they gave it; otherwise use none.\n"
    "  • Plain language, no jargon, under ~180 words. Write only this single "
    "reply — do not simulate the client's next turn.\n\n"

    "SAFETY (non-negotiable): no diagnosis, no medication advice, no self-harm "
    "instructions. If any crisis or self-harm signal appears, set Technique to "
    "CRISIS_REFERRAL and gently steer them to immediate professional/crisis "
    "support instead of standard CBT."
)


def _format_intake(intake: Optional[Dict]) -> str:
    if not intake:
        return ""
    dem = intake.get("demographics") or {}
    funct = intake.get("functioning") or {}
    past = intake.get("past_history") or {}
    parts = [
        "[CLIENT INTAKE — 6 sections]",
        f"§1 Demographics: {dem}",
        f"§2 Presenting problem: {intake.get('presenting','')}",
        f"§3 Reason for counseling: {intake.get('reason','')}",
        f"§4 Past history: {past.get('raw','') or past}",
        f"§5 Functioning: {funct}",
        f"§6 Social support: {intake.get('social_support','')}",
    ]
    return "\n".join(parts)


# Raw-scrape cruft that slipped into the KB (site navigation, GUID sitemaps).
# Feeding it to the 7B invites verbatim echo — drop such chunks entirely.
_JUNK_CHUNK = re.compile(
    r"\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-|"
    r"Toggle navigation|Site map|Skip to (main )?content|"
    r"Accessibility\s+Contact Us|Staff Profiles|cookie polic", re.I)


def _format_retrieved(items: List[Dict]) -> str:
    if not items:
        return ""
    lines = [
        "[REFERENCE MATERIAL — CBT knowledge base, NOT the client's words]",
        "NOTE: Use the passages below as background clinical knowledge only.",
        "Do NOT treat them as descriptions of this client's situation.",
    ]
    n = 0
    for it in items:
        text = it.get("text", "")[:600]
        if _JUNK_CHUNK.search(text):
            continue                    # navigation/sitemap scrape — useless
        n += 1
        src = it.get("source_collection", "?")
        lines.append(f"({n}) [{src}] {text}")
    if n == 0:
        return ""
    return "\n".join(lines)


def _format_analysis(analysis: Optional[Dict]) -> str:
    if not analysis:
        return ""
    base = (
        "[PSYCHOLOGICAL ANALYSIS]\n"
        f"- Emotion: {analysis.get('emotion','')}\n"
        f"- Severity: {analysis.get('severity','')}\n"
        f"- Cognitive distortions: {analysis.get('cognitive_distortions','')}\n"
        f"- Technique hint: {analysis.get('technique_hint','')}"
    )
    base += _technique_scaffold(analysis.get("technique_hint"))
    materials = (analysis.get("suggested_materials") or "").strip()
    if materials:
        base += (
            "\n- Suggested materials (REAL items from the library — you MAY "
            "offer one by its exact title if it fits; do NOT invent others): "
            f"{materials}")
    plan = (analysis.get("session_plan") or "").strip()
    if plan:
        base += ("\n- Session plan — advance THIS step in your Plan/Response, "
                 "do not restart earlier steps: " + plan)
    if analysis.get("delivery_request"):
        base += (
            "\n- THE CLIENT EXPLICITLY ASKED YOU TO DELIVER the analysis "
            "('walk me through it', 'how likely', 'just tell me'). Do NOT ask "
            "ANY question this turn — no clarifying, no 'can you walk me "
            "through', no 'what makes you believe'. Give the concrete "
            "breakdown/steps directly, using what they already told you, and "
            "END WITH A STATEMENT.")
    if analysis.get("exercise_continue"):
        base += (
            "\n- THE CLIENT JUST ANSWERED your exercise question — their "
            "evidence is already in their message. Do NOT ask them to gather, "
            "list, or think of evidence again ('let's start by', 'can you "
            "think of any past experiences' are FORBIDDEN this turn). "
            "Instead: (1) reflect the strongest point they gave on EACH side "
            "in their own words; (2) offer ONE balanced alternative thought "
            "built from that evidence; (3) give one small concrete step for "
            "before the event. END WITH A STATEMENT. If the client says they "
            "have NO evidence on a side (first attempt, no wins yet), do NOT "
            "invent any for them — normalize it instead ('a first attempt "
            "means no record of failure either') and reframe the goal toward "
            "learning and completion.")
    facts = (analysis.get("user_facts") or "").strip()
    if facts:
        base += (
            "\n- The client asked about their OWN data; these are their REAL "
            "records from the system. Answer using ONLY these — do not invent "
            "or alter any dates, names, or scores, and do not say you cannot "
            "access them:\n" + facts)
    return base


def _format_memory(mem: Optional[Dict]) -> str:
    """Durable per-user memory the assistant should carry across threads."""
    if not mem:
        return ""
    themes = ", ".join(mem.get("recurring_themes", []) or []) or "—"
    techs = ", ".join(mem.get("techniques_used", []) or []) or "—"
    return (
        "[USER MEMORY — background notes about this client, NOT a transcript "
        "of past talks. Do not reference these as things you discussed "
        "together unless they also appear in CONVERSATION SO FAR]\n"
        f"- Total prior turns: {mem.get('turn_count', 0)}\n"
        f"- Recurring themes: {themes}\n"
        f"- Techniques tried before: {techs}\n"
        f"- Gist: {mem.get('summary', '—') or '—'}"
    )


def _format_history(history: Optional[List[Dict]]) -> str:
    """The current conversation thread so the model has multi-turn context."""
    if not history:
        return ""
    lines = ["[CONVERSATION SO FAR — this thread, oldest→newest]"]
    for turn in history:
        u = (turn.get("user") or "").strip()
        a = (turn.get("reply") or "").strip()
        if u:
            lines.append(f"Client: {u}")
        if a:
            lines.append(f"Assistant: {a}")
    return "\n".join(lines)


def _format_session_ctx(ctx: Optional[Dict]) -> str:
    if not ctx:
        return ""
    base = (
        "[SESSION CONTEXT]\n"
        f"- Prior session count: {ctx.get('prior_count', 0)}\n"
        f"- Last technique used: {ctx.get('last_technique', '—')}\n"
        f"- Recent summary: {ctx.get('summary', '—')}"
    )
    parts = [base,
             _format_style_prefs(ctx.get("style_prefs")),
             _format_memory(ctx.get("memory")),
             _format_history(ctx.get("history"))]
    return "\n\n".join(p for p in parts if p)


_STYLE_LABEL = {
    "brief": "keep the reply SHORT (2-4 sentences, no long lists)",
    "direct": "be direct and get to the point — minimal preamble",
    "no_questions": "do NOT end with a question; offer support/statements "
                    "instead (unless safety requires a check)",
    "just_listen": "the client asked to simply be HEARD — shift to a warmer, "
                   "softer, unhurried tone and keep it SHORT (1-3 sentences). "
                   "Only reflect and gently validate what they feel, mirroring "
                   "their own words; do NOT give advice, exercises, techniques, "
                   "reframes, or analysis, and do NOT end with a question. "
                   "SAFETY OVERRIDES THIS: if their distress is clearly worsening "
                   "or any risk, hopelessness, or self-harm appears, break the "
                   "listen-only stance — gently check in and offer support",
}


def _format_style_prefs(prefs) -> str:
    """Client-stated style preferences to honour this turn."""
    items = [_STYLE_LABEL[p] for p in (prefs or []) if p in _STYLE_LABEL]
    if not items:
        return ""
    return ("[CLIENT STYLE PREFERENCE — the client asked you to: "
            + "; ".join(items) + ". Honour this.]")


# Thoughts the client stated verbatim (they quote them: "I'm never enough").
# Deterministically extracted and pinned into the prompt so the responder can
# never claim it doesn't know them — the 7B otherwise keeps re-asking "what
# thoughts come up?" even after the client answered.
_QUOTED_THOUGHT = re.compile(r'["“]([^"”]{3,80})["”]')
# Unquoted but explicit first-person statements count too — "I'm afraid I
# won't make it into the top tier" IS the named thought, quotes or not (the
# quoted-only rule let a six-turn re-ask loop through in live testing).
_STATED_THOUGHT = re.compile(
    r"\bi\s*(?:'m|am|’m|'ve| have)?\s*(?:really\s+|so\s+|just\s+|quite\s+|"
    r"very\s+|started\s+|been\s+)?"
    r"(?:afraid|scared|worried|terrified|stressed|anxious|convinced|certain|"
    r"sure|believing|doubting|questioning)\s+"
    r"(?:that\s+|because\s+|about\s+)?([^.?!;\n]{5,90})"
    r"|\bi(?:'m| am)?\s*(?:keep\s+)?thinking\s+(?:that\s+)?([^.?!;\n]{5,90})"
    r"|\bi believe\s+(?:that\s+)?((?!in you\b)[^.?!;\n]{8,90})"
    r"|\bmy (?:biggest |main )?(?:fear|worry|concern) is\s+(?:that\s+)?"
    r"([^.?!;\n]{5,90})"
    r"|\bmy mind keeps? (?:saying|telling me)\s+(?:that\s+)?([^.?!;\n]{5,90})"
    r"|\b(?:part of me|something in me) (?:is |keeps )?"
    r"(?:convinced|certain|sure|saying|believing)\s*(?:that\s+)?"
    r"([^.?!;\n]{5,90})"
    r"|\bmade me (?:certain|sure|believe|think|feel like)\s*(?:that\s+)?"
    r"([^.?!;\n]{5,90})"
    r"|\bi feel like\s+([^.?!;\n]{5,90})", re.I)


def _format_named_thoughts(session_ctx, user_input: str) -> str:
    texts = []
    for h in (session_ctx or {}).get("history") or []:
        texts.append(h.get("user") or "")
    texts.append(user_input or "")
    seen, found = set(), []
    for t in texts:
        for m in _QUOTED_THOUGHT.findall(t):
            k = m.strip().lower()
            if k and k not in seen:
                seen.add(k)
                found.append(m.strip())
        for groups in _STATED_THOUGHT.findall(t):
            m = next((g for g in groups if g), "")
            # drop leading conjunction noise ("again and I can't…")
            m = re.sub(r"^(?:again|and|but|then|,|\s)+", "", m, flags=re.I)
            k = m.strip().lower()
            if len(k) >= 5 and k not in seen:
                seen.add(k)
                found.append(m.strip())
    if not found:
        return ""
    # Newest FIRST — the client updates their thought as the conversation
    # deepens ("won't win a prize" → "everyone will be disappointed in me"),
    # and the model was observed clinging to the oldest pinned one.
    newest_first = list(reversed(found[-4:]))
    return ("[CLIENT'S OWN NAMED THOUGHTS — they already told you these. "
            "NEVER ask what their thoughts are. Work on the FIRST one below "
            "(their most recent); only revisit an older one if the client "
            "brings it back. Never re-quote a thought you already worked on "
            "in a previous reply — move it forward instead.]\n"
            + "\n".join(f'- "{t}"' for t in newest_first))


def build_messages(user_input_scrubbed: str,
                    intake: Optional[Dict] = None,
                    analysis: Optional[Dict] = None,
                    session_ctx: Optional[Dict] = None,
                    retrieved: Optional[List[Dict]] = None) -> List[Dict]:
    claude = getattr(settings, "llm_provider", "local") == "claude"
    if claude:
        # Frontier brain: give it the context and a short task, then trust it.
        # No EMPHASIS/CONTINUITY nagging — those tamed the 7B and only flatten
        # a capable model. (Bolding still comes from the separate emphasis pass.)
        task = ("[CLINICAL TASK]\n"
                "Reply as the CBT therapist in the four-field format. Validate "
                "warmly, then move the work forward with a real CBT step. Use "
                "only what the client actually told you.")
    else:
        task = ("[CLINICAL TASK]\n"
                "As the CBT clinician:\n"
                "1. Select the best-fit CBT technique based on distortion type and severity.\n"
                "2. State your clinical rationale in 1-2 sentences.\n"
                "3. Define 2-3 concrete micro-steps for this session.\n"
                "4. Write the empathetic client-facing response (≤200 words).\n"
                "EMPHASIS: In the Response, use markdown **bold** on the 1-2 words or "
                "short phrases that carry the MOST meaning of YOUR reply — the insight, "
                "the shift, or the next action — so they naturally stand out. Pick them "
                "from the sentence itself; never bold filler or whole sentences. "
                "Example: \"That thought — 'I'll definitely fail' — is a **prediction**, "
                "not a fact. Let's look at the **evidence** for and against it.\"\n"
                "CONTINUITY: Read CONVERSATION SO FAR. Do NOT repeat a question you "
                "already asked or ask the client to 'share more' again if they just "
                "did — build on what they already told you and ADVANCE to the next "
                "step of the technique (e.g. move from naming the thought to examining "
                "the evidence, then to a reframe or a concrete action).")
    blocks = [
        _format_intake(intake),
        _format_session_ctx(session_ctx),
        _format_analysis(analysis),
        _format_retrieved(retrieved or []),
        _format_named_thoughts(session_ctx, user_input_scrubbed),
        "[CURRENT CLIENT MESSAGE]\n" + user_input_scrubbed,
        task,
    ]
    user_text = "\n\n".join(b for b in blocks if b).strip()
    return [
        {"role": "system",
         "content": SYSTEM_PROMPT_CLAUDE if claude else SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]


def prompt_hash(messages: List[Dict]) -> str:
    """Deterministic SHA-256 of the full prompt for audit/repro."""
    joined = "\n".join(f"{m['role']}:{m['content']}" for m in messages)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
