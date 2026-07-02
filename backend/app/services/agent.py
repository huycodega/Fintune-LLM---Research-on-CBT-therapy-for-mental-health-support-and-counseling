"""
Agentic orchestration layer — the ReAct loop for the CBT assistant.

WHERE THIS SITS
───────────────
The deterministic safety gate in `chat.py` runs FIRST and is authoritative:
  L0 (crisis) and L1 (high risk) never reach this module.
This agent only ever runs in the L2/L3 zone. Its job is to let the
cbt-qwen2.5-7b-v2 orchestrator ("brain") DECIDE how to handle a
moderate/routine message — how much to retrieve, whether to recall the
user's history, whether to ask a clarifying question, or whether to escalate
to a clinician — instead of a fixed Python pipeline.

SAFETY INVARIANTS
─────────────────
  • The agent can only move safety UP, never down: `escalate_to_clinician`
    forces a clinician review even on L3. There is NO tool that lowers risk.
  • The actual client-facing reply is always produced by the fine-tuned
    responder `cbt-qwen2.5-7b-v2` via `generate_cbt_response` (which routes
    through llm_client + prompt_builder), so the orchestrator never writes
    therapeutic copy itself.
  • Any failure (orchestrator unreachable, malformed tool calls, step budget
    exhausted with no draft) returns None / forces a generate so chat.py can
    fall back to the fixed pipeline. The agent never blocks a response.

TOOLS (wrap existing services)
──────────────────────────────
  retrieve_cbt_knowledge  → retrieval.retrieve
  recall_session_memory   → Qdrant session_memory (filtered by user_id)
  analyze_cognition       → analyzer.analyze
  generate_cbt_response   → prompt_builder + llm_client.generate  [TERMINAL]
  ask_clarification       → returns a question to the user         [TERMINAL]
  escalate_to_clinician   → forces review queue                    [TERMINAL]
"""
import logging
import re
from collections import Counter
from typing import Dict, List, Optional

from app.core.config import settings
from app.services import (
    agent_client, retrieval, analyzer, prompt_builder, llm_client,
    post_process, preflight, embedder, qdrant_client as qd, metrics,
    safety_gate, user_memory,
)
from app.db import models
from app.db.session import db_session


log = logging.getLogger(__name__)

# Terminal tools end the loop and decide the session outcome.
_TERMINAL = {"generate_cbt_response", "ask_clarification",
             "escalate_to_clinician"}

# Required arguments per tool — used to OBSERVE (not hide) whether the
# orchestrator emits well-formed tool calls. A missing arg still runs the
# tool (it falls back to the client message) but is recorded in the trace and
# counted in metrics so the agent eval can report tool-arg validity.
_REQUIRED_ARGS = {
    "retrieve_cbt_knowledge": ["query"],
    "recall_session_memory": ["query"],
    "analyze_cognition": ["text"],
    "plan_session": [],
    "recommend_lesson": ["topic"],
    "recommend_resource": ["topic"],
    "summarize_progress": [],
    "get_my_data": ["kind"],
    "list_psychologists": [],
    "suggest_screening": ["instrument", "reason"],
    "generate_cbt_response": [],
    "ask_clarification": ["question"],
    "escalate_to_clinician": ["reason"],
}


def _missing_args(name: str, args: Dict) -> List[str]:
    """Return the list of required args the model failed to supply."""
    req = _REQUIRED_ARGS.get(name, [])
    if not isinstance(args, dict):
        return list(req)
    return [k for k in req if not str(args.get(k) or "").strip()]


def _risk_escalation(state: Dict, trace: List[Dict], step: int) -> Optional[Dict]:
    """Defense-in-depth: if the client's words carry acute-risk language, return
    an escalation result that overrides whatever non-escalate terminal the model
    chose. Safety can only go UP. Returns None when there is no acute risk.
    The primary safety gate already ran in chat.py; this is a second net so a
    risky turn that slipped into the L2/L3 agent never auto-replies."""
    if not safety_gate.has_acute_risk(state.get("user_scrubbed", "")):
        return None
    metrics.inc("cbt_agent_risk_recheck_total")
    trace.append({"step": step, "tool": "escalate_to_clinician",
                  "arguments": {"reason": "acute-risk re-check"},
                  "note": "forced escalate (risk re-check overrode terminal)"})
    return {"outcome": "escalate",
            "escalate_reason": ("Safety re-check detected acute-risk language; "
                                "routed to a clinician."),
            "trace": trace}


