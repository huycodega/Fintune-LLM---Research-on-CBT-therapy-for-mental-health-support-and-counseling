"""
Clinician / admin endpoints:
  GET    /api/admin/queue        — review queue
  GET    /api/admin/session/{id} — session detail + drafts (decrypted)
  POST   /api/admin/review/{id}  — approve / edit / reject + feedback +
                                     SOAP export
  GET    /api/admin/stats
  GET    /api/admin/audit
  POST   /api/admin/dpo-export   — dump preference_pairs view to MinIO
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text as sa_text

from app.core import auth, audit as audit_mod
from app.core.crypto import encrypt_phi, decrypt_str
from app.db import models
from app.db.session import get_db
from app.schemas.api import ReviewIn
from app.services import (
    redis_client as rc, soap_export, minio_client, session_memory, fhir_export,
    metrics,
)


router = APIRouter(prefix="/api/admin")


@router.get("/queue")
def queue(_: dict = Depends(auth.require_admin),
           db: Session = Depends(get_db)):
    rows = (db.query(models.ReviewQueue, models.Session, models.User)
             .join(models.Session,
                    models.Session.id == models.ReviewQueue.session_id)
             .join(models.User, models.User.id == models.Session.user_id)
             .filter(models.ReviewQueue.resolved_at.is_(None))
             .order_by(models.ReviewQueue.priority,
                        models.ReviewQueue.created_at).all())
    out = []
    for q, s, u in rows:
        out.append({
            "session_id": str(s.id),
            "username": u.username,
            "user_input": decrypt_str(s.user_input_enc),
            "triage_level": s.triage_level,
            "severity": s.severity,
            "confidence": s.confidence,
            "priority": q.priority,
            "sla_due_at": q.sla_due_at.isoformat() if q.sla_due_at else None,
            "claimed_by": str(q.claimed_by) if q.claimed_by else None,
            "created_at": s.created_at.isoformat(),
        })
    return {"queue": out}


@router.get("/session/{sid}")
def session_detail(sid: str, _: dict = Depends(auth.require_admin),
                    db: Session = Depends(get_db)):
    s = db.query(models.Session).filter_by(id=sid).first()
    if not s:
        raise HTTPException(404, "Session not found")
    drafts = (db.query(models.Draft).filter_by(session_id=s.id)
                .order_by(models.Draft.idx).all())
    intake = (db.query(models.IntakeForm).filter_by(id=s.intake_id).first()
              if s.intake_id else None)
    return {
        "session_id": str(s.id),
        "user_input": decrypt_str(s.user_input_enc),
        "triage_level": s.triage_level,
        "triage_reason": s.triage_reason,
        "severity": s.severity,
        "confidence": s.confidence,
        "analysis": s.analysis,
        "retrieved_ids": s.retrieved_ids,
        "status": s.status,
        "drafts": [{
            "id": str(d.id), "idx": d.idx,
            "technique": d.technique, "rationale": d.rationale,
            "plan": d.plan,
            "response": decrypt_str(d.response_enc) if d.response_enc else "",
            "well_formed": d.well_formed,
            "preflight_pass": d.preflight_pass,
            "hallucination_score": d.hallucination_score,
        } for d in drafts],
        "intake_snapshot": {
            "demographics": intake.demographics if intake else None,
            "presenting": (decrypt_str(intake.presenting) if intake and
                            intake.presenting else None),
            "reason": intake.reason if intake else None,
        } if intake else None,
    }


@router.post("/review/{sid}")
def review(sid: str, body: ReviewIn, request: Request,
            clinician: dict = Depends(auth.require_admin),
            db: Session = Depends(get_db)):
    if body.decision not in ("approve", "edit", "reject"):
        raise HTTPException(400, "decision must be approve|edit|reject")

    s = db.query(models.Session).filter_by(id=sid).first()
    if not s:
        raise HTTPException(404, "Session not found")
    if s.status != "pending_review":
        raise HTTPException(409, "Session is not pending_review")

    if not rc.acquire_review_lock(sid, clinician["uid"]):
        raise HTTPException(423, "Session locked by another clinician")

    try:
        drafts = (db.query(models.Draft).filter_by(session_id=s.id)
                    .order_by(models.Draft.idx).all())

        if body.decision == "reject":
            final_reply = (
                "Thank you for sharing. A clinician will reach out to you "
                "directly. If you need urgent support, please contact 988 "
                "or your nearest emergency services.")
            final_tech = "clinician_referral"
            chosen = None
        elif body.decision == "edit":
            if not body.edited_response.strip():
                raise HTTPException(400, "edited_response required")
            final_reply = body.edited_response.strip()
            final_tech = (body.edited_technique.strip() or
                           (drafts[body.chosen_idx].technique if drafts
                             else "edited"))
            chosen = drafts[body.chosen_idx] if drafts else None
        else:  # approve
            if not drafts:
                raise HTTPException(400, "No draft to approve (L1) — use 'edit'")
            idx = max(0, min(body.chosen_idx, len(drafts) - 1))
            chosen = drafts[idx]
            final_reply = decrypt_str(chosen.response_enc)
            final_tech = chosen.technique

        # update session
        s.status = "answered" if body.decision != "reject" else "rejected"
        s.final_reply_enc = encrypt_phi(final_reply)
        s.final_technique = final_tech
        s.reviewed_by = clinician["uid"]
        s.reviewed_at = datetime.now(timezone.utc)
        s.completed_at = s.reviewed_at

        # close queue row
        q = db.query(models.ReviewQueue).filter_by(session_id=s.id).first()
        if q:
            q.resolved_at = s.reviewed_at
            q.resolution = body.decision
            q.claimed_by = clinician["uid"]
            q.claimed_at = s.reviewed_at

        # feedback row (for DPO)
        edit_diff = None
        if body.decision == "edit" and chosen:
            edit_diff = {
                "before": decrypt_str(chosen.response_enc),
                "after": final_reply,
            }
        db.add(models.Feedback(
            session_id=s.id,
            draft_chosen=chosen.id if chosen else None,
            rating=body.rating,
            edit_diff=edit_diff,
            clinician_id=clinician["uid"],
        ))

        # SOAP export + session memory + FHIR write-back (non-reject only)
        soap_key = None
        fhir_synced = False
        if body.decision != "reject":
            intake = (db.query(models.IntakeForm).filter_by(id=s.intake_id)
                        .first() if s.intake_id else None)
            soap_row = soap_export.export(db, s, intake)
            db.flush()                     # so soap_row.id is real
            soap_key = soap_row.pdf_s3_key
            try:
                fhir_res = fhir_export.export(s, soap_row)
                fhir_synced = fhir_res.get("synced", False)
            except Exception:
                fhir_synced = False
            # Best-effort session memory upsert into Qdrant.
            try:
                session_memory.write_session(s)
            except Exception:
                pass

        metrics.inc("cbt_review_decision_total", decision=body.decision)

        audit_mod.audit(
            db, action=f"review_{body.decision}", actor=clinician,
            ip=auth.client_ip(request),
            resource_type="session", resource_id=s.id,
            detail={"technique": final_tech, "soap_s3_key": soap_key,
                    "fhir_synced": fhir_synced})

        return {
            "ok": True, "session_id": str(s.id), "decision": body.decision,
            "final_technique": final_tech,
            "soap_s3_key": soap_key,
            "fhir_synced": fhir_synced,
        }
    finally:
        rc.release_review_lock(sid)


@router.get("/stats")
def stats(_: dict = Depends(auth.require_admin),
           db: Session = Depends(get_db)):
    total = db.query(func.count(models.Session.id)).scalar()
    pending = db.query(func.count(models.ReviewQueue.session_id)).filter(
        models.ReviewQueue.resolved_at.is_(None)).scalar()
    by_level = dict(db.query(models.Session.triage_level,
                                func.count(models.Session.id))
                       .group_by(models.Session.triage_level).all())
    by_tech = dict(db.query(models.Session.final_technique,
                               func.count(models.Session.id))
                      .filter(models.Session.final_technique.isnot(None))
                      .group_by(models.Session.final_technique).all())
    return {
        "total_sessions": total,
        "pending_review": pending,
        "by_triage_level": by_level,
        "technique_distribution": by_tech,
    }


@router.get("/audit")
def audit_list(limit: int = 100, _: dict = Depends(auth.require_admin),
                db: Session = Depends(get_db)):
    rows = (db.query(models.AuditTrail)
              .order_by(models.AuditTrail.ts.desc()).limit(limit).all())
    return {"audit": [{
        "id": str(r.id), "ts": r.ts.isoformat(),
        "actor": r.actor_username, "role": r.actor_role,
        "action": r.action, "resource_type": r.resource_type,
        "resource_id": str(r.resource_id) if r.resource_id else None,
        "ip": str(r.ip_address) if r.ip_address else None,
    } for r in rows]}


@router.post("/dpo-export")
def dpo_export(_: dict = Depends(auth.require_admin),
                db: Session = Depends(get_db)):
    """Dump preference_pairs view → MinIO cbt-training-data bucket."""
    rows = db.execute(sa_text(
        "SELECT feedback_id, user_input_hash, chosen_draft_id, chosen_enc, "
        "rejected_draft_id, rejected_enc FROM preference_pairs"
    )).fetchall()

    out_lines = []
    for r in rows:
        out_lines.append(json.dumps({
            "feedback_id": str(r.feedback_id),
            "user_input_hash": r.user_input_hash,
            "chosen": decrypt_str(r.chosen_enc) if r.chosen_enc else "",
            "rejected": decrypt_str(r.rejected_enc) if r.rejected_enc else "",
        }))
    body = "\n".join(out_lines).encode("utf-8")
    key = f"dpo-batches/{datetime.utcnow():%Y-%m-%d_%H%M%S}.jsonl"
    minio_client.put_bytes("cbt-training-data", key, body,
                            content_type="application/x-ndjson")
    return {"ok": True, "pairs": len(rows), "key": key}
