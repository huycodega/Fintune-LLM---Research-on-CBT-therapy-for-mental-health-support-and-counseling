"""
Chat endpoint — wires the FULL pipeline v4:

  rate-limit  →  load intake  →  safety triage (.pt)
              →  L0: crisis screen, no AI
              →  L1: NO draft, push to clinician queue
              →  L2/L3 continue:
                     analysis  →  retrieval (Qdrant + rerank)
                              →  prompt build (PII scrubbed)
                              →  Modal LLM (or mock, circuit-broken)
                              →  parse + grounding + pre-flight
                              →  L2: pending review
                              →  L3: auto-sent
"""
import hashlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core import auth, audit as audit_mod
from app.core.config import settings
from app.core.crypto import encrypt_phi, decrypt_str
from app.db import models
from app.db.session import get_db
from app.schemas.api import ChatIn
from app.services import (
    safety_gate, analyzer, retrieval, prompt_builder, llm_client,
    post_process, preflight, pii_scrubber, redis_client as rc, calibration,
    metrics, session_memory, agent, agent_client, user_memory, triage_log,
    moderation_store, scope_router, self_data, summarizer, actions, warmup,
)


router = APIRouter(prefix="/api")

# how many prior turns of THIS thread to feed back as multi-turn context
_HISTORY_TURNS = 6


@router.post("/warmup")
def warmup_modal(user: dict = Depends(auth.current_user)):
    """Fired when the Chat page opens: wake the Modal GPU containers while the
    user is still typing their first message. Best-effort, cluster-deduped."""
    return {"started": warmup.fire()}


def _resolve_conversation(db, user_id, conversation_id, first_message):
    """Return an owned Conversation, creating one if conversation_id is None.
    Sets the title from the first message when the thread is still untitled."""
    if conversation_id:
        c = db.query(models.Conversation).filter_by(id=conversation_id).first()
        if not c or str(c.user_id) != str(user_id):
            raise HTTPException(404, "Conversation not found")
    else:
        c = models.Conversation(user_id=user_id, title="New conversation")
        db.add(c); db.flush()
    if c.title in (None, "", "New conversation"):
        c.title = (first_message.strip()[:60] or "New conversation")
    c.updated_at = datetime.now(timezone.utc)
    return c


def _thread_history(db, conversation_id):
    """Last N turns of this thread as [{user, reply}] for prompt context."""
    rows = (db.query(models.Session)
              .filter_by(conversation_id=conversation_id)
              .order_by(models.Session.created_at.asc())
              .all())
    rows = rows[-_HISTORY_TURNS:]
    hist = []
    for s in rows:
        reply = (decrypt_str(s.final_reply_enc)
                 if s.final_reply_enc else "")
        hist.append({"user": decrypt_str(s.user_input_enc), "reply": reply})
    return hist


CRISIS_RESOURCES = {
    "US": {"name": "988 Suicide & Crisis Lifeline", "phone": "988",
            "url": "https://988lifeline.org", "available": "24/7"},
    "INT": {"name": "Find A Helpline (international)",
             "phone": "https://findahelpline.com",
             "url": "https://findahelpline.com", "available": "varies"},
}


def _sla_for(level: str) -> datetime:
    base = datetime.now(timezone.utc)
    return base + timedelta(minutes=15 if level == "L1" else 60)


# Re-ask questions ("what thoughts come up?", "tell me more") AFTER the client
# already named their thoughts read as not-listening. The 7B produces them
# stochastically, so across n drafts we rank the ones that ADVANCE the work
# above the ones that ask again — deterministic, no extra model call.
# Scored per SENTENCE: a sentence only counts when it asks for the client's
# EXISTING material (_REASK_CORE) and is not an advancing technique question
# (_ADVANCE_OK: evidence, worst case, likelihood, hypotheticals, reframe,
# friend-perspective, action step) — those are legitimate next steps.
_REASK_CORE = re.compile(
    r"what (specific )?(thoughts?|feelings?|emotions?|fears?|worries|concerns?)\b|"
    r"what (goes|runs) through your (mind|head)|"
    r"\btell me more\b|\bshare more\b|"
    r"can you (tell|describe|share|identify|pick out|give me an example)|"
    r"when (do|does|did)?\s?(it|they|these|those|that|the)\b"
    r".{0,40}(come up|appear|happen|start)", re.I)
_ADVANCE_OK = re.compile(
    r"\bevidence\b|worst case|worst that could|how likely|\bimagine\b|"
    r"what if\b|\binstead\b|balanced|alternative|reframe|"
    r"a friend\b|someone you care|willing to|could you try|next step|"
    r"for and against", re.I)


def _reask_count(resp: str) -> int:
    n = 0
    for sent in re.split(r"(?<=[.!?])\s+", resp or ""):
        s = sent.strip()
        if s and _REASK_CORE.search(s) and not _ADVANCE_OK.search(s):
            n += 1
    return n


# The client explicitly asks for a delivered analysis — any question in the
# reply is a dodge on such turns, so drafts are ranked by TOTAL question count.
_DELIVERY_REQ = re.compile(
    r"\b(walk me through|how likely|what are the odds|just tell me|"
    r"tell me (straight|directly|honestly)|"
    r"give me the (odds|evidence|breakdown|steps)|"
    r"break (it|this|that) down( for me)?|lay it out)\b", re.I)


def _question_count(resp: str) -> int:
    return sum(1 for s in re.split(r"(?<=[.!?])\s+", resp or "")
               if s.strip().endswith("?"))


# ── Greeting fast-path ───────────────────────────────────────────────────────
# A standalone greeting carries no risk content, so we answer it instantly with
# a warm opener instead of spinning up the safety gate + agent. The whole
# message must BE the greeting (anchored) — "hi I want to disappear" is NOT a
# greeting and goes through the full pipeline.
_GREETING_PAT = re.compile(
    r"^\s*(hi+|hey+|hello+|helo+|heya|hiya|yo|hai|hallo|alo+|sup|"
    r"good\s*(morning|afternoon|evening)|gm|"
    r"ch[aà]o|xin\s*ch[aà]o)"
    r"[\s,.!~]*(there|bot|mindcare|ai|friend|b[aạ]n|nh[eé])?[\s,.!?~]*$",
    re.IGNORECASE,
)