# ─────────────────────────────────────────────────────────────────────────────
# Tool schemas advertised to the orchestrator (OpenAI function-calling format)
# ─────────────────────────────────────────────────────────────────────────────
TOOL_SCHEMAS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_cbt_knowledge",
            "description": (
                "Search the CBT knowledge base and similar prior counseling "
                "dialogues. Call this to ground the response in evidence "
                "before generating. Returns the most relevant passages."),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Search query — usually the "
                              "client's concern or detected distortion."},
                    "top_k": {"type": "integer",
                              "description": "How many passages (default 5)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_session_memory",
            "description": (
                "Retrieve THIS client's own prior session summaries to keep "
                "continuity (technique used last time, recurring themes). "
                "Only returns this user's history."),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "What to look for in past sessions."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_cognition",
            "description": (
                "Run psychological analysis on a piece of text to detect "
                "emotion, cognitive distortions, and a suggested CBT technique."),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string",
                             "description": "Text to analyze (the client message)."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_session",
            "description": (
                "Lay out a short, standard CBT plan for this session and mark "
                "which step to work on now. Call it early (after analyze) to "
                "structure a multi-turn piece of work; it keeps later turns "
                "advancing the SAME plan instead of restarting."),
            "parameters": {
                "type": "object",
                "properties": {
                    "technique": {"type": "string",
                                  "description": "Optional CBT technique to plan "
                                  "around; defaults to the analyzed technique hint."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_lesson",
            "description": (
                "Find published CBT micro-lessons matching a topic so you can "
                "offer the client concrete practice. Returns real lesson titles "
                "from the library — never invent one. To answer 'what lessons "
                "are there / do you have', pass list_all=true to list the "
                "available lessons instead of matching a topic."),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string",
                              "description": "Theme to match, e.g. 'stress', "
                              "'sleep', 'all-or-nothing thinking'."},
                    "list_all": {"type": "boolean",
                                 "description": "Set true to LIST the available "
                                 "lessons (for 'what lessons are there')."},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_resource",
            "description": (
                "Find published support resources (articles, audio, tools) "
                "matching a topic. Returns real resources from the library — "
                "never invent one."),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string",
                              "description": "Theme to match for the resource."},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_progress",
            "description": (
                "Retrieve a compact summary of THIS client's journey so far "
                "(recurring themes, techniques tried, total prior turns) so you "
                "can acknowledge progress and stay consistent. Returning-client "
                "context only — do NOT narrate it as a shared transcript."),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_data",
            "description": (
                "Look up THIS client's own MindCare records to answer a factual "
                "question about themselves. Use it for: 'who am I' (profile), "
                "'my appointments' (upcoming/past bookings), 'my mood' (recent "
                "mood check-ins), 'my screening results' (PHQ-9/GAD-7 history). "
                "Returns REAL records only — never invent dates, names, or "
                "scores. After calling, finish with generate_cbt_response."),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string",
                             "enum": ["profile", "appointments", "mood",
                                      "screening_history"],
                             "description": "Which record to fetch."},
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_psychologists",
            "description": (
                "List the counselling experts the client can book a consultation "
                "with (name, specialty, experience). Use it for 'which "
                "psychologists are there / who can I talk to'. Returns the real "
                "directory — never invent a person."),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_screening",
            "description": (
                "Gently invite the client to take a short, validated self-check "
                "(PHQ-9 for low mood, GAD-7 for anxiety) when their message shows "
                "persistent depression or anxiety signals and a quick measure "
                "would help them and the clinician track it. Adds a soft prompt to "
                "the reply — it does NOT diagnose. Use at most once."),
            "parameters": {
                "type": "object",
                "properties": {
                    "instrument": {"type": "string", "enum": ["phq9", "gad7"],
                                   "description": "phq9 for depression/low mood, gad7 for anxiety."},
                    "reason": {"type": "string",
                               "description": "Brief why, in plain language."},
                },
                "required": ["instrument", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_cbt_response",
            "description": (
                "TERMINAL. Produce the final CBT response using the fine-tuned "
                "responder. Call this once you have gathered enough context "
                "(retrieval / analysis). The response is drafted by the "
                "specialist model, not by you."),
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {"type": "string",
                              "description": "Optional one-line clinical focus "
                              "to steer the responder (e.g. distortion to target)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_clarification",
            "description": (
                "TERMINAL. When the client's message is too vague to respond "
                "therapeutically, ask ONE concise clarifying question instead "
                "of generating a full response."),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string",
                                 "description": "The single clarifying question."},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_clinician",
            "description": (
                "TERMINAL. If you detect risk signals the triage may have "
                "missed (self-harm hints, severe hopelessness, safeguarding "
                "concerns), escalate to a human clinician. Safety can only go "
                "UP — use this whenever in doubt."),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string",
                               "description": "Why this needs a human clinician."},
                },
                "required": ["reason"],
            },
        },
    },
]


_SYSTEM_PROMPT = (
    "You are the clinical orchestrator of a CBT support system. You do NOT "
    "write the therapeutic reply yourself — a fine-tuned specialist model does "
    "that when you call generate_cbt_response. Your job is to decide, step by "
    "step, how to handle a client message that has already been triaged as "
    "MODERATE (L2) or ROUTINE (L3).\n\n"
    "ALWAYS respond by CALLING A TOOL, never with prose. Do not explain your "
    "reasoning in free text — express every decision as a tool call.\n\n"
    "Recommended procedure (follow it unless the message is too vague):\n"
    "  1. analyze_cognition(text=<the client message>) — detect the emotion "
    "and cognitive distortion.\n"
    "  1b. (optional) plan_session() — lay out a short CBT plan and work the "
    "current step; use it for multi-turn work so each turn advances the plan.\n"
    "  2. retrieve_cbt_knowledge(query=<the concern or distortion>) — pull "
    "CBT evidence to ground the reply. This step is REQUIRED before generating.\n"
    "  3. ENRICH the reply before generating — DO call these when they apply, "
    "they make the response concrete and personal:\n"
    "     • Returning client (there IS conversation history / prior turns): call "
    "summarize_progress() to acknowledge their journey and stay consistent.\n"
    "     • Client wants something to DO, or names a workable theme (stress, "
    "sleep, exams, racing thoughts, 'what can I do', 'how do I practise'): call "
    "recommend_lesson(topic=...) and/or recommend_resource(topic=...), then offer "
    "ONE by its EXACT returned title. NEVER invent a lesson/resource.\n"
    "     • Client asks what suits THEM / their current mood ('which exercises "
    "fit my mood', 'what should I try for how I feel'): first analyze_cognition "
    "(and optionally get_my_data(kind=\"mood\")) to read their state, THEN "
    "recommend_lesson/recommend_resource with that theme so the picks are "
    "tailored — not a generic list.\n"
    "     • Client asks what to focus on BASED ON their screening/results: call "
    "get_my_data(kind=\"screening_history\") to read PHQ-9/GAD-7, then "
    "recommend_lesson/recommend_resource matched to it (e.g. low mood → "
    "behavioural activation; high anxiety → relaxation/decatastrophizing). "
    "Report scores factually; NEVER diagnose.\n"
    "     • Persistent low mood or anxiety signals (and no recent self-check): call "
    "suggest_screening(instrument=\"phq9\"|\"gad7\", reason=...) to gently invite a "
    "validated check-in. At most once; never diagnose.\n"
    "     • The client asks about THEIR OWN data or the app's offerings: fetch the "
    "REAL records first, then generate. 'who am I' → get_my_data(kind=\"profile\"); "
    "'my appointments' → get_my_data(kind=\"appointments\"); 'my mood' → "
    "get_my_data(kind=\"mood\"); 'my screening/PHQ-9/GAD-7 results' → "
    "get_my_data(kind=\"screening_history\"); 'what lessons are there' → "
    "recommend_lesson(list_all=true); 'which psychologists/experts can I see' → "
    "list_psychologists(). NEVER invent appointments, scores, lessons, or names — "
    "only state what the tool returned.\n"
    "  4. Finish with exactly ONE terminal action:\n"
    "       • generate_cbt_response — the normal path, AFTER retrieving.\n"
    "       • ask_clarification — ONLY if the message is too vague to help.\n"
    "       • escalate_to_clinician — if you sense risk beyond the triage.\n\n"
    "Examples (each step is one tool call):\n"
    "  A) \"I always fail and everyone judges me\": analyze_cognition → "
    "retrieve_cbt_knowledge(query=\"all-or-nothing thinking, fear of judgement\") "
    "→ generate_cbt_response.\n"
    "  B) \"The exam stress is overwhelming — what can I actually do?\": "
    "analyze_cognition → retrieve_cbt_knowledge(query=\"managing exam stress\") → "
    "recommend_lesson(topic=\"exam stress\") → generate_cbt_response (offer the "
    "returned lesson by name).\n"
    "  C) Returning client (\"the same spiral is back\"): summarize_progress() → "
    "retrieve_cbt_knowledge(...) → generate_cbt_response.\n"
    "  D) \"What are my upcoming appointments?\": get_my_data(kind=\"appointments\") "
    "→ generate_cbt_response (state ONLY the returned bookings).\n\n"
    "Safety rules:\n"
    "  • You may only INCREASE caution. Never downplay risk.\n"
    "  • If anything hints at self-harm, hopelessness, or danger, escalate.\n"
    "  • NEVER call generate_cbt_response before retrieve_cbt_knowledge has "
    "run at least once (unless you are asking for clarification).\n"
    "Keep tool use efficient — you have a limited number of steps."
)


