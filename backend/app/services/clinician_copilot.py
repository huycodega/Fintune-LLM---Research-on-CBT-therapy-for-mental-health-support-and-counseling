"""
Clinician Copilot — an AI assistant that helps the human clinician REVIEW a
session faster. It never decides; the clinician still calls /api/admin/review.

All functions are best-effort: when the orchestrator (Modal) is unavailable
they return a short "copilot unavailable" string so the review UI degrades
gracefully instead of erroring.

Backed by the same cbt-qwen2.5-7b-v2 orchestrator as the agent loop
(via agent_client.complete) — no extra model, no fine-tune.

Actions exposed through /api/admin/copilot/{sid}:
  summarize → concise case summary
  suggest   → recommended approve/edit/reject + rationale (advisory only)
  explain   → plain-language explanation of triage + grounding/hallucination
  soap      → AI-drafted SOAP note (Subjective/Objective/Assessment/Plan)
  ask       → free-form question about the case
"""
import logging
from typing import Dict, List, Optional

from app.core.crypto import decrypt_str
from app.services import agent_client


log = logging.getLogger(__name__)

_UNAVAILABLE = ("Copilot is unavailable (agent orchestrator offline). "
                "Please review manually.")

_SYSTEM = (
    "You are a clinical supervision copilot assisting a licensed mental-health "
    "clinician who is reviewing an AI-drafted CBT response before it reaches a "
    "student client. Be concise, clinically precise, and BALANCED — caution does "
    "NOT mean defaulting to rejection. You advise; the clinician decides. Never "
    "invent facts not present in the case data.\n"
    "How to read the metrics: the draft has ALREADY passed the deterministic "
    "safety gate, so it is not a crisis case. preflight_pass=True means the reply "
    "is well-formed and rule-compliant. A LOW grounding score is EXPECTED and "
    "normal for warm, empathic CBT replies (they make few factual claims) — it is "
    "NOT by itself a reason to reject. Judge mainly on safety, empathy, and "
    "clinical appropriateness of the actual text.")


# ─────────────────────────────────────────────────────────────────────────────
# Case serialization (shared context block)
# ─────────────────────────────────────────────────────────────────────────────
def _draft_lines(drafts: List[Dict]) -> str:
    if not drafts:
        return "(no AI drafts — L1 high-risk, no automated draft generated)"
    out = []
    for d in drafts:
        out.append(
            f"- Draft #{d.get('idx', '?')}: technique={d.get('technique')}, "
            f"grounding={d.get('hallucination_score')}, "
            f"preflight_pass={d.get('preflight_pass')}, "
            f"well_formed={d.get('well_formed')}\n"
            f"  response: {(d.get('response') or '')[:400]}")
    return "\n".join(out)


def _case_context(session, drafts: List[Dict],
                  intake) -> str:
    user_text = decrypt_str(session.user_input_enc)
    analysis = session.analysis or {}
    presenting = ""
    if intake is not None and getattr(intake, "presenting", None):
        try:
            presenting = decrypt_str(intake.presenting)
        except Exception:
            presenting = ""
    parts = [
        "[CASE DATA]",
        f"Triage level: {session.triage_level} (severity={session.severity}, "
        f"confidence={session.confidence})",
        f"Triage reason: {session.triage_reason}",
        f"Detected emotion: {analysis.get('emotion', '—')}",
        f"Cognitive distortions: {analysis.get('cognitive_distortions', '—')}",
        f"Technique hint: {analysis.get('technique_hint', '—')}",
        f"\n[CLIENT MESSAGE]\n{user_text}",
    ]
    if presenting:
        parts.append(f"\n[INTAKE — PRESENTING PROBLEM]\n{presenting}")
    parts.append(f"\n[AI DRAFTS]\n{_draft_lines(drafts)}")
    if analysis.get("agent_trace"):
        parts.append(f"\n[AGENT REASONING STEPS]\n{analysis['agent_trace']}")
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Public actions
# ─────────────────────────────────────────────────────────────────────────────
def summarize_case(session, drafts, intake) -> str:
    ctx = _case_context(session, drafts, intake)
    user = (ctx + "\n\n[TASK]\nSummarize this case for the reviewing clinician "
            "in 3-4 sentences: the client's core concern, the assessed risk, "
            "and what the AI is proposing.")
    return agent_client.complete(_SYSTEM, user, max_new_tokens=300) or _UNAVAILABLE


def suggest_decision(session, drafts, intake) -> str:
    ctx = _case_context(session, drafts, intake)
    user = (ctx + "\n\n[TASK]\nRecommend ONE action and justify it briefly "
            "(advisory only):\n"
            "• APPROVE (state which draft #) — when a draft is safe, empathic, "
            "and clinically appropriate. This should be the DEFAULT for a sound "
            "draft; a low grounding score alone is NOT a reason to reject.\n"
            "• EDIT — when it's close but needs a specific, named fix.\n"
            "• REJECT — ONLY when the text is unsafe, clinically inappropriate, "
            "fabricates a clinical claim, or there is NO draft (high-risk L1), in "
            "which case routing to a human clinician is the correct action.\n"
            "Weigh the safety, empathy and appropriateness of the actual reply — "
            "not the raw grounding number. Start your answer with the chosen "
            "action word.")
    return agent_client.complete(_SYSTEM, user, max_new_tokens=400) or _UNAVAILABLE


def explain_triage(session, drafts, intake) -> str:
    ctx = _case_context(session, drafts, intake)
    user = (ctx + "\n\n[TASK]\nExplain in plain language why this message was "
            "triaged to its current level, and what the grounding / "
            "hallucination scores on the drafts mean for trustworthiness. "
            "Help a busy clinician decide quickly.")
    return agent_client.complete(_SYSTEM, user, max_new_tokens=350) or _UNAVAILABLE


def answer_question(session, drafts, intake, question: str) -> str:
    ctx = _case_context(session, drafts, intake)
    user = (ctx + f"\n\n[CLINICIAN QUESTION]\n{question}\n\n[TASK]\nAnswer the "
            "clinician's question using only the case data above.")
    return agent_client.complete(_SYSTEM, user, max_new_tokens=400) or _UNAVAILABLE


def draft_soap(session, drafts, intake) -> Optional[Dict]:
    """
    AI-drafted SOAP note. Returns a dict with subjective/objective/assessment/
    plan keys, or None when the orchestrator is unavailable (caller then uses
    the template-based soap_export.synthesize as fallback).
    """
    ctx = _case_context(session, drafts, intake)
    user = (ctx + "\n\n[TASK]\nWrite a clinical SOAP note. Output EXACTLY four "
            "labeled sections, each 1-3 sentences:\n"
            "Subjective: <client's reported experience>\n"
            "Objective: <observable data: triage, emotion, distortions, scores>\n"
            "Assessment: <clinical impression>\n"
            "Plan: <CBT technique chosen and next steps>")
    text = agent_client.complete(_SYSTEM, user, max_new_tokens=500)
    if not text:
        return None
    return _parse_soap(text)


def _parse_soap(text: str) -> Dict:
    import re
    def grab(label: str) -> str:
        m = re.search(
            rf"{label}\s*:\s*(.+?)(?=\n(?:Subjective|Objective|Assessment|Plan)\s*:|\Z)",
            text, re.S | re.I)
        return m.group(1).strip() if m else ""
    return {
        "subjective": grab("Subjective") or text.strip(),
        "objective": grab("Objective"),
        "assessment": grab("Assessment"),
        "plan": grab("Plan"),
    }