def _info_reply(db, u, infos):
    """Build the direct answer for one or more factual info intents.

    Returns (text, cards): `text` is the combined reply (real DB records only,
    stored for history); `cards` is a list of {kind, items} the chat UI renders
    as tappable items (lessons → open, psychologists → book, appointments).
    Returns ("", []) on total failure.
    """
    texts, cards = [], []
    seen = set()
    for info in infos:
        if info in seen:
            continue
        seen.add(info)
        try:
            if info in ("meta", "offtopic"):
                texts.append(scope_router.reply_for(info))
            elif info == "profile":
                texts.append(self_data.profile(db, u.id))
            elif info == "mood":
                texts.append(self_data.mood(db, u.id))
            elif info == "screening":
                texts.append(self_data.screening(db, u.id))
            elif info == "progress":
                texts.append(self_data.lesson_progress(db, u.id))
            elif info == "recall":
                texts.append(self_data.recall(db, u.id))
            elif info == "privacy":
                texts.append(
                    "Your privacy matters here. Your messages are encrypted, "
                    "and only a clinician reviews sensitive cases — nothing is "
                    "shared otherwise. You can hide conversations from your "
                    "history, download a copy of your data, or permanently "
                    "delete your whole account anytime from Settings. One "
                    "honest note: records a clinician has already reviewed are "
                    "kept for safety unless you delete your account.")
            elif info == "clinical_boundary":
                texts.append(
                    "I'm not able to give a medical diagnosis or recommend "
                    "medication — those need a licensed professional who can "
                    "properly assess you, and a clinician on our team can help "
                    "with that. What I can do is help you understand and work "
                    "through what you're feeling. What's been going on lately?")
            elif info == "role_boundary":
                texts.append(
                    "I'm not a licensed therapist or clinician — I'm MindCare "
                    "AI, a CBT-based support companion, so I can't replace "
                    "professional therapy. But I can listen and help you work "
                    "through stress, anxiety, and low mood with evidence-based "
                    "tools, and a real clinician reviews anything sensitive. "
                    "What's on your mind?")
            elif info == "no_file":
                texts.append(
                    "I can't open or read uploaded files, documents, or case "
                    "notes — I only see the messages you type here. If there's "
                    "something in a document you'd like help with, feel free to "
                    "paste the relevant part and we'll look at it together.")
            elif info == "other_user":
                texts.append(
                    "I can only access your own records — I'm not able to view "
                    "anyone else's data. If it helps, I can show you your own "
                    "screening results, appointments, or mood history.")
            elif info == "vague_cbt":
                texts.append(
                    "Happy to help with CBT! Would you like a quick explanation "
                    "of what it is, a practical exercise to try, or help applying "
                    "it to something specific you're going through?")
            elif info == "vague":
                texts.append(
                    "I'm really glad you reached out. Could you tell me a bit "
                    "more about what's going on — even one sentence about what "
                    "feels hardest right now helps me support you. And if "
                    "anything ever feels urgent or unsafe, you can reach 988 any "
                    "time.")
            elif info == "appointments":
                items = self_data.appointments_cards(db, u.id)
                texts.append(self_data.appointments(db, u.id))
                if items:
                    cards.append({"kind": "appointments", "items": items})
            elif info == "lessons":
                items = self_data.lessons_cards(db)
                texts.append(self_data.lessons(db))
                if items:
                    cards.append({"kind": "lessons", "items": items})
            elif info == "resources":
                items = self_data.resources_cards(db)
                texts.append(self_data.resources(db))
                if items:
                    cards.append({"kind": "resources", "items": items})
            elif info == "psychologists":
                items = self_data.psychologists_cards(db)
                texts.append(self_data.psychologists(db))
                if items:
                    cards.append({"kind": "psychologists", "items": items})
        except Exception:
            continue
    return "\n\n".join(t for t in texts if t), cards