# ─────────────────────────────────────────────────────────────────────────────
# Tool implementations
# ─────────────────────────────────────────────────────────────────────────────
def _tool_retrieve(args: Dict, state: Dict) -> str:
    query = (args.get("query") or state["user_scrubbed"]).strip()
    top_k = int(args.get("top_k") or settings.rag_final_top_k)
    try:
        # v2 risk-aware retriever — route by the (locked) risk level.
        hits = retrieval.retrieve(
            query, risk_level=state.get("risk_level", "normal"), top_k=top_k)
    except Exception as e:
        log.warning("agent retrieve failed: %s", e)
        return "retrieval unavailable"
    # accumulate for generate_cbt_response (dedupe by id)
    seen = {r["id"] for r in state["retrieved"]}
    for h in hits:
        if h["id"] not in seen:
            state["retrieved"].append(h)
            seen.add(h["id"])
    if not hits:
        return "No relevant passages found."
    lines = [f"({i}) [{h.get('source_collection','?')}] {h.get('text','')[:300]}"
             for i, h in enumerate(hits, 1)]
    return "Top passages:\n" + "\n".join(lines)


def _tool_recall_memory(args: Dict, state: Dict) -> str:
    query = (args.get("query") or state["user_scrubbed"]).strip()
    uid = state.get("user_id")
    if not uid:
        return "No user context for memory recall."
    try:
        from qdrant_client.http.models import (
            Filter, FieldCondition, MatchValue)
        vec = embedder.embed_one(query)
        flt = Filter(must=[FieldCondition(
            key="user_id", match=MatchValue(value=str(uid)))])
        hits = qd.search(settings.qdrant_collection_memory, vec,
                         limit=3, filter_dict=flt)
    except Exception as e:
        log.warning("agent memory recall failed: %s", e)
        return "Session memory unavailable."
    if not hits:
        return "No prior sessions for this client."
    out = []
    for h in hits:
        payload = dict(getattr(h, "payload", {}) or {})
        out.append(payload.get("text", "")[:300])
    return ("Prior sessions for THIS client (routing context only — use to "
            "stay consistent, do NOT quote back as 'our talks'/'as we "
            "discussed'):\n" + "\n---\n".join(out))


def _tool_analyze(args: Dict, state: Dict) -> str:
    text = (args.get("text") or state["user_scrubbed"]).strip()
    try:
        analysis = analyzer.analyze(text, severity=state.get("severity"))
    except Exception as e:
        log.warning("agent analyze failed: %s", e)
        return "Analysis unavailable."
    state["analysis"] = analysis
    return (f"Emotion: {analysis.get('emotion')}; "
            f"Distortions: {analysis.get('cognitive_distortions')}; "
            f"Technique hint: {analysis.get('technique_hint')}")


# ─────────────────────────────────────────────────────────────────────────────
# Session planning — standard CBT micro-step sequences per technique. The plan
# is deterministic (clinically conventional), so no extra LLM call is needed and
# it can never drift into unsafe territory. Progress through the plan is inferred
# from how many turns this thread already has.
# ─────────────────────────────────────────────────────────────────────────────
_CBT_PLANS = {
    "thought record": [
        "Validate the feeling and name the triggering situation",
        "Identify the automatic thought",
        "Rate how strongly it's believed and the emotion",
        "Examine the evidence for and against the thought",
        "Craft a balanced, alternative thought",
        "Re-rate the belief/emotion and agree a small next step",
    ],
    "cognitive restructuring": [
        "Validate and pinpoint the key distorted thought",
        "Name the cognitive distortion at work",
        "Test the thought against the evidence",
        "Reframe into a fairer, balanced thought",
        "Plan one concrete action to practise it",
    ],
    "decatastrophizing": [
        "Validate the worry and name the feared worst case",
        "Estimate how likely it realistically is",
        "Plan how you'd cope even if it happened",
        "Shrink the catastrophe to a manageable size",
    ],
    "behavioral activation": [
        "Validate low motivation and pick one valued/avoided activity",
        "Break it into a tiny first step",
        "Schedule exactly when to do it",
        "Plan a brief review of how it felt",
    ],
    "problem solving": [
        "Validate and define the problem clearly",
        "Brainstorm several possible options",
        "Weigh the pros and cons of each",
        "Choose one and plan the first action",
    ],
}
_GENERIC_PLAN = [
    "Validate the client's experience",
    "Clarify the key thought or feeling to work on",
    "Examine it together with a CBT technique",
    "Agree one concrete next step",
]


def _prior_ai_turns(state: Dict) -> int:
    ctx = state.get("session_ctx") or {}
    hist = ctx.get("history") or []
    return sum(1 for t in hist if (t.get("reply") or "").strip())


def _tool_plan_session(args: Dict, state: Dict) -> str:
    """Build (or advance) a short CBT session plan and mark the current step.
    Deterministic per detected technique; the current step follows the number
    of turns already taken in this thread, so multi-turn work advances."""
    analysis = state.get("analysis") or {}
    tech = (args.get("technique") or analysis.get("technique_hint")
            or "").strip().lower()
    steps = _CBT_PLANS.get(tech, _GENERIC_PLAN)
    current = min(_prior_ai_turns(state), len(steps) - 1)
    state["plan"] = {"technique": tech or "general CBT",
                     "steps": steps, "current": current}
    lines = [("→ " if i == current else "   ") + f"{i+1}. {s}"
             for i, s in enumerate(steps)]
    return (f"Session plan ({tech or 'general CBT'}) — currently on step "
            f"{current + 1}/{len(steps)}:\n" + "\n".join(lines))


