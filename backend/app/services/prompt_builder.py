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

Model: Huysun29/cbt-llama-3.1-8b (Llama-3.1-8B Instruct + CBT LoRA)
Safety gate: Huysun29/cbt-qwen-7b (run prior to this builder)
"""
import hashlib
from typing import Dict, List, Optional


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
    "Technique: <one specific CBT technique, e.g. 'Socratic questioning'>\n"
    "Rationale: <1-2 sentences: clinical justification for this technique>\n"
    "Plan: <2-3 concrete therapeutic micro-steps for this session>\n"
    "Response: <warm, empathetic, clinically grounded reply to the client "
    "— avoid jargon, speak directly to their experience>\n\n"

    "Clinical guidelines:\n"
    "  • Ground every response in the retrieved CBT knowledge and case examples\n"
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
    lines = ["[RETRIEVED CONTEXT — CBT knowledge + prior dialogues]"]
    for i, it in enumerate(items, 1):
        src = it.get("source_collection", "?")
        text = it.get("text", "")[:600]
        lines.append(f"({i}) [{src}] {text}")
    return "\n".join(lines)


def _format_analysis(analysis: Optional[Dict]) -> str:
    if not analysis:
        return ""
    return (
        "[PSYCHOLOGICAL ANALYSIS]\n"
        f"- Emotion: {analysis.get('emotion','')}\n"
        f"- Severity: {analysis.get('severity','')}\n"
        f"- Cognitive distortions: {analysis.get('cognitive_distortions','')}\n"
        f"- Technique hint: {analysis.get('technique_hint','')}"
    )


def _format_session_ctx(ctx: Optional[Dict]) -> str:
    if not ctx:
        return ""
    return (
        "[SESSION CONTEXT]\n"
        f"- Prior session count: {ctx.get('prior_count', 0)}\n"
        f"- Last technique used: {ctx.get('last_technique', '—')}\n"
        f"- Recent summary: {ctx.get('summary', '—')}"
    )


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