def _is_greeting(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 40:
        return False
    return bool(_GREETING_PAT.match(t))


def _greeting_reply(mem: dict) -> str:
    """Memory-aware opener. Returning user → recall; new user → simple welcome."""
    mem = mem or {}
    turns = mem.get("turn_count", 0) or 0
    themes = [t for t in (mem.get("recurring_themes") or []) if t][:2]
    if turns > 0:
        if themes:
            return (
                "Hey, good to see you again — I'm right here. Last time we were "
                f"working through {', '.join(themes)}. How have things been with "
                "that since we last talked?"
            )
        return (
            "Hey, good to see you again — I'm right here. How have you been "
            "since we last talked? Anything you'd like to pick up on today?"
        )
    return (
        "Hi, I'm really glad you're here. I'm your CBT companion — a safe, "
        "private space to talk through whatever's on your mind. What would you "
        "like to start with today?"
    )


# Greetings answer instantly without touching Modal, so we use the moment to
# warm the scale-to-zero GPU services in the BACKGROUND: by the time the user
# sends their first real message, safety/llm/agent containers are already hot.
# Throttled in-process so repeated greetings don't re-trigger warm-ups.
_log = logging.getLogger("cbt")
_last_warm = 0.0
_WARM_COOLDOWN = 240  # seconds


def _warm_modal() -> None:
    global _last_warm
    now = time.time()
    if now - _last_warm < _WARM_COOLDOWN:
        return
    _last_warm = now
    _log.info("greeting → warming Modal GPU services in background")
    t0 = time.time()
    tiny = [{"role": "user", "content": "hi"}]
    try:
        safety_gate.assess("hi", history=[])
    except Exception:
        pass
    try:
        llm_client.generate(tiny, n=1, temperature=0.1)
    except Exception:
        pass
    try:
        if agent_client.available():
            agent_client.chat(tiny, tools=[], max_new_tokens=8)
    except Exception:
        pass
    _log.info("greeting warm-up done in %.1fs", time.time() - t0)


@router.post("/chat")
def chat(body: ChatIn, request: Request,
          background_tasks: BackgroundTasks,
          user: dict = Depends(auth.current_user),
          db: Session = Depends(get_db)):
    if user["role"] != "user":
        raise HTTPException(403, "Only user role may call /chat")

    # ---- preconditions ----
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    if u.consent_at is None:
        raise HTTPException(403, "Consent required (call /api/consent first)")
    # Intake is OPTIONAL: a user who skipped it can chat right away — context
    # then builds up from conversation memory instead (user_memory + summary).
    # Session.intake_id is nullable, so no placeholder row is needed.
    intake = (db.query(models.IntakeForm)
                .filter_by(user_id=u.id)
                .order_by(models.IntakeForm.created_at.desc())
                .first())
    intake_id = intake.id if intake else None

    ip = auth.client_ip(request)
    rc.rate_limit_check(str(u.id), ip)

    text = body.message.strip()
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # ---- resolve the thread FIRST so the safety gate can see prior turns ----
    convo = _resolve_conversation(db, u.id, body.conversation_id, text)

    # ---- UI "just listen" toggle: sync the DURABLE per-thread state so the
    # responder holds advice for the whole thread. Lives on the Conversation
    # row (Postgres) — a Redis flag died on every redeploy and silently
    # reverted the mode. Does NOT consume a turn. None = leave as-is. ----
    if body.listen_only is not None:
        convo.listen_mode = bool(body.listen_only)
    elif convo.listen_mode and scope_router.wants_guidance(text):
        # No toggle change this turn, but the client explicitly asked for help →
        # lift listen-only so they actually get guidance. (A physical UI toggle
        # re-asserts itself on the next message, so it stays authoritative.)
        convo.listen_mode = False

    # ---- Greeting fast-path: instant, memory-aware "hello" ----
    # Skips the safety gate + agent (no Modal call) so a bare "hi" returns
    # immediately. Returning users get a recall-flavoured greeting; new users a
    # simple welcome. We do NOT count this as a real turn (no user_memory
    # update) so it never makes a brand-new user look "returning".
    if _is_greeting(text):
        mem = user_memory.load_for_prompt(db, u.id)
        greeting = _greeting_reply(mem)
        user_message = moderation_store.record_user_message(
            db, convo, u, text, "L3")
        sess = models.Session(
            user_id=u.id, intake_id=intake_id, conversation_id=convo.id,
            user_input_enc=encrypt_phi(text), user_input_hash=text_hash,
            triage_level="L3", triage_reason="greeting", severity="low",
            confidence=1.0, status="auto_sent",
            final_reply_enc=encrypt_phi(greeting), final_technique="greeting",
            analysis={"greeting": True,
                      "memory_aware": bool(mem.get("turn_count"))},
            completed_at=datetime.now(timezone.utc),
        )
        db.add(sess); db.flush()
        moderation_store.record_ai_message(
            db, convo, user_message, greeting, "L3", "not_required",
            confidence=1.0, model_name="greeting")
        # Warm the GPU services in the background so the first real message is fast.
        background_tasks.add_task(_warm_modal)
        return {
            "session_id": str(sess.id),
            "conversation_id": str(convo.id),
            "outcome": "answered",
            "triage": {"triage_level": "L3", "reason": "greeting",
                       "severity": "low", "confidence": 1.0},
            "final": {"technique": "greeting", "response": greeting},
            "drafts": [{"idx": 0, "technique": "greeting",
                        "response": greeting}],
            "mode": "greeting",
        }

    # ---- Jailbreak / prompt-injection gate (clean refusal, not crisis framing) ----
    # A clear jailbreak with NO self-harm content gets a direct refusal instead of
    # being over-triaged into the crisis flow. Guarded by has_acute_risk, so a real
    # crisis (even one worded as a jailbreak) still takes the safety path below.
    if (settings.scope_router_enabled
            and scope_router._JAILBREAK_PAT.search(text)
            and not safety_gate.has_acute_risk(text)):
        reply = (
            "I can't share my internal instructions or set aside my safety "
            "guidelines — they're here to keep you safe. But I'm genuinely glad "
            "you're here: tell me what's going on for you and we'll work through "
            "it together.")
        user_message = moderation_store.record_user_message(db, convo, u, text, "L3")
        sess = models.Session(
            user_id=u.id, intake_id=intake_id, conversation_id=convo.id,
            user_input_enc=encrypt_phi(text), user_input_hash=text_hash,
            triage_level="L3", triage_reason="jailbreak_refused", severity="low",
            confidence=1.0, status="answered",
            final_reply_enc=encrypt_phi(reply), final_technique="safety_boundary",
            analysis={"jailbreak": True},
            completed_at=datetime.now(timezone.utc))
        db.add(sess); db.flush()
        moderation_store.record_ai_message(
            db, convo, user_message, reply, "L3", "not_required",
            confidence=1.0, model_name="jailbreak_gate")
        audit_mod.audit(db, action="jailbreak_refused", actor=user, ip=ip,
                         resource_type="session", resource_id=sess.id, detail={})
        return {
            "session_id": str(sess.id), "conversation_id": str(convo.id),
            "outcome": "answered",
            "triage": {"triage_level": "L3", "reason": "jailbreak_refused",
                       "severity": "low", "confidence": 1.0},
            "final": {"technique": "safety_boundary", "response": reply},
            "drafts": [{"idx": 0, "technique": "safety_boundary",
                        "response": reply}],
            "mode": "jailbreak_gate",
        }

    # Prior CLIENT turns of this thread (decrypted), most recent last. Reading
    # each message in isolation caused L1 over-triage with hallucinated reasons;
    # giving the model context fixes that and (verified) still escalates a
    # regex-evading crisis. The regex hard-override stays as the backstop.
    prior_rows = (db.query(models.Session)
                    .filter_by(conversation_id=convo.id)
                    .order_by(models.Session.created_at.asc())
                    .all())
    turn_index = len(prior_rows)
    history = [decrypt_str(r.user_input_enc) for r in prior_rows
               if r.user_input_enc]
    if settings.safety_use_context and settings.safety_context_turns:
        safety_history = history[-settings.safety_context_turns:]
    else:
        safety_history = []

    # Cache key folds in the context — the same words in a different thread can
    # triage differently now, so they must not collide on a stale decision.
    if safety_history:
        triage_key = hashlib.sha256(
            ("\n".join(safety_history) + " " + text).encode("utf-8")
        ).hexdigest()
    else:
        triage_key = text_hash

    # ---- safety triage with cache ----
    cached = rc.triage_cache_get(triage_key)
    if cached:
        triage = cached
        metrics.inc("cbt_triage_cache_total", outcome="hit")
    else:
        with metrics.Timer("cbt_stage_latency_seconds", stage="triage"):
            triage = safety_gate.assess(text, history=safety_history)
        # Post-hoc temperature scaling — fixes overconfidence.
        # Persist BOTH raw and calibrated so audit/eval can replay.
        raw_conf = float(triage.get("confidence", 0.0))
        cal_conf = calibration.calibrate_confidence(raw_conf)
        triage["confidence_raw"] = raw_conf
        triage["confidence"] = cal_conf
        triage["calibration_T"] = calibration.get_temperature()
        rc.triage_cache_set(triage_key, triage)
        metrics.inc("cbt_triage_cache_total", outcome="miss")

    level = triage["triage_level"]
    metrics.inc("cbt_triage_level_total", level=level)

    # ---- structured triage log (foundation for the eval set) ----
    # Logged for EVERY level — L0/L1 included, since those are exactly the
    # decisions we want to audit for false positives. No raw PHI: a hash plus
    # a PII-scrubbed preview only.
    triage_log.record(
        text_hash=text_hash,
        preview=pii_scrubber.scrub(text),
        triage=triage,
        user_id=str(u.id),
        conversation_id=str(convo.id),
        turn_index=turn_index,
        history_len=len(safety_history),
    )

    base = dict(
        user_id=u.id, intake_id=intake_id, conversation_id=convo.id,
        user_input_enc=encrypt_phi(text),
        user_input_hash=text_hash,
        triage_level=level,
        triage_reason=triage["reason"],
        severity=triage["severity"],
        confidence=triage["confidence"],
    )
    # New per-message source of truth. Legacy sessions remain dual-written
    # during the compatibility window.
    user_message = moderation_store.record_user_message(
        db, convo, u, text, level)

    # ---- L0: Emergency — NO AI ----
    if level == "L0":
        sess = models.Session(**base, status="crisis", analysis={})
        db.add(sess); db.flush()
        moderation_store.enqueue(db, convo, user_message, level)
        audit_mod.audit(db, action="triage_L0_crisis", actor=user,
                         ip=ip, resource_type="session", resource_id=sess.id,
                         detail=triage)
        return {
            "session_id": str(sess.id),
            "conversation_id": str(convo.id),
            "outcome": "crisis",
            "triage": triage,
            "crisis_resources": CRISIS_RESOURCES,
            "message": ("I'm really glad you told me this — what you're "
                         "carrying sounds incredibly heavy, and you don't have "
                         "to hold it on your own. Because your safety matters "
                         "most, I won't send an automated reply here. Please "
                         "reach out to one of the resources below right now — "
                         "real people are ready to listen, any time of day."),
        }

    # ---- L1: High risk — NO draft, push to clinician ----
    if level == "L1":
        sess = models.Session(**base, status="pending_review", analysis={})
        db.add(sess); db.flush()
        db.add(models.ReviewQueue(
            session_id=sess.id, triage_level=level, priority=1,
            sla_due_at=_sla_for(level)))
        moderation_store.enqueue(db, convo, user_message, level)
        audit_mod.audit(db, action="triage_L1_no_ai_pushed", actor=user,
                         ip=ip, resource_type="session", resource_id=sess.id,
                         detail=triage)
        return {
            "session_id": str(sess.id),
            "conversation_id": str(convo.id),
            "outcome": "pending_review",
            "triage": triage, "crisis_resources": CRISIS_RESOURCES,
            "message": ("Thank you for trusting me with something this hard. "
                         "What you shared matters, and I want a real person to "
                         "give it the care it deserves — a clinician is "
                         "reviewing your message now and will follow up. If "
                         "anything feels urgent while you wait, the resources "
                         "below are here for you any time."),
        }

    # ---- Preference gate: remember "be brief / don't ask / be direct" ----
    # Store the style preference for this thread and acknowledge; future turns
    # honour it (session_ctx.style_prefs → responder prompt). L2/L3 only.
    if level in ("L2", "L3"):
        prefs_now = scope_router.detect_preference(text)
        # Only acknowledge-and-stop when the message is essentially JUST the
        # instruction ("be brief", "just listen"). When the same message also
        # carries a real disclosure, we still store the preference but fall
        # through so the responder actually replies — honouring it — instead of
        # sending a bare "Got it" over a heartfelt paragraph.
        if prefs_now:
            if "just_listen" in prefs_now:
                convo.listen_mode = True     # durable per-thread state (DB)
            merged = sorted((set(rc.chat_prefs_get(str(convo.id)))
                             | set(prefs_now)) - {"just_listen"})
            rc.chat_prefs_set(str(convo.id), merged)
            if convo.listen_mode:
                merged = sorted(set(merged) | {"just_listen"})
        if prefs_now and len(text.split()) <= 12:
            bits = []
            if "brief" in prefs_now:
                bits.append("keep my replies short")
            if "direct" in prefs_now:
                bits.append("get straight to the point")
            if "no_questions" in prefs_now:
                bits.append("hold back on the questions")
            if "just_listen" in prefs_now:
                bits.append("just listen and hold the advice")
            # A "just listen" request shouldn't be answered with a question.
            closing = ("I'm here — take your time."
                       if ("just_listen" in prefs_now or "no_questions" in prefs_now)
                       else "What's on your mind?")
            ack = ("Got it — I'll " + (", and ".join(bits) or "adjust my style")
                   + " from now on. " + closing)
            sess = models.Session(
                **base, status="answered", analysis={"style_prefs": merged},
                final_reply_enc=encrypt_phi(ack), final_technique="preference",
                completed_at=datetime.now(timezone.utc))
            db.add(sess); db.flush()
            moderation_store.record_ai_message(
                db, convo, user_message, ack, level, "not_required",
                confidence=triage.get("confidence"), model_name="preference_gate")
            audit_mod.audit(db, action="style_preference", actor=user, ip=ip,
                             resource_type="session", resource_id=sess.id,
                             detail={"prefs": merged})
            return {
                "session_id": str(sess.id), "conversation_id": str(convo.id),
                "outcome": "answered", "triage": triage,
                "final": {"technique": "preference", "response": ack},
                "drafts": [{"idx": 0, "technique": "preference", "response": ack}],
                "mode": "preference_gate",
                "listen_active": "just_listen" in merged,
            }

    # ---- Action gate: "do something" requests (write, with confirm) ----
    # Detect log-mood / cancel-appointment / mark-lesson-done / start-screening
    # and return confirm-cards — NOTHING is written here; the actual write only
    # happens when the user taps Confirm (calls the existing REST endpoints).
    # Runs BEFORE the info-gate so "cancel my appointment" isn't read as a list.
    # Guards: L2/L3 only, no distress signal, safety regex clears L0/L1.
    if settings.action_gate_enabled and level in ("L2", "L3"):
        akind = actions.detect(text)
        if (akind and not scope_router._DISTRESS_VETO.search(text.lower())
                and safety_gate._heuristic(text).get("triage_level")
                not in ("L0", "L1")):
            atext, acts = actions.propose(db, u.id, akind, text)
            if atext:
                sess = models.Session(
                    **base, status="answered",
                    analysis={"action_intent": akind},
                    final_reply_enc=encrypt_phi(atext),
                    final_technique=f"action_{akind}"[:60],
                    completed_at=datetime.now(timezone.utc))
                db.add(sess); db.flush()
                moderation_store.record_ai_message(
                    db, convo, user_message, atext, level, "not_required",
                    confidence=triage.get("confidence"), model_name="action_gate")
                audit_mod.audit(db, action=f"action_{akind}", actor=user, ip=ip,
                                 resource_type="session", resource_id=sess.id,
                                 detail={"action_intent": akind,
                                         "n_options": len(acts)})
                return {
                    "session_id": str(sess.id),
                    "conversation_id": str(convo.id),
                    "outcome": "answered", "triage": triage,
                    "final": {"technique": f"action_{akind}"[:60],
                              "response": atext},
                    "drafts": [{"idx": 0, "technique": f"action_{akind}"[:60],
                                "response": atext}],
                    "actions": acts,
                    "mode": "action_gate",
                }

    # ---- Direct-answer gate: factual self-data / meta / off-topic ----
    # A benign informational question ("who am I", "my appointments", "what
    # lessons are there", "how does MindCare work") should be answered DIRECTLY
    # from the database — not turned into a CBT draft for clinician review. Runs
    # on L2/L3 (L0/L1 already returned). Strict guards keep it safe: it fires
    # only on an EXPLICIT info pattern with NO distress signal AND a clean safety
    # regex (not L0/L1), so a genuine moderate-risk message is never intercepted.
    if settings.scope_router_enabled and level in ("L2", "L3"):
        infos = (scope_router.info_intents_smart(text)
                 if settings.scope_router_semantic
                 else scope_router.info_intents(text))
        if infos and safety_gate._heuristic(text).get("triage_level") \
                not in ("L0", "L1"):
            reply, cards = _info_reply(db, u, infos)
            if reply:
                tech = "info_" + "_".join(infos)
                sess = models.Session(
                    **base, status="answered",
                    analysis={"info_intents": infos},
                    final_reply_enc=encrypt_phi(reply),
                    final_technique=tech[:60],
                    completed_at=datetime.now(timezone.utc))
                db.add(sess); db.flush()
                moderation_store.record_ai_message(
                    db, convo, user_message, reply, level, "not_required",
                    confidence=triage.get("confidence"), model_name="info_gate")
                audit_mod.audit(db, action="info_gate", actor=user, ip=ip,
                                 resource_type="session", resource_id=sess.id,
                                 detail={"info_intents": infos})
                return {
                    "session_id": str(sess.id),
                    "conversation_id": str(convo.id),
                    "outcome": "answered", "triage": triage,
                    "final": {"technique": tech[:60], "response": reply},
                    "drafts": [{"idx": 0, "technique": tech[:60],
                                "response": reply}],
                    "cards": cards,
                    "mode": "info_gate",
                }

    # ---- Scope gate (L3 routine only) ----
    # An off-topic or "about MindCare" question on a SAFE, routine turn doesn't
    # need the CBT pipeline — answer it directly and skip the agent. Only ever
    # runs on L3 (L0/L1/L2 returned above) and biases to "personal", so a real
    # support message is never redirected.
    if settings.scope_router_enabled and level == "L3":
        scope = (scope_router.classify_smart(text)
                 if settings.scope_router_semantic
                 else scope_router.classify(text))
        if scope != "personal":
            reply = scope_router.reply_for(scope)
            sess = models.Session(
                **base, status="answered", analysis={"scope": scope},
                final_reply_enc=encrypt_phi(reply),
                final_technique=f"scope_{scope}",
                completed_at=datetime.now(timezone.utc))
            db.add(sess); db.flush()
            moderation_store.record_ai_message(
                db, convo, user_message, reply, level, "not_required",
                confidence=triage.get("confidence"), model_name="scope_router")
            audit_mod.audit(db, action=f"scope_{scope}", actor=user, ip=ip,
                             resource_type="session", resource_id=sess.id,
                             detail={"scope": scope})
            return {
                "session_id": str(sess.id),
                "conversation_id": str(convo.id),
                "outcome": "answered", "triage": triage,
                "final": {"technique": f"scope_{scope}", "response": reply},
                "drafts": [{"idx": 0, "technique": f"scope_{scope}",
                            "response": reply}],
                "mode": "scope_router",
            }

    # ---- L2 / L3: full pipeline ----
    analysis = analyzer.analyze(text, severity=triage["severity"])
    # The client explicitly asked for a DELIVERED analysis ("walk me through
    # it", "how likely") — pin a no-questions directive into the prompt and
    # (below) rank question-y drafts last. The 7B otherwise bounces the request
    # back ("can you walk me through it?").
    delivery_req = bool(_DELIVERY_REQ.search(text))
    if delivery_req:
        analysis["delivery_request"] = True

    # session context: prior count + last technique + durable memory +
    # the running history of THIS conversation thread (multi-turn).
    prior = (db.query(models.Session)
               .filter(models.Session.user_id == u.id,
                       models.Session.status.in_(["answered", "auto_sent"]))
               .order_by(models.Session.created_at.desc()).all())
    session_ctx = {
        "prior_count": len(prior),
        "last_technique": prior[0].final_technique if prior else None,
        # Rolling LLM summary of this thread, refreshed in the background after
        # each turn (summarizer.refresh_after_turn). Empty on the first turn.
        "summary": rc.thread_summary_get(str(convo.id)) or "(no summary yet)",
        "memory": user_memory.load_for_prompt(db, u.id),
        "history": _thread_history(db, convo.id),
        # Style preferences the client stated earlier ("be brief", …) — honoured
        # by the responder prompt. just_listen comes from the DURABLE per-thread
        # flag on the Conversation row, not Redis.
        "style_prefs": sorted(set(rc.chat_prefs_get(str(convo.id)))
                              | ({"just_listen"} if convo.listen_mode else set())),
    }

    # intake snapshot for prompt — None when the user skipped intake; the
    # prompt builder omits the block and memory fills the gap over time.
    intake_dict = None
    if intake is not None:
        intake_dict = {
            "demographics": intake.demographics,
            "presenting": decrypt_str(intake.presenting) if intake.presenting else "",
            "reason": intake.reason,
            "past_history": intake.past_history,
            "functioning": intake.functioning,
            "social_support": intake.social_support,
        }

    # PII scrub before any LLM / agent call
    scrubbed_text = pii_scrubber.scrub(text)
    scrubbed_intake = (pii_scrubber.scrub_dict(
        intake_dict, ["presenting", "reason", "social_support"])
        if intake_dict else None)

    # Map deterministic triage level → retriever risk_level:
    #   L3 routine → "normal", L2 moderate → "moderate". (L0/L1 never reach here.)
    risk_level = "moderate" if level == "L2" else "normal"

    # ════════════════════════════════════════════════════════════════════
    # AGENTIC PATH (feature-flagged). When the orchestrator is enabled AND
    # reachable, the cbt-qwen2.5-7b-v2 brain runs a ReAct loop: it decides how much
    # to retrieve / analyze / recall, then takes ONE terminal action
    # (generate / ask_clarification / escalate). On ANY failure run_agent
    # returns None and we fall back to the deterministic pipeline below.
    # L0/L1 never reach here, and the agent can only RAISE caution.
    # ════════════════════════════════════════════════════════════════════
    agent_result = None
    if agent_client.available():
        try:
            with metrics.Timer("cbt_stage_latency_seconds", stage="agent"):
                agent_result = agent.run_agent(
                    user_scrubbed=scrubbed_text, intake=scrubbed_intake,
                    session_ctx=session_ctx, analysis=analysis,
                    severity=triage["severity"], triage_level=level,
                    user_id=str(u.id), risk_level=risk_level,
                    n_responses=body.n_responses or settings.n_responses,
                    temperature=body.temperature or settings.temperature)
        except Exception:
            agent_result = None

    # ---- Agent terminal: ask a clarifying question (no full draft) ----
    if agent_result and agent_result.get("outcome") == "needs_clarification":
        question = agent_result["clarification"]
        analysis["agent_trace"] = agent_result.get("trace")
        sess = models.Session(
            **base, status="answered", analysis=analysis,
            final_reply_enc=encrypt_phi(question),
            final_technique="clarification",
            completed_at=datetime.now(timezone.utc))
        db.add(sess); db.flush()
        moderation_store.record_ai_message(
            db, convo, user_message, question, level, "not_required",
            confidence=triage.get("confidence"), model_name="cbt-agent")
        audit_mod.audit(db, action="agent_ask_clarification", actor=user,
                         ip=ip, resource_type="session", resource_id=sess.id)
        return {
            "session_id": str(sess.id), "conversation_id": str(convo.id),
            "outcome": "answered", "triage": triage,
            "final": {"technique": "clarification", "response": question},
            "drafts": [{"idx": 0, "technique": "clarification",
                        "response": question}],
            "mode": "agent",
            "listen_active": bool(convo.listen_mode),
        }

    # ---- Agent terminal: escalate to a clinician (force review even on L3) ----
    if agent_result and agent_result.get("outcome") == "escalate":
        reason = agent_result["escalate_reason"]
        analysis["agent_trace"] = agent_result.get("trace")
        analysis["agent_escalation"] = reason
        sess = models.Session(**base, status="pending_review", analysis=analysis)
        db.add(sess); db.flush()
        db.add(models.ReviewQueue(
            session_id=sess.id, triage_level=level, priority=1,
            sla_due_at=_sla_for("L1")))
        moderation_store.enqueue(db, convo, user_message, level)
        audit_mod.audit(db, action="agent_escalate_to_clinician", actor=user,
                         ip=ip, resource_type="session", resource_id=sess.id,
                         detail={"reason": reason})
        return {
            "session_id": str(sess.id), "conversation_id": str(convo.id),
            "outcome": "pending_review", "triage": triage,
            "message": ("Thank you for sharing. A clinician will follow up "
                         "with you directly on this."),
        }

    # ---- Drafts: from the agent, OR from the deterministic pipeline ----
    if agent_result and agent_result.get("outcome") == "drafts":
        # The orchestrator sensed a "just be heard" intent this turn (a paraphrase
        # regex missed) → make it sticky for the thread. Auto-ON only; the user's
        # toggle / an explicit "give me advice" is what turns it back off.
        if agent_result.get("listen_detected"):
            convo.listen_mode = True
        drafts = agent_result["drafts"]
        retrieved = agent_result.get("retrieved") or []
        analysis = agent_result.get("analysis") or analysis
        analysis["agent_trace"] = agent_result.get("trace")
        if agent_result.get("plan"):
            analysis["agent_plan"] = agent_result["plan"]
        if agent_result.get("self_critique"):
            analysis["agent_self_critique"] = agent_result["self_critique"]
        p_hash = agent_result.get("prompt_hash", "")
        retrieved_ids = [r["id"] for r in retrieved]
        gen_mode = agent_result.get("gen_mode", "agent")
        metrics.observe("cbt_retrieval_count", len(retrieved))
    else:
        # ── deterministic pipeline: v2 risk-aware retrieval + gate ──
        try:
            with metrics.Timer("cbt_stage_latency_seconds", stage="retrieval"):
                candidates = retrieval.retrieve(text, risk_level=risk_level,
                                                top_k=settings.rag_final_top_k)
        except Exception:
            candidates = []
        # Gate: inject context only when top-1 rerank is confident enough;
        # otherwise generate with no context (exactly like the eval).
        use_rag, gate_reason = retrieval.should_use_rag(risk_level, candidates)
        retrieved = candidates if use_rag else []
        retrieved_ids = [r["id"] for r in retrieved]
        analysis["rag_gate"] = {"risk_level": risk_level, "used_rag": use_rag,
                                "reason": gate_reason,
                                "n_candidates": len(candidates)}
        metrics.observe("cbt_retrieval_count", len(retrieved))

        messages = prompt_builder.build_messages(
            user_input_scrubbed=scrubbed_text,
            intake=scrubbed_intake,
            analysis=analysis,
            session_ctx=session_ctx,
            retrieved=retrieved,
        )
        p_hash = prompt_builder.prompt_hash(messages)
        with metrics.Timer("cbt_stage_latency_seconds", stage="llm_generate"):
            gen = llm_client.generate(
                messages,
                n=body.n_responses or settings.n_responses,
                temperature=body.temperature or settings.temperature)
        drafts = post_process.parse_all(gen.get("responses", []))
        gen_mode = gen.get("mode", "modal")

    # Anti-fabrication: drop a vocative name the client never gave us — the
    # responder sometimes borrows one from RAG reference transcripts ("Thank
    # you for sharing, Ryan"). Allowed = intake name, username, and any name
    # the client actually typed in this thread.
    _allowed_names = {w.lower() for t in ([text] + (history or []))
                      for w in re.findall(r"\b[A-Z][a-z]{1,20}\b", t or "")}
    _allowed_names.add((u.username or "").lower())
    _in_name = ((intake_dict or {}).get("demographics") or {}).get("name") or ""
    _allowed_names.update(w.lower() for w in str(_in_name).split())
    for d in drafts:
        d["response"] = post_process.scrub_unknown_names(
            d.get("response") or "", _allowed_names)

    # Listen-only: guarantee no draft carries a probing question, REGARDLESS of
    # which path produced it. The agent already strips its own drafts, but the
    # deterministic fallback only asked via the prompt — and the 7B sometimes
    # ignores that. This is the single choke-point both paths flow through.
    if "just_listen" in (session_ctx.get("style_prefs") or []):
        for d in drafts:
            d["response"] = post_process.strip_questions(d.get("response") or "")

    # pre-flight + grounding per-draft
    pf = preflight.check_all(drafts, triage["severity"])
    for d, (ok, reasons), idx in zip(drafts, pf, range(len(drafts))):
        d["preflight_pass"] = ok
        d["preflight_reasons"] = reasons
        d["grounding_score"] = post_process.grounding_score(
            d["response"], retrieved)
        if not ok:
            metrics.inc("cbt_preflight_fail_total",
                         severity=triage["severity"])
        if d["grounding_score"] < 0.1:
            metrics.inc("cbt_hallucination_flag_total",
                         severity=triage["severity"])

    # When the client has already NAMED their thoughts (quoted somewhere in
    # this thread), rank drafts that re-ask for them below drafts that advance
    # the work — the L2 admin list and the L3 auto-pick both use this order.
    # When nothing was named yet, exploration questions are legitimate and the
    # order is untouched.
    named_given = bool(prompt_builder._format_named_thoughts(
        session_ctx, scrubbed_text))

    def _draft_penalty(d):
        resp = d.get("response") or ""
        pen = _reask_count(resp) if named_given else 0
        if delivery_req:      # any question is a dodge on a delivery turn
            pen += _question_count(resp)
        return pen

    if drafts and (named_given or delivery_req):
        drafts.sort(key=lambda d: (0 if d.get("preflight_pass") else 1,
                                   _draft_penalty(d),
                                   -(d.get("grounding_score") or 0.0)))

    # ---- L2 vent-release valve (default: clinician pre-approval) ----
    # Every L2 waits for a clinician UNLESS a stack of checks unanimously rules
    # the turn ordinary venting. Any doubt anywhere → review, like before:
    #   1) regex heuristic saw no markers (heuristic L3);
    #   2) no acute-risk language in this message or ANY earlier turn;
    #   3) this thread has never triaged L0/L1 (sticky caution — a client who
    #      showed risk before never gets auto-released again in this thread);
    #   4) a dedicated VENT-vs-CONCERN model screen (context-aware) must answer
    #      VENT — fail-closed on mock/degraded/ambiguity;
    #   5) downstream, the draft must still pass the preflight+grounding gate.
    # Released turns stay labelled L2 in Moderation sessions for retrospective
    # review. L0/L1 and marker-based L2 are untouched; safety only goes UP.
    l2_release = False
    if (level == "L2"
            and getattr(settings, "l2_vent_release_enabled", True)
            and triage.get("heuristic_level", "L3") == "L3"
            and not safety_gate.has_acute_risk(text)
            and not any(safety_gate.has_acute_risk(h)
                        for h in (history or []))):
        prior_risk = (db.query(models.Session)
                      .filter(models.Session.conversation_id == convo.id,
                              models.Session.triage_level.in_(["L0", "L1"]))
                      .first())
        if prior_risk is None:
            l2_release = safety_gate.vent_check(text, safety_history)
    if l2_release:
        analysis["l2_vent_release"] = True

    # ---- L2: drafts BUT clinician review required ----
    if level == "L2" and not l2_release:
        sess = models.Session(
            **base, status="pending_review", analysis=analysis,
            retrieved_ids=retrieved_ids, prompt_hash=p_hash)
        db.add(sess); db.flush()
        selected = drafts[0] if drafts else None
        ai_message = None
        if selected:
            ai_message = moderation_store.record_ai_message(
                db, convo, user_message, selected["response"], level, "pending",
                confidence=triage.get("confidence"), model_name=gen_mode)
        for i, d in enumerate(drafts):
            db.add(models.Draft(
                session_id=sess.id, idx=i,
                technique=d["technique"], rationale=d["rationale"],
                plan=d["plan"],
                response_enc=encrypt_phi(d["response"]),
                well_formed=d["well_formed"],
                hallucination_score=d["grounding_score"],
                preflight_pass=d["preflight_pass"],
                source_user_message_id=user_message.id,
            ))
        db.add(models.ReviewQueue(
            session_id=sess.id, triage_level=level, priority=2,
            sla_due_at=_sla_for(level)))
        moderation_store.enqueue(
            db, convo, user_message, level, ai_message=ai_message,
            kind="ai_review" if ai_message else "user_escalation")
        audit_mod.audit(db, action="triage_L2_draft_pending", actor=user,
                         ip=ip, resource_type="session", resource_id=sess.id,
                         detail={"n_drafts": len(drafts)})
        # memory: record themes/technique even though reply is pending review
        user_memory.update_after_turn(
            db, u.id, analysis=analysis,
            technique=drafts[0]["technique"] if drafts else None,
            severity=triage["severity"])
        background_tasks.add_task(summarizer.refresh_after_turn,
                                  str(u.id), str(convo.id))
        return {
            "session_id": str(sess.id),
            "conversation_id": str(convo.id),
            "outcome": "pending_review",
            "triage": triage,
            "message": ("Thank you for sharing. A clinician is reviewing "
                         "the response for appropriateness — usually within "
                         "the hour, and you'll see it here the moment it's "
                         "approved. If you need support right now, 988 (US) "
                         "or findahelpline.com are available 24/7."),
            "listen_active": bool(convo.listen_mode),
        }

    # ---- L3: pick the best draft, then gate before auto-sending ----
    # Prefer a preflight-passing draft that does NOT re-ask for material the
    # client already gave, then the better-grounded one.
    chosen = max(
        drafts,
        key=lambda d: (1 if d.get("preflight_pass") else 0,
                       -_draft_penalty(d),
                       d.get("grounding_score", 0.0)),
    ) if drafts else None

    # Anti-fabrication gate: never auto-send a reply that fails preflight (or
    # falls below the grounding floor, if enabled). Hold it for a clinician
    # instead — safe by construction (routes to a human, never bypasses one).
    gate_fail = []
    if chosen is None:
        gate_fail.append("no draft produced")
    else:
        if settings.autosend_require_preflight and not chosen.get("preflight_pass"):
            gate_fail.append("preflight failed: " +
                             "; ".join(chosen.get("preflight_reasons") or []))
        floor = settings.autosend_grounding_floor
        if floor > 0 and chosen.get("grounding_score", 0.0) < floor:
            gate_fail.append(
                f"grounding {chosen.get('grounding_score')} < floor {floor}")

    # Hard gate: durable memory in the prompt → don't auto-send (see config).
    mem = (session_ctx or {}).get("memory") or {}
    if settings.autosend_block_with_memory and mem.get("turn_count", 0) > 0:
        gate_fail.append(
            "USER MEMORY present — held for review to prevent memory-narrated "
            "fabrication")

    if gate_fail:
        sess = models.Session(
            **base, status="pending_review", analysis=analysis,
            retrieved_ids=retrieved_ids, prompt_hash=p_hash)
        db.add(sess); db.flush()
        ai_message = None
        if chosen:
            ai_message = moderation_store.record_ai_message(
                db, convo, user_message, chosen["response"], level, "pending",
                confidence=triage.get("confidence"), model_name=gen_mode)
        for i, d in enumerate(drafts):
            db.add(models.Draft(
                session_id=sess.id, idx=i,
                technique=d["technique"], rationale=d["rationale"], plan=d["plan"],
                response_enc=encrypt_phi(d["response"]),
                well_formed=d["well_formed"],
                hallucination_score=d["grounding_score"],
                preflight_pass=d["preflight_pass"],
                source_user_message_id=user_message.id,
            ))
        db.add(models.ReviewQueue(
            session_id=sess.id, triage_level=level, priority=2,
            sla_due_at=_sla_for(level)))
        moderation_store.enqueue(
            db, convo, user_message, level, ai_message=ai_message,
            kind="ai_review" if ai_message else "user_escalation")
        audit_mod.audit(db, action="triage_L3_held_for_review", actor=user,
                         ip=ip, resource_type="session", resource_id=sess.id,
                         detail={"reasons": gate_fail})
        metrics.inc("cbt_autosend_blocked_total", severity=triage["severity"])
        user_memory.update_after_turn(
            db, u.id, analysis=analysis,
            technique=chosen["technique"] if chosen else None,
            severity=triage["severity"])
        background_tasks.add_task(summarizer.refresh_after_turn,
                                  str(u.id), str(convo.id))
        return {
            "session_id": str(sess.id),
            "conversation_id": str(convo.id),
            "outcome": "pending_review",
            "triage": triage,
            "message": ("Thank you for sharing. A clinician is reviewing the "
                         "response before it's sent, to make sure it fits you — "
                         "usually within the hour; it will appear here as soon "
                         "as it's approved."),
            "listen_active": bool(convo.listen_mode),
        }

    # ---- L3: auto-send the gated-OK draft ----
    # Emphasis pass: let the model bold the naturally-important part of the reply
    # it's about to send (one short call, only on the auto-sent turn; best-effort).
    if getattr(settings, "emphasis_pass_enabled", True):
        chosen["response"] = post_process.emphasize_llm(chosen["response"])
    sess = models.Session(
        **base, status="auto_sent",
        analysis=analysis, retrieved_ids=retrieved_ids, prompt_hash=p_hash,
        final_reply_enc=encrypt_phi(chosen["response"]),
        final_technique=chosen["technique"],
        completed_at=datetime.now(timezone.utc),
    )
    db.add(sess); db.flush()
    moderation_store.record_ai_message(
        db, convo, user_message, chosen["response"], level, "not_required",
        confidence=triage.get("confidence"), model_name=gen_mode)
    for i, d in enumerate(drafts):
        db.add(models.Draft(
            session_id=sess.id, idx=i,
            technique=d["technique"], rationale=d["rationale"],
            plan=d["plan"],
            response_enc=encrypt_phi(d["response"]),
            well_formed=d["well_formed"],
            hallucination_score=d["grounding_score"],
            preflight_pass=d["preflight_pass"],
            source_user_message_id=user_message.id,
        ))
    audit_mod.audit(db, action="triage_L3_auto_sent", actor=user,
                     ip=ip, resource_type="session", resource_id=sess.id,
                     detail={"technique": chosen["technique"]})

    # best-effort session memory writeback (Qdrant) + durable user memory
    try:
        session_memory.write_session(sess)
    except Exception:
        pass
    user_memory.update_after_turn(
        db, u.id, analysis=analysis,
        technique=chosen["technique"], severity=triage["severity"])
    background_tasks.add_task(summarizer.refresh_after_turn,
                              str(u.id), str(convo.id))

    return {
        "session_id": str(sess.id),
        "conversation_id": str(convo.id),
        "outcome": "answered",
        "triage": triage, "analysis": analysis,
        "drafts": [{"idx": i, "technique": d["technique"],
                    "response": d["response"]}
                   for i, d in enumerate(drafts)],
        "final": {"technique": chosen["technique"],
                  "response": chosen["response"]},
        "retrieved_count": len(retrieved),
        "mode": gen_mode,
        # True listen-mode state after this turn — the UI mirrors it so the
        # toggle/banner always reflect reality (even when auto-detected).
        "listen_active": bool(convo.listen_mode),
    }


@router.get("/my/sessions")
def my_sessions(user: dict = Depends(auth.current_user),
                 db: Session = Depends(get_db)):
    rows = (db.query(models.Session)
              .filter_by(user_id=user["uid"])
              .order_by(models.Session.created_at.desc()).limit(50).all())
    return {"sessions": [
        {"id": str(s.id), "created_at": s.created_at.isoformat(),
         "triage_level": s.triage_level, "status": s.status,
         "final_technique": s.final_technique} for s in rows]}


@router.get("/my/session/{sid}")
def my_session(sid: str, user: dict = Depends(auth.current_user),
                db: Session = Depends(get_db)):
    s = db.query(models.Session).filter_by(id=sid).first()
    if not s or str(s.user_id) != user["uid"]:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": str(s.id),
        "created_at": s.created_at.isoformat(),
        "user_input": decrypt_str(s.user_input_enc),
        "status": s.status,
        "triage_level": s.triage_level,
        "final_reply": decrypt_str(s.final_reply_enc) if s.final_reply_enc else None,
        "final_technique": s.final_technique,
    }