def _topic_terms(topic: str) -> list:
    return [t for t in (topic or "").lower().replace(",", " ").split() if len(t) > 2]


def _match_published(rows, topic: str, limit: int = 3) -> list:
    """Rank published rows by topic-keyword overlap (title/category/tags) and
    return ONLY genuine matches (score > 0). No blind fallback: if nothing in the
    library fits the conversation we return [] so the caller recommends NOTHING,
    rather than pushing an off-topic item. (Never fabricates — real rows only.)"""
    terms = _topic_terms(topic)
    scored = []
    for r in rows:
        hay = " ".join(str(x).lower() for x in
                       [r.title, r.category or "", " ".join(r.tags or [])])
        score = sum(1 for t in terms if t in hay)
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored][:limit]


# Cosine floor for semantic matching. bge-m3 is L2-normalized, so this is a
# straight dot-product threshold: below it the item isn't relevant enough to
# recommend (precision over recall — we'd rather offer nothing than off-topic).
_SEMANTIC_THRESHOLD = 0.38


def _item_text(r) -> str:
    """Compact text representation of a lesson/resource for embedding."""
    parts = [getattr(r, "title", "") or "",
             getattr(r, "category", "") or "",
             " ".join(getattr(r, "tags", None) or []),
             getattr(r, "description", "") or ""]
    return " ".join(p for p in parts if p).strip()


def _semantic_rank(rows, topic: str, limit: int = 3):
    """Rank published rows by EMBEDDING similarity to the topic (meaning, not
    keywords) so e.g. 'sadness' matches a 'low mood / depression' lesson.
    Returns matched rows (cosine >= threshold), [] when nothing is relevant
    enough, or None when embeddings are unavailable (caller falls back to
    keyword matching)."""
    if not rows or not (topic or "").strip():
        return None
    try:
        from app.services import embedder
        texts = [topic] + [_item_text(r) for r in rows]
        vecs = embedder.embed(texts)
        if not vecs or len(vecs) != len(texts):
            return None
        q = vecs[0]
        sims = [(sum(a * b for a, b in zip(q, v)), r)
                for r, v in zip(rows, vecs[1:])]
        sims.sort(key=lambda x: -x[0])
        return [r for s, r in sims if s >= _SEMANTIC_THRESHOLD][:limit]
    except Exception as e:
        log.warning("semantic recommend failed (%s) — keyword fallback", e)
        return None


def _rank_published(rows, topic: str, limit: int = 3) -> list:
    """Prefer semantic ranking; fall back to keyword overlap if embeddings are
    unavailable. Either way, only genuinely-relevant items are returned."""
    sem = _semantic_rank(rows, topic, limit)
    if sem is not None:
        return sem
    return _match_published(rows, topic, limit)


def _top_recommendations(topic: str, limit: int = 2) -> Dict:
    """Pick the FEW most relevant published items for the topic — lessons and
    resources ranked TOGETHER by meaning, capped at `limit` total, and only when
    they genuinely match (semantic threshold). Returns
    {"lessons": [...], "resources": [...]}; empty when nothing fits."""
    out = {"lessons": [], "resources": []}
    try:
        with db_session() as db:
            lessons = (db.query(models.Lesson).filter_by(status="published")
                       .order_by(models.Lesson.updated_at.desc()).limit(50).all())
            resources = (db.query(models.Resource).filter_by(status="published")
                         .order_by(models.Resource.updated_at.desc()).limit(50).all())
            rows = list(lessons) + list(resources)
            if not rows:
                return out
            for r in _rank_published(rows, topic, limit):
                if isinstance(r, models.Lesson):
                    out["lessons"].append({"title": r.title, "category": r.category,
                                           "duration": r.duration})
                else:
                    out["resources"].append({"title": r.title, "type": r.type})
    except Exception as e:
        log.warning("top_recommendations failed: %s", e)
    return out


_LIST_ALL_WORDS = {"", "all", "any", "everything", "available", "list",
                   "lessons", "what", "show"}


def _tool_recommend_lesson(args: Dict, state: Dict) -> str:
    raw = (args.get("topic") or "").strip()
    # "what lessons are there" → list mode (explicit flag or a generic topic).
    list_all = bool(args.get("list_all")) or raw.lower() in _LIST_ALL_WORDS
    try:
        with db_session() as db:
            rows = (db.query(models.Lesson)
                    .filter_by(status="published")
                    .order_by(models.Lesson.updated_at.desc()).limit(50).all())
            if list_all:
                picked = rows[:6]
            else:
                topic = raw or state.get("user_scrubbed", "")
                picked = _rank_published(rows, topic, 2)
            items = [{"title": r.title, "category": r.category,
                      "duration": r.duration} for r in picked]
    except Exception as e:
        log.warning("agent recommend_lesson failed: %s", e)
        return "Lesson library unavailable."
    if not items:
        return "No lessons in the library yet."
    state["recommendations"]["lessons"].extend(items)
    header = "Available CBT lessons:" if list_all else "Matching CBT lessons:"
    return header + "\n" + "\n".join(
        f"- {it['title']}" + (f" ({it['duration']})" if it['duration'] else "")
        for it in items)


def _tool_recommend_resource(args: Dict, state: Dict) -> str:
    topic = (args.get("topic") or state.get("user_scrubbed", "")).strip()
    try:
        with db_session() as db:
            rows = (db.query(models.Resource)
                    .filter_by(status="published")
                    .order_by(models.Resource.updated_at.desc()).limit(50).all())
            picked = _rank_published(rows, topic, 2)
            items = [{"title": r.title, "type": r.type} for r in picked]
    except Exception as e:
        log.warning("agent recommend_resource failed: %s", e)
        return "Resource library unavailable."
    if not items:
        return "No resources in the library yet."
    state["recommendations"]["resources"].extend(items)
    return "Matching resources:\n" + "\n".join(
        f"- {it['title']} [{it['type']}]" for it in items)


def _tool_summarize_progress(args: Dict, state: Dict) -> str:
    uid = state.get("user_id")
    if not uid:
        return "No prior history for this client."
    try:
        with db_session() as db:
            mem = user_memory.load_for_prompt(db, uid)
    except Exception as e:
        log.warning("agent summarize_progress failed: %s", e)
        return "Progress summary unavailable."
    if not mem or not mem.get("turn_count"):
        return "This is an early session — little prior history yet."
    themes = ", ".join(mem.get("recurring_themes", []) or []) or "—"
    techs = ", ".join(mem.get("techniques_used", []) or []) or "—"
    return ("Client journey (routing context only — do NOT quote as a "
            f"transcript):\n- Prior turns: {mem.get('turn_count', 0)}\n"
            f"- Recurring themes: {themes}\n- Techniques tried: {techs}\n"
            f"- Gist: {mem.get('summary', '—') or '—'}")


