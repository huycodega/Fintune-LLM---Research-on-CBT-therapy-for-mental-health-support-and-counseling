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
from typing import Dict, List, Optional

from app.services.preflight import CANONICAL_TECHNIQUES

_TECH_LIST = ", ".join(CANONICAL_TECHNIQUES)


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
    "  • Every turn must ADVANCE the therapeutic work, not reset it. Track where "
    "you are in the technique and take the logical next step.\n\n"

    "Clinical guidelines:\n"
    "  • Use retrieved CBT knowledge as background — ALWAYS respond to what the client actually said in [CURRENT CLIENT MESSAGE], never to retrieved examples\n"
    "  • Match technique to the client's distortion type and severity level\n"
    "  • For L2 severity (moderate): prioritise validation before challenging\n"
    "  • If any crisis signals appear: set Technique to CRISIS_REFERRAL and "
    "recommend immediate escalation — do NOT provide standard CBT\n"
    "  • Keep Response under 200 words — concise, human, therapeutic"
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


def _format_retrieved(items: List[Dict]) -> str:
    if not items:
        return ""
    lines = [
        "[REFERENCE MATERIAL — CBT knowledge base, NOT the client's words]",
        "NOTE: Use the passages below as background clinical knowledge only.",
        "Do NOT treat them as descriptions of this client's situation.",
    ]
    for i, it in enumerate(items, 1):
        src = it.get("source_collection", "?")
        text = it.get("text", "")[:600]
        lines.append(f"({i}) [{src}] {text}")
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
    materials = (analysis.get("suggested_materials") or "").strip()
    if materials:
        base += (
            "\n- Suggested materials (REAL items from the library — you MAY "
            "offer one by its exact title if it fits; do NOT invent others): "
            f"{materials}")
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
             _format_memory(ctx.get("memory")),
             _format_history(ctx.get("history"))]
    return "\n\n".join(p for p in parts if p)


def build_messages(user_input_scrubbed: str,
                    intake: Optional[Dict] = None,
                    analysis: Optional[Dict] = None,
                    session_ctx: Optional[Dict] = None,
                    retrieved: Optional[List[Dict]] = None) -> List[Dict]:
    blocks = [
        _format_intake(intake),
        _format_session_ctx(session_ctx),
        _format_analysis(analysis),
        _format_retrieved(retrieved or []),
        "[CURRENT CLIENT MESSAGE]\n" + user_input_scrubbed,
        "[CLINICAL TASK]\n"
        "As the CBT clinician:\n"
        "1. Select the best-fit CBT technique based on distortion type and severity.\n"
        "2. State your clinical rationale in 1-2 sentences.\n"
        "3. Define 2-3 concrete micro-steps for this session.\n"
        "4. Write the empathetic client-facing response (≤200 words).",
    ]
    user_text = "\n\n".join(b for b in blocks if b).strip()
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]


def prompt_hash(messages: List[Dict]) -> str:
    """Deterministic SHA-256 of the full prompt for audit/repro."""
    joined = "\n".join(f"{m['role']}:{m['content']}" for m in messages)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
