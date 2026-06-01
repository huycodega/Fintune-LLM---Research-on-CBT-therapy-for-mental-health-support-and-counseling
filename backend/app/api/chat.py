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
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
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
    metrics, session_memory,
)


router = APIRouter(prefix="/api")


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


@router.post("/chat")
def chat(body: ChatIn, request: Request,
          user: dict = Depends(auth.current_user),
          db: Session = Depends(get_db)):
    if user["role"] != "user":
        raise HTTPException(403, "Only user role may call /chat")

    # ---- preconditions ----
    u = db.query(models.User).filter_by(id=user["uid"]).first()
    if u.consent_at is None:
        raise HTTPException(403, "Consent required (call /api/consent first)")
    intake = (db.query(models.IntakeForm)
                .filter_by(user_id=u.id)
                .order_by(models.IntakeForm.created_at.desc())
                .first())
    if intake is None:
        raise HTTPException(403, "Intake form required (call /api/intake first)")

    ip = auth.client_ip(request)
    rc.rate_limit_check(str(u.id), ip)

    text = body.message.strip()
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # ---- safety triage (.pt) with cache ----
    cached = rc.triage_cache_get(text_hash)
    if cached:
        triage = cached
        metrics.inc("cbt_triage_cache_total", outcome="hit")
    else:
        with metrics.Timer("cbt_stage_latency_seconds", stage="triage"):
            triage = safety_gate.assess(text)
        # Post-hoc temperature scaling — fixes overconfidence.
        # Persist BOTH raw and calibrated so audit/eval can replay.
        raw_conf = float(triage.get("confidence", 0.0))
        cal_conf = calibration.calibrate_confidence(raw_conf)
        triage["confidence_raw"] = raw_conf
        triage["confidence"] = cal_conf
        triage["calibration_T"] = calibration.get_temperature()
        rc.triage_cache_set(text_hash, triage)
        metrics.inc("cbt_triage_cache_total", outcome="miss")

    level = triage["triage_level"]
    metrics.inc("cbt_triage_level_total", level=level)

    base = dict(
        user_id=u.id, intake_id=intake.id,
        user_input_enc=encrypt_phi(text),
        user_input_hash=text_hash,
        triage_level=level,
        triage_reason=triage["reason"],
        severity=triage["severity"],
        confidence=triage["confidence"],
    )

    # ---- L0: Emergency — NO AI ----
    if level == "L0":
        sess = models.Session(**base, status="crisis", analysis={})
        db.add(sess); db.flush()
        audit_mod.audit(db, action="triage_L0_crisis", actor=user,
                         ip=ip, resource_type="session", resource_id=sess.id,
                         detail=triage)
        return {
            "session_id": str(sess.id),
            "outcome": "crisis",
            "triage": triage,
            "crisis_resources": CRISIS_RESOURCES,
            "message": ("Based on what you shared, the system is concerned "
                         "for your safety. AI will not respond automatically. "
                         "Please reach out to the resources below."),
        }

    # ---- L1: High risk — NO draft, push to clinician ----
    if level == "L1":
        sess = models.Session(**base, status="pending_review", analysis={})
        db.add(sess); db.flush()
        db.add(models.ReviewQueue(
            session_id=sess.id, triage_level=level, priority=1,
            sla_due_at=_sla_for(level)))
        audit_mod.audit(db, action="triage_L1_no_ai_pushed", actor=user,
                         ip=ip, resource_type="session", resource_id=sess.id,
                         detail=triage)
        return {
            "session_id": str(sess.id), "outcome": "pending_review",
            "triage": triage, "crisis_resources": CRISIS_RESOURCES,
            "message": ("Your message will be reviewed by a clinician "
                         "directly. AI will not generate an automated reply."),
        }

    # ---- L2 / L3: full pipeline ----
    analysis = analyzer.analyze(text, severity=triage["severity"])

    # session context: prior count + last technique (simple now)
    prior = (db.query(models.Session)
               .filter(models.Session.user_id == u.id,
                       models.Session.status.in_(["answered", "auto_sent"]))
               .order_by(models.Session.created_at.desc()).all())
    session_ctx = {
        "prior_count": len(prior),
        "last_technique": prior[0].final_technique if prior else None,
        "summary": "(no summary yet)",   # extend later: LLM-summarize last N
    }

    # intake snapshot for prompt
    intake_dict = {
        "demographics": intake.demographics,
        "presenting": decrypt_str(intake.presenting) if intake.presenting else "",
        "reason": intake.reason,
        "past_history": intake.past_history,
        "functioning": intake.functioning,
        "social_support": intake.social_support,
    }

    # retrieval (Qdrant + rerank)
    try:
        with metrics.Timer("cbt_stage_latency_seconds", stage="retrieval"):
            retrieved = retrieval.retrieve(
                query=text,
                top_k_per_collection=settings.retrieval_top_k // 2,
                rerank_top_k=settings.retrieval_rerank_top_k)
    except Exception:
        retrieved = []
    retrieved_ids = [r["id"] for r in retrieved]
    metrics.observe("cbt_retrieval_count", len(retrieved))

    # PII scrub before LLM
    scrubbed_text = pii_scrubber.scrub(text)
    scrubbed_intake = pii_scrubber.scrub_dict(
        intake_dict, ["presenting", "reason", "social_support"])

    messages = prompt_builder.build_messages(
        user_input_scrubbed=scrubbed_text,
        intake=scrubbed_intake,
        analysis=analysis,
        session_ctx=session_ctx,
        retrieved=retrieved,
    )
    p_hash = prompt_builder.prompt_hash(messages)

    # LLM call (circuit-broken)
    with metrics.Timer("cbt_stage_latency_seconds", stage="llm_generate"):
        gen = llm_client.generate(
            messages,
            n=body.n_responses or settings.n_responses,
            temperature=body.temperature or settings.temperature)
    drafts = post_process.parse_all(gen.get("responses", []))

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

    # ---- L2: drafts BUT clinician review required ----
    if level == "L2":
        sess = models.Session(
            **base, status="pending_review", analysis=analysis,
            retrieved_ids=retrieved_ids, prompt_hash=p_hash)
        db.add(sess); db.flush()
        for i, d in enumerate(drafts):
            db.add(models.Draft(
                session_id=sess.id, idx=i,
                technique=d["technique"], rationale=d["rationale"],
                plan=d["plan"],
                response_enc=encrypt_phi(d["response"]),
                well_formed=d["well_formed"],
                hallucination_score=d["grounding_score"],
                preflight_pass=d["preflight_pass"],
            ))
        db.add(models.ReviewQueue(
            session_id=sess.id, triage_level=level, priority=2,
            sla_due_at=_sla_for(level)))
        audit_mod.audit(db, action="triage_L2_draft_pending", actor=user,
                         ip=ip, resource_type="session", resource_id=sess.id,
                         detail={"n_drafts": len(drafts)})
        return {
            "session_id": str(sess.id), "outcome": "pending_review",
            "triage": triage,
            "message": ("Thank you for sharing. A clinician is reviewing "
                         "the response for appropriateness. You will be "
                         "notified once approved."),
        }

    # ---- L3: auto-send first draft ----
    chosen = drafts[0]
    sess = models.Session(
        **base, status="auto_sent",
        analysis=analysis, retrieved_ids=retrieved_ids, prompt_hash=p_hash,
        final_reply_enc=encrypt_phi(chosen["response"]),
        final_technique=chosen["technique"],
        completed_at=datetime.now(timezone.utc),
    )
    db.add(sess); db.flush()
    for i, d in enumerate(drafts):
        db.add(models.Draft(
            session_id=sess.id, idx=i,
            technique=d["technique"], rationale=d["rationale"],
            plan=d["plan"],
            response_enc=encrypt_phi(d["response"]),
            well_formed=d["well_formed"],
            hallucination_score=d["grounding_score"],
            preflight_pass=d["preflight_pass"],
        ))
    audit_mod.audit(db, action="triage_L3_auto_sent", actor=user,
                     ip=ip, resource_type="session", resource_id=sess.id,
                     detail={"technique": chosen["technique"]})

    # best-effort session memory writeback (Qdrant)
    try:
        session_memory.write_session(sess)
    except Exception:
        pass

    return {
        "session_id": str(sess.id), "outcome": "answered",
        "triage": triage, "analysis": analysis,
        "drafts": [{"idx": i, "technique": d["technique"],
                    "response": d["response"]}
                   for i, d in enumerate(drafts)],
        "final": {"technique": chosen["technique"],
                  "response": chosen["response"]},
        "retrieved_count": len(retrieved),
        "mode": gen.get("mode", "modal"),
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