# ── self-data tools — read THIS user's own records (real, never fabricated) ───
# Each appends a verbatim block to state["facts"]; _do_generate surfaces those
# blocks in the reply so the actual data is always shown (anti-fabrication: the
# DB is the source of truth, not the responder's prose).
def _tool_get_my_data(args: Dict, state: Dict) -> str:
    from app.services import self_data
    kind = (args.get("kind") or "").strip().lower()
    uid = state.get("user_id")
    if not uid:
        return "No signed-in user to look up."
    fn = {
        "profile":           lambda db: self_data.profile(db, uid),
        "appointments":      lambda db: self_data.appointments(db, uid),
        "mood":              lambda db: self_data.mood(db, uid),
        "screening_history": lambda db: self_data.screening(db, uid),
    }.get(kind)
    if not fn:
        return f"Unknown data kind: {kind}"
    try:
        with db_session() as db:
            block = fn(db)
    except Exception as e:
        log.warning("agent get_my_data(%s) failed: %s", kind, e)
        return "That information is unavailable right now."
    state["facts"].append(block)
    return block


def _tool_list_psychologists(args: Dict, state: Dict) -> str:
    from app.services import self_data
    try:
        with db_session() as db:
            block = self_data.psychologists(db)
    except Exception as e:
        log.warning("agent list_psychologists failed: %s", e)
        return "The expert directory is unavailable right now."
    state["facts"].append(block)
    return block


# Practice-seeking signals — when the client clearly wants something to DO and
# the model didn't pull a lesson/resource itself, _ensure_enriched fetches a real
# one. Gated so it never spam-recommends on ordinary turns.
_PRACTICE_PAT = re.compile(
    r"\b(what (can|should|could) i do|how (do|can|should) i|"
    r"something (concrete|practical|to (do|try|practi\w*))|"
    r"practi[cs]e|exercises?|tips?|techniques?|tools? (to|for)|"
    r"manage|cope with|deal with|work on|get better at|"
    r"this week|day[ -]?to[ -]?day|every ?day|homework|steps? (to|for))\b", re.I)


def _ensure_enriched(state: Dict) -> None:
    """Deterministic enrichment: when the client clearly wants something to
    practise and the orchestrator didn't already pull a lesson/resource, fetch a
    REAL one so the reply is actionable. Gated on practice-seeking signals — it
    never recommends on ordinary turns, and never fabricates (real items only)."""
    recs = state.get("recommendations") or {"lessons": [], "resources": []}
    if recs.get("lessons") or recs.get("resources"):
        return   # the model already enriched — don't double up
    msg = state.get("user_scrubbed", "")
    if not _PRACTICE_PAT.search(msg):
        return   # not a practice-seeking message — leave it alone
    analysis = state.get("analysis") or {}
    topic = ((analysis.get("technique_hint") or "") + " " + msg).strip()
    top = _top_recommendations(topic, limit=2)
    if not (top["lessons"] or top["resources"]):
        return   # nothing in the library genuinely fits — recommend nothing
    metrics.inc("cbt_agent_forced_enrichment_total")
    state["forced_enrichment"] = True
    state["recommendations"]["lessons"].extend(top["lessons"])
    state["recommendations"]["resources"].extend(top["resources"])


def _tool_suggest_screening(args: Dict, state: Dict) -> str:
    """Record a soft suggestion to take a validated self-check. Non-terminal —
    the CTA is appended to the final reply; scoring stays the standard PHQ-9/GAD-7."""
    instrument = (args.get("instrument") or "phq9").lower()
    if instrument not in ("phq9", "gad7"):
        instrument = "phq9"
    state["screening_suggestion"] = {
        "instrument": instrument,
        "reason": (args.get("reason") or "").strip(),
    }
    label = "GAD-7 (anxiety)" if instrument == "gad7" else "PHQ-9 (low mood)"
    return f"Will invite the client to a quick {label} self-check."


def _screening_footer(state: Dict) -> str:
    s = state.get("screening_suggestion")
    if not s:
        return ""
    label = "GAD-7 anxiety check-in" if s["instrument"] == "gad7" else "PHQ-9 mood check-in"
    return (f"\n\n💡 When you're ready, a quick {label} on the Screening page can "
            f"help us track how you're doing.")


def _rec_footer(state: Dict) -> str:
    """Render the REAL lessons/resources the agent pulled as a short footer, so
    the reply always names them even when the responder doesn't weave them in.
    Empty string when there are no recommendations."""
    recs = state.get("recommendations") or {}
    lines = []
    for x in recs.get("lessons", []) or []:
        dur = f" ({x['duration']})" if x.get("duration") else ""
        lines.append(f"- Lesson: {x['title']}{dur}")
    for x in recs.get("resources", []) or []:
        ty = f" [{x['type']}]" if x.get("type") else ""
        lines.append(f"- Resource: {x['title']}{ty}")
    if not lines:
        return ""
    seen, uniq = set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            uniq.append(ln)
    return "\n\nFrom your library, these might help:\n" + "\n".join(uniq)


def _facts_footer(state: Dict) -> str:
    """Surface the REAL records the self-data tools pulled (profile,
    appointments, mood, screening, experts) verbatim from the DB, so the reply
    always shows the actual data instead of the responder paraphrasing (and
    possibly fabricating) it. Empty string when no self-data was fetched."""
    facts = state.get("facts") or []
    if not facts:
        return ""
    seen, uniq = set(), []
    for f in facts:
        f = (f or "").strip()
        if f and f not in seen:
            seen.add(f)
            uniq.append(f)
    return ("\n\n" + "\n\n".join(uniq)) if uniq else ""


def _ensure_grounded(state: Dict, trace: List[Dict], step: int) -> None:
    """Guarantee the responder gets at least one retrieval before generating.
    The orchestrator often shortcuts straight to generate_cbt_response; an
    ungrounded reply is exactly what we don't want, so when nothing has been
    retrieved yet we auto-retrieve using the client's own message."""
    if state.get("retrieved"):
        return
    metrics.inc("cbt_agent_forced_grounding_total")
    state["forced_grounding"] = True
    res = _tool_retrieve({"query": state["user_scrubbed"]}, state)
    trace.append({"step": step, "tool": "retrieve_cbt_knowledge",
                  "arguments": {"query": state["user_scrubbed"][:80]},
                  "result": res[:200], "note": "auto-grounding (forced before generate)"})


