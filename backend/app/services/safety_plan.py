"""
Collaborative safety plan (Stanley-Brown Safety Planning Intervention).

A structured, six-section plan the client can build, save, and return to —
the clinical gold standard for elevated risk, which generic chatbots don't
offer. The AI DRAFTS it from the conversation (warning signs, coping
strategies, distractions it can infer) and ALWAYS carries the crisis lines;
the client edits and owns it. It never replaces the crisis gate: acute risk
still routes to the hotline + clinician regardless.

    plan = safety_plan.generate(user_texts)        # dict of 6 sections
    safety_plan.save(db, user_id, plan)
    safety_plan.load(db, user_id)                  # dict or None
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.crypto import decrypt_str, encrypt_phi
from app.db import models
from app.services import llm_client

log = logging.getLogger(__name__)

# Always-present professional/crisis contacts — never AI-generated, never
# removed. The plan is additive to these, not a replacement.
CRISIS_CONTACTS = [
    "988 Suicide & Crisis Lifeline — call or text 988 (US, 24/7)",
    "Find A Helpline (international) — https://findahelpline.com",
    "Your campus counselling/health centre",
    "Emergency services — 911 (or your local emergency number)",
]

SECTIONS = [
    "warning_signs", "coping_strategies", "distractions",
    "support_people", "professionals", "safe_environment",
]

_SYS = (
    "You are a CBT clinician drafting a collaborative SAFETY PLAN with a "
    "student (Stanley-Brown structure). From the conversation, draft SHORT, "
    "concrete, first-person bullet items for these sections. Use ONLY what "
    "the student implied plus widely-safe generic options; never invent "
    "specific people or facts. Output STRICT JSON with these keys, each a "
    "list of 2-4 short strings:\n"
    '  "warning_signs": thoughts/feelings/situations that signal things are '
    "getting harder;\n"
    '  "coping_strategies": things I can do ALONE to steady myself (grounding, '
    "breathing, a walk, music);\n"
    '  "distractions": places I can go or activities that take my mind off it;\n'
    '  "support_people": TYPES of people I could reach out to (a close friend, '
    "a sibling, a trusted classmate) — do NOT invent names;\n"
    '  "safe_environment": small steps to make my surroundings safer/calmer.\n'
    "Do NOT include a 'professionals' key — that is filled by the system. "
    "Output ONLY the JSON object.")


def _empty() -> Dict[str, List[str]]:
    return {
        "warning_signs": [
            "I notice my thoughts racing toward worst-case outcomes",
            "I start avoiding people or tasks",
            "I feel hopeless or like a burden",
        ],
        "coping_strategies": [
            "Try the 5-4-3-2-1 grounding technique",
            "Slow breathing: in for 4, out for 6, for two minutes",
            "Step outside for a short walk or change of room",
        ],
        "distractions": [
            "Go to a public, comfortable place (library, café)",
            "Watch or listen to something familiar and calming",
        ],
        "support_people": [
            "A close friend I trust",
            "A family member or sibling I feel safe with",
        ],
        "safe_environment": [
            "Put away anything I could use to hurt myself",
            "Stay around other people rather than being alone",
        ],
    }


def generate(user_texts: List[str]) -> Dict:
    """Draft a plan from the conversation. Falls back to safe defaults when
    the model is unavailable — a plan is ALWAYS returned, with crisis lines."""
    plan = _empty()
    convo = "\n".join(t for t in (user_texts or []) if t)[:2000]
    if convo.strip():
        try:
            gen = llm_client.generate(
                [{"role": "system", "content": _SYS},
                 {"role": "user",
                  "content": f"[CONVERSATION]\n{convo}\n\nDraft the JSON."}],
                n=1, temperature=0.3)
            if gen and not gen.get("degraded") and gen.get("mode") != "mock":
                raw = (gen.get("responses") or [""])[0]
                m = re.search(r"\{.*\}", raw, re.S)
                if m:
                    parsed = json.loads(m.group())
                    for k in ("warning_signs", "coping_strategies",
                              "distractions", "support_people",
                              "safe_environment"):
                        v = parsed.get(k)
                        if isinstance(v, list) and v:
                            plan[k] = [str(x).strip()[:160] for x in v[:4]
                                       if str(x).strip()]
        except Exception as e:
            log.warning("safety_plan generate failed (%s) — defaults", e)
    # professionals is SYSTEM-owned and always present
    plan["professionals"] = list(CRISIS_CONTACTS)
    return plan


def save(db, user_id, plan: Dict) -> None:
    row = db.query(models.SafetyPlan).filter_by(user_id=user_id).first()
    # never persist without the crisis contacts
    plan = {**plan, "professionals": list(CRISIS_CONTACTS)}
    blob = encrypt_phi(json.dumps(plan, ensure_ascii=False))
    now = datetime.now(timezone.utc)
    if row:
        row.content_enc = blob
        row.updated_at = now
    else:
        db.add(models.SafetyPlan(user_id=user_id, content_enc=blob,
                                 created_at=now, updated_at=now))
    db.flush()


def load(db, user_id) -> Optional[Dict]:
    row = db.query(models.SafetyPlan).filter_by(user_id=user_id).first()
    if not row:
        return None
    try:
        plan = json.loads(decrypt_str(row.content_enc))
        plan["professionals"] = list(CRISIS_CONTACTS)  # always fresh
        plan["updated_at"] = row.updated_at.isoformat() if row.updated_at else None
        return plan
    except Exception as e:
        log.warning("safety_plan load failed for %s: %s", user_id, e)
        return None


# Intent: the client explicitly wants a plan (distinct from a crisis message,
# which the safety gate handles first — this only runs on non-L0 turns).
_INTENT = re.compile(
    r"\b(safety plan|make (me )?a plan|coping plan|plan to (stay|keep) safe|"
    r"help me (stay|keep) safe|stay safe plan|crisis plan|"
    r"plan for when (things|it) get)", re.I)


def wants_plan(text: str) -> bool:
    return bool(_INTENT.search(text or ""))