# Below this grounding score (when retrieval exists) a draft is considered
# under-supported and triggers ONE self-revision. Grounding is lexical/NLI and
# noisy, so the floor is deliberately low — the primary signal is preflight.
_GROUNDING_FLOOR = 0.12


def _draft_to_text(d: Dict) -> str:
    return (f"Technique: {d.get('technique','')}\n"
            f"Rationale: {d.get('rationale','')}\n"
            f"Plan: {d.get('plan','')}\n"
            f"Response: {d.get('response','')}")


def _self_correct(drafts: List[Dict], state: Dict,
                  base_messages: List[Dict], temperature: float) -> List[Dict]:
    """Self-critique: score the best draft with preflight (deterministic) +
    grounding; if it fails the bar, ask the responder to revise ONCE against the
    specific critique, then keep the revision only if it's not worse. Bounded to
    a single extra call — quality up without runaway cost."""
    if not drafts:
        return drafts
    severity = state.get("severity", "moderate")
    retrieved = state.get("retrieved", [])

    def evald(d: Dict) -> Dict:
        ok, reasons = preflight.check_draft(d, severity)
        try:
            g = post_process.grounding_score(d.get("response", ""), retrieved)
        except Exception:
            g = 1.0   # don't penalise when the scorer can't load (low-RAM host)
        return {"d": d, "ok": ok, "reasons": reasons, "g": g}

    scored = sorted((evald(d) for d in drafts),
                    key=lambda s: (s["ok"], s["g"]), reverse=True)
    best = scored[0]
    ranked = [s["d"] for s in scored]
    metrics.inc("cbt_agent_selfcritique_total")

    grounded_ok = (not retrieved) or best["g"] >= _GROUNDING_FLOOR
    if best["ok"] and grounded_ok:
        return ranked   # passes the bar — no extra call

    metrics.inc("cbt_agent_selfcritique_revised_total")
    issues = "; ".join(best["reasons"]) or \
        "the response is weakly grounded in the provided reference material"
    state["self_critique"] = issues
    revise_msgs = base_messages + [
        {"role": "assistant", "content": _draft_to_text(best["d"])},
        {"role": "user", "content":
            "[SELF-REVIEW] A clinical reviewer flagged your draft: " + issues
            + ". Rewrite it ONCE: choose EXACTLY ONE canonical technique "
            "(verbatim from the allowed list), keep all four labeled fields, "
            "base every statement ONLY on the reference material and the "
            "client's own words (invent nothing), and keep the Response under "
            "200 words."},
    ]
    try:
        gen2 = llm_client.generate(
            revise_msgs, n=1, temperature=max(0.2, (temperature or 0.65) - 0.2))
        revised = post_process.parse_all(gen2.get("responses", []))
    except Exception as e:
        log.warning("self-critique revision failed: %s", e)
        return ranked
    if revised:
        rv = evald(revised[0])
        if (rv["ok"], rv["g"]) >= (best["ok"], best["g"]):
            state["self_critique_applied"] = True
            return [rv["d"]] + ranked
    return ranked


def _strip_trailing_question(text: str) -> str:
    """Listen-only safety net: drop a trailing question so the reply stays a
    pure validation, but only when real validating content remains before it."""
    t = (text or "").strip()
    if not t.endswith("?"):
        return t
    parts = re.split(r"(?<=[.!?])\s+", t)
    if len(parts) >= 2 and parts[-1].strip().endswith("?"):
        kept = " ".join(parts[:-1]).strip()
        if len(kept) >= 20:
            return kept
    return t


def _do_generate(args: Dict, state: Dict,
                 n_responses: int, temperature: float) -> Dict:
    """Terminal: build the prompt and call the fine-tuned responder."""
    # Listen-only: the client wants to be heard, not directed — so we suppress
    # lesson/resource enrichment, the "From your library" footer, and screening
    # CTAs. Real self-data (facts) still surfaces; risk still escalated upstream.
    listen_only = "just_listen" in ((state.get("session_ctx") or {}).get("style_prefs") or [])
    if not listen_only:
        _ensure_enriched(state)   # deterministic lesson/resource for practice-seeking
    focus = (args or {}).get("focus", "")
    analysis = dict(state.get("analysis") or {})
    if focus:
        analysis = {**analysis, "agent_focus": focus}
    # Surface any real lessons/resources the agent pulled so the responder can
    # offer them by name (never fabricate — these come from the library).
    recs = state.get("recommendations") or {}
    rec_lines = ([f"Lesson: {x['title']}" for x in recs.get("lessons", [])]
                 + [f"Resource: {x['title']}" for x in recs.get("resources", [])])
    if rec_lines:
        # de-dupe preserving order
        seen, uniq = set(), []
        for ln in rec_lines:
            if ln not in seen:
                seen.add(ln); uniq.append(ln)
        analysis["suggested_materials"] = "; ".join(uniq)
    # Surface any factual self-data the agent fetched (profile / appointments /
    # mood / screening / experts) so the responder answers from REAL records and
    # never says "I can't access that" or invents details.
    if state.get("facts"):
        analysis["user_facts"] = "\n".join(state["facts"])
    # Tell the responder which planned step to work on this turn.
    plan = state.get("plan")
    if plan and plan.get("steps"):
        cur, steps = plan["current"], plan["steps"]
        analysis["session_plan"] = (
            f"{plan['technique']} — work step {cur + 1}/{len(steps)} NOW: "
            f"{steps[cur]}. (Full plan: " + " → ".join(steps) + ")")
    messages = prompt_builder.build_messages(
        user_input_scrubbed=state["user_scrubbed"],
        intake=state.get("intake"),
        analysis=analysis,
        session_ctx=state.get("session_ctx"),
        retrieved=state["retrieved"],
    )
    gen = llm_client.generate(messages, n=n_responses, temperature=temperature)
    drafts = post_process.parse_all(gen.get("responses", []))
    # Self-critique: revise once if the best draft fails preflight/grounding.
    drafts = _self_correct(drafts, state, messages, temperature)
    # Listen-only: last-resort guard so no draft ends with a probing question.
    if listen_only:
        for d in drafts:
            d["response"] = _strip_trailing_question(d.get("response") or "")
    # Deterministically append the REAL recommended materials so the user always
    # sees the actual library items by name (the responder often omits them).
    # Suppressed in listen-only mode — recommending exercises is "telling them
    # what to do", which is exactly what the client asked us not to do.
    footer = "" if listen_only else _rec_footer(state)
    if footer:
        recs = state.get("recommendations") or {}
        titles = ([x.get("title", "") for x in (recs.get("lessons") or [])]
                  + [x.get("title", "") for x in (recs.get("resources") or [])])
        for d in drafts:
            resp = d.get("response") or ""
            if not resp:
                continue
            low = resp.lower()
            # Skip when the responder already listed the materials itself, so we
            # don't append a duplicate "From your library" block.
            if "from your library" in low or any(t and t.lower() in low for t in titles):
                continue
            d["response"] = resp.rstrip() + footer
    # Append the REAL self-data records verbatim (profile / appointments / mood /
    # screening / experts). The DB is the source of truth — append unless the
    # responder already reproduced the block, so the user always sees actual data.
    facts_block = _facts_footer(state)
    if facts_block:
        first_line = facts_block.strip().splitlines()[0]
        for d in drafts:
            resp = d.get("response") or ""
            if resp and first_line not in resp:
                d["response"] = resp.rstrip() + facts_block
    # Append the optional screening check-in CTA (if the agent suggested one).
    screen_cta = "" if listen_only else _screening_footer(state)
    if screen_cta:
        for d in drafts:
            resp = d.get("response") or ""
            low = resp.lower()
            if resp and "screening page" not in low and "check-in" not in low:
                d["response"] = resp.rstrip() + screen_cta
    return {
        "outcome": "drafts",
        "drafts": drafts,
        "retrieved": state["retrieved"],
        "analysis": state.get("analysis") or {},
        "gen_mode": gen.get("mode", "modal"),
        "prompt_hash": prompt_builder.prompt_hash(messages),
        "plan": state.get("plan"),
        "self_critique": state.get("self_critique"),
        "recommendations": state.get("recommendations"),
        "forced_enrichment": state.get("forced_enrichment", False),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Context curation — keep the ORCHESTRATOR's context short and clean.
#
# A 7B degrades fast when its context fills with long, noisy tool observations.
# What the orchestrator echoes back to itself does NOT need the full result: the
# real retrieved passages live in state["retrieved"] (used at generation), and
# the full text is kept in the trace. So we feed the model only a compact view —
# enough to decide the next step — capping length and trimming retrieval dumps to
# the first couple of passages. Pure upside: nothing the final reply needs is lost.
# ─────────────────────────────────────────────────────────────────────────────
_OBS_CAP = 500


def _first_tool(resp: Dict) -> str:
    tc = (resp or {}).get("tool_calls") or []
    return tc[0].get("name") if tc else "_prose"


def _vote_decide(messages: List[Dict], tools: List[Dict]):
    """Self-consistency: sample the orchestrator N times and pick the MAJORITY
    first-tool decision (a 7B routes more reliably by vote). Returns
    (response, confidence in [0,1]). N=1 → a single call, confidence 1.0 — the
    default, byte-identical to the old behaviour."""
    n = max(1, int(getattr(settings, "agent_self_consistency", 1) or 1))
    if n <= 1:
        return agent_client.chat(messages, tools=tools), 1.0
    samples = [r for r in (agent_client.chat(messages, tools=tools)
                           for _ in range(n)) if r is not None]
    if not samples:
        return None, 0.0
    votes = Counter(_first_tool(r) for r in samples)
    winner, count = votes.most_common(1)[0]
    chosen = next(r for r in samples if _first_tool(r) == winner)
    return chosen, count / len(samples)


def _low_confidence_escalation(conf: float, trace: List[Dict],
                               step: int) -> Optional[Dict]:
    """Confidence gate: when the terminal decision was reached with low vote
    agreement, route to a clinician rather than auto-answering. Safe (escalate
    only RAISES caution). Inactive unless agent_confidence_floor > 0 (and voting
    is on, which is the only way conf < 1.0)."""
    floor = float(getattr(settings, "agent_confidence_floor", 0.0) or 0.0)
    if floor <= 0 or conf >= floor:
        return None
    metrics.inc("cbt_agent_lowconf_escalate_total")
    trace.append({"step": step, "tool": "escalate_to_clinician",
                  "arguments": {"reason": "low orchestrator confidence"},
                  "note": f"forced escalate (confidence {conf:.2f} < {floor})"})
    return {"outcome": "escalate",
            "escalate_reason": ("The assistant was uncertain how best to help "
                                "here; a clinician will follow up to be safe."),
            "trace": trace}


def _curate_observation(name: str, text: str) -> str:
    text = (text or "").strip()
    if name == "retrieve_cbt_knowledge":
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) > 1:
            head, passages = lines[:1], [ln[:160] for ln in lines[1:3]]
            extra = len(lines) - 1 - len(passages)
            tail = [f"(+{extra} more passages retrieved)"] if extra > 0 else []
            return "\n".join(head + passages + tail)
    if len(text) > _OBS_CAP:
        return text[:_OBS_CAP].rstrip() + " …"
    return text


# ─────────────────────────────────────────────────────────────────────────────
# ReAct loop
# ─────────────────────────────────────────────────────────────────────────────
def run_agent(*, user_scrubbed: str,
              intake: Optional[Dict],
              session_ctx: Optional[Dict],
              analysis: Optional[Dict],
              severity: str,
              triage_level: str,
              user_id: str,
              n_responses: int,
              temperature: float,
              risk_level: str = "normal") -> Optional[Dict]:
    """
    Run the agentic loop for an L2/L3 message.

    Returns one of:
      {"outcome": "drafts", "drafts": [...], "trace": [...], ...}
      {"outcome": "needs_clarification", "clarification": str, "trace": [...]}
      {"outcome": "escalate", "escalate_reason": str, "trace": [...]}
    or None when the orchestrator is unavailable (caller falls back to the
    fixed pipeline).
    """
    if not agent_client.available():
        return None

    state = {
        "user_scrubbed": user_scrubbed,
        "intake": intake,
        "session_ctx": session_ctx,
        "analysis": analysis,          # may be pre-computed; tool can refresh
        "severity": severity,
        "risk_level": risk_level,      # locked — drives risk-aware retrieval
        "user_id": user_id,
        "retrieved": [],
        "recommendations": {"lessons": [], "resources": []},
        "facts": [],   # verbatim self-data blocks (profile/appointments/…)
    }

    # Listen-only mode: the client asked to simply be heard. The orchestrator
    # must NOT bounce a clarifying question back — it goes straight to a warm
    # validation. (Genuine risk still escalates via _risk_escalation first.)
    listen_only = "just_listen" in ((session_ctx or {}).get("style_prefs") or [])

    task = (
        f"[TRIAGE] level={triage_level} severity={severity}\n"
        f"[CLIENT MESSAGE]\n{user_scrubbed}\n\n"
        "Decide how to handle this. Gather context with tools, then take one "
        "terminal action.")
    if listen_only:
        task += ("\n\n[LISTEN-ONLY MODE] The client asked to simply be HEARD, "
                 "not questioned. Do NOT call ask_clarification and do NOT ask "
                 "questions. Go straight to generate_cbt_response with a brief, "
                 "warm validation that reflects their feeling.")
    messages: List[Dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    trace: List[Dict] = []
    non_terminal_tools = {
        "retrieve_cbt_knowledge": _tool_retrieve,
        "recall_session_memory": _tool_recall_memory,
        "analyze_cognition": _tool_analyze,
        "plan_session": _tool_plan_session,
        "recommend_lesson": _tool_recommend_lesson,
        "recommend_resource": _tool_recommend_resource,
        "summarize_progress": _tool_summarize_progress,
        "get_my_data": _tool_get_my_data,
        "list_psychologists": _tool_list_psychologists,
        "suggest_screening": _tool_suggest_screening,
    }

    for step in range(settings.agent_max_steps):
        resp, step_conf = _vote_decide(messages, TOOL_SCHEMAS)
        if resp is None:
            # Orchestrator died mid-loop. If we already gathered context,
            # still produce a response; otherwise fall back entirely.
            if state["retrieved"] or state.get("analysis"):
                log.info("Agent orchestrator dropped — forcing generate")
                esc = _risk_escalation(state, trace, step)
                if esc is not None:
                    return esc
                _ensure_grounded(state, trace, step)
                result = _do_generate({}, state, n_responses, temperature)
                result["trace"] = trace + [{"step": step, "tool": "_forced_generate",
                                            "note": "orchestrator unreachable"}]
                return result
            return None

        tool_calls = resp.get("tool_calls") or []

        if not tool_calls:
            # Model replied in prose instead of calling a tool. Nudge it once
            # toward a terminal action; record its message for context.
            metrics.inc("cbt_agent_prose_total")
            content = (resp.get("content") or "").strip()
            messages.append({"role": "assistant",
                             "content": content[:_OBS_CAP]})
            messages.append({"role": "user", "content":
                             "Choose a terminal action now: call "
                             "generate_cbt_response, ask_clarification, or "
                             "escalate_to_clinician."})
            trace.append({"step": step, "tool": "_prose",
                          "content": content[:200]})
            continue

        # Run context-gathering tools BEFORE any terminal action in the same
        # batch — the model sometimes lists generate_cbt_response first, which
        # would otherwise generate before retrieve/analyze had run.
        tool_calls.sort(key=lambda c: 1 if c.get("name") in _TERMINAL else 0)

        # Execute calls in order; stop at the first terminal action.
        for call in tool_calls:
            name = call.get("name", "")
            args = call.get("arguments") or {}

            metrics.inc("cbt_agent_tool_calls_total", tool=name or "unknown")
            missing = _missing_args(name, args)
            if missing:
                metrics.inc("cbt_agent_bad_args_total", tool=name or "unknown")

            if name == "generate_cbt_response":
                metrics.inc("cbt_agent_terminal_total", action=name)
                esc = _risk_escalation(state, trace, step)
                if esc is not None:
                    return esc
                low = _low_confidence_escalation(step_conf, trace, step)
                if low is not None:
                    return low
                grounded = bool(state.get("retrieved"))
                _ensure_grounded(state, trace, step)   # never generate ungrounded
                result = _do_generate(args, state, n_responses, temperature)
                trace.append({"step": step, "tool": name, "arguments": args,
                              "model_grounded": grounded})
                result["trace"] = trace
                return result

            if name == "ask_clarification":
                metrics.inc("cbt_agent_terminal_total", action=name)
                esc = _risk_escalation(state, trace, step)
                if esc is not None:
                    return esc
                # Listen-only mode never bounces a question back — validate
                # instead. Safety (above) still escalates genuine risk first.
                if listen_only:
                    low = _low_confidence_escalation(step_conf, trace, step)
                    if low is not None:
                        return low
                    _ensure_grounded(state, trace, step)
                    result = _do_generate({}, state, n_responses, temperature)
                    trace.append({"step": step, "tool": "ask_clarification→generate",
                                  "note": "listen-only: validated instead of asking"})
                    result["trace"] = trace
                    return result
                low = _low_confidence_escalation(step_conf, trace, step)
                if low is not None:
                    return low
                q = (args.get("question") or
                     "Could you tell me a bit more about what's been "
                     "happening?").strip()
                trace.append({"step": step, "tool": name, "arguments": args,
                              "missing_args": missing})
                return {"outcome": "needs_clarification",
                        "clarification": q, "trace": trace}

            if name == "escalate_to_clinician":
                metrics.inc("cbt_agent_terminal_total", action=name)
                reason = (args.get("reason") or
                          "Agent flagged possible elevated risk.").strip()
                trace.append({"step": step, "tool": name, "arguments": args,
                              "missing_args": missing})
                return {"outcome": "escalate",
                        "escalate_reason": reason, "trace": trace}

            # Non-terminal tool
            fn = non_terminal_tools.get(name)
            if fn is None:
                result_text = f"Unknown tool: {name}"
                metrics.inc("cbt_agent_unknown_tool_total", tool=name or "unknown")
            else:
                result_text = fn(args, state)
            messages.append({"role": "assistant", "content": "",
                             "tool_calls": [call]})
            messages.append({"role": "tool", "name": name,
                             "content": _curate_observation(name, result_text)})
            trace.append({"step": step, "tool": name, "arguments": args,
                          "missing_args": missing,
                          "result": result_text[:200]})

    # Step budget exhausted with no terminal action → force a response so the
    # client is never left hanging.
    log.info("Agent hit step budget (%d) — forcing generate",
             settings.agent_max_steps)
    esc = _risk_escalation(state, trace, settings.agent_max_steps)
    if esc is not None:
        return esc
    _ensure_grounded(state, trace, settings.agent_max_steps)
    result = _do_generate({}, state, n_responses, temperature)
    result["trace"] = trace + [{"step": settings.agent_max_steps,
                                "tool": "_forced_generate",
                                "note": "step budget exhausted"}]
    return result
