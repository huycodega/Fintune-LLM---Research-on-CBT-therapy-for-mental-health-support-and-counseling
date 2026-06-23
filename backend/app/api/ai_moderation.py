"""
Admin — AI Moderation queue.

Compatibility adapter over the existing ``review_queue`` / ``sessions``
tables (the per-message ``moderation_queue`` cutover in design doc §1.3.3
is not wired yet). ``queue_item_id`` == ``session_id`` here because the
legacy ``review_queue`` is keyed by session.

  GET   /api/admin/ai-moderation/stats
  GET   /api/admin/ai-moderation/items
  GET   /api/admin/ai-moderation/items/{queue_item_id}
  PATCH /api/admin/ai-moderation/items/{queue_item_id}/claim
  PATCH /api/admin/ai-moderation/items/{queue_item_id}/approve
  PATCH /api/admin/ai-moderation/items/{queue_item_id}/edit-response
  PATCH /api/admin/ai-moderation/items/{queue_item_id}/reject
  PATCH /api/admin/ai-moderation/items/{queue_item_id}/need-improvement

``risk_level`` is the L0–L3 the safety gate already stored on the session;
the frontend owns the label/colour mapping (design doc §2.3).
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core import auth, audit as audit_mod
from app.core.crypto import encrypt_phi, decrypt_str
from app.db import models
from app.db.session import get_db


router = APIRouter(prefix="/api/admin/ai-moderation")

REFERRAL_REPLY = (
    "Thank you for sharing. A clinician will reach out to you directly. "
    "If you need urgent support, please contact 988 (Suicide & Crisis "
    "Lifeline) or your local emergency services."
)


# ── Request bodies ───────────────────────────────────────────────────────────
class DecisionIn(BaseModel):
    checklist: Optional[dict] = None
    note: Optional[str] = ""
    draft_idx: Optional[int] = None


class EditIn(DecisionIn):
    response: str


# ── Helpers ──────────────────────────────────────────────────────────────────
def _mask_email(email: Optional[str]) -> str:
    if not email or "@" not in email:
        return "—"
    name, _, domain = email.partition("@")
    head = name[:2] if len(name) >= 2 else name
    return f"{head}***@{domain}"


def _display(username: str) -> str:
    return (username or "User").split("@")[0]


def _kind(triage: Optional[str], has_draft: bool) -> str:
    # L0/L1 are handled deterministically with no AI reply → user_escalation.
    if triage in ("L0", "L1") and not has_draft:
        return "user_escalation"
    return "ai_review"


def _status(q: models.ReviewQueue) -> str:
    if q.resolved_at:
        return "resolved"
    if q.claimed_by:
        return "claimed"
    return "pending"


def _item(q, s, u, drafts, claimer_name=None):
    triage = s.triage_level or (q.triage_level if q else None) or "L3"
    ai_draft = next((d for d in drafts if d.response_enc), None)
    has_draft = ai_draft is not None
    draft = None
    if has_draft:
        draft = {
            "response": decrypt_str(ai_draft.response_enc),
            "confidence": s.confidence if s.confidence is not None else 0.8,
            "model_name": s.final_technique or "cbt-agent",
        }
    messages = [{
        "id": f"{s.id}-u",
        "sender": "user",
        "content": decrypt_str(s.user_input_enc),
        "risk_level": triage,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }]
    return {
        "id": str(s.id),
        "conversation_id": str(s.conversation_id or s.id),
        "kind": _kind(triage, has_draft),
        "status": _status(q) if q else "pending",
        "risk_level": triage,
        "priority": (q.priority if q and q.priority is not None else 50),
        "sla_due_at": q.sla_due_at.isoformat() if q and q.sla_due_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "claimed_by": {"name": claimer_name} if (q and q.claimed_by) else None,
        "user": {"name": _display(u.username), "masked_email": _mask_email(u.email)},
        "messages": messages,
        "draft": draft,
        "drafts": [{
            "id": str(d.id), "idx": d.idx,
            "technique": d.technique or f"Option {d.idx + 1}",
            "rationale": d.rationale, "plan": d.plan,
            "preflight_pass": d.preflight_pass,
            "response": decrypt_str(d.response_enc) if d.response_enc else "",
        } for d in drafts],
        "revisions": [],
    }


def _stats(db: Session) -> dict:
    open_q = db.query(models.ReviewQueue).filter(models.ReviewQueue.resolved_at.is_(None))
    pending = open_q.filter(models.ReviewQueue.claimed_by.is_(None)).count()
    in_review = open_q.filter(models.ReviewQueue.claimed_by.isnot(None)).count()
    escalations = (
        db.query(func.count(models.ReviewQueue.session_id))
        .join(models.Session, models.Session.id == models.ReviewQueue.session_id)
        .filter(models.ReviewQueue.resolved_at.is_(None),
                models.Session.triage_level.in_(("L0", "L1")))
        .scalar()
    )
    today = datetime.now(timezone.utc).date()
    resolved_today = (
        db.query(func.count(models.ReviewQueue.session_id))
        .filter(models.ReviewQueue.resolved_at.isnot(None),
                func.date(models.ReviewQueue.resolved_at) == today)
        .scalar()
    )
    return {
        "pending": pending,
        "in_review": in_review,
        "escalations": escalations or 0,
        "resolved_today": resolved_today or 0,
    }


def _load(qid: str, db: Session):
    s = db.query(models.Session).filter_by(id=qid).first()
    if not s:
        raise HTTPException(404, "Moderation item not found")
    q = db.query(models.ReviewQueue).filter_by(session_id=qid).first()
    return q, s


def _ensure_claimable(q, actor):
    if q is None:
        raise HTTPException(404, "No review queue entry for this item")
    if q.resolved_at:
        raise HTTPException(409, "This item is already resolved")
    if q.claimed_by and str(q.claimed_by) != actor["uid"]:
        raise HTTPException(423, "Claimed by another reviewer")


def _finalize(s, q, decision, final_reply, final_tech, actor, db, request):
    s.status = "answered" if decision != "reject" else "rejected"
    if final_reply is not None:
        s.final_reply_enc = encrypt_phi(final_reply)
    s.final_technique = final_tech
    s.reviewed_by = actor["uid"]
    s.reviewed_at = datetime.now(timezone.utc)
    s.completed_at = s.reviewed_at
    if q:
        q.resolved_at = s.reviewed_at
        q.resolution = decision
        q.claimed_by = actor["uid"]
        q.claimed_at = q.claimed_at or s.reviewed_at
    audit_mod.audit(db, action=f"moderation_{decision}", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="session", resource_id=s.id,
                    detail={"technique": final_tech})


# ── Read ─────────────────────────────────────────────────────────────────────
@router.get("/stats")
def stats(_: dict = Depends(auth.require_admin), db: Session = Depends(get_db)):
    return _stats(db)


@router.get("/items")
def items(_: dict = Depends(auth.require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(models.ReviewQueue, models.Session, models.User)
        .join(models.Session, models.Session.id == models.ReviewQueue.session_id)
        .join(models.User, models.User.id == models.Session.user_id)
        .filter(models.ReviewQueue.resolved_at.is_(None))
        .order_by(models.ReviewQueue.priority, models.ReviewQueue.created_at)
        .all()
    )
    claimer_ids = {q.claimed_by for q, s, u in rows if q.claimed_by}
    names = {}
    if claimer_ids:
        for cu in db.query(models.User).filter(models.User.id.in_(claimer_ids)).all():
            names[cu.id] = _display(cu.username)

    out = []
    for q, s, u in rows:
        drafts = (db.query(models.Draft).filter_by(session_id=s.id)
                  .order_by(models.Draft.idx).all())
        out.append(_item(q, s, u, drafts, claimer_name=names.get(q.claimed_by)))
    return {"items": out, "stats": _stats(db)}


@router.get("/history")
def history(limit: int = 100, _: dict = Depends(auth.require_admin),
            db: Session = Depends(get_db)):
    """Already-resolved moderation decisions (approve / edit / reject),
    newest-first — the 'processed' history of the AI Moderation queue."""
    rows = (
        db.query(models.ReviewQueue, models.Session, models.User)
        .join(models.Session, models.Session.id == models.ReviewQueue.session_id)
        .join(models.User, models.User.id == models.Session.user_id)
        .filter(models.ReviewQueue.resolved_at.isnot(None))
        .order_by(models.ReviewQueue.resolved_at.desc())
        .limit(limit).all()
    )
    reviewer_ids = {s.reviewed_by for _q, s, _u in rows if s.reviewed_by}
    names = {}
    if reviewer_ids:
        for ru in db.query(models.User).filter(models.User.id.in_(reviewer_ids)).all():
            names[ru.id] = _display(ru.username)

    out = []
    for q, s, u in rows:
        try:
            final = decrypt_str(s.final_reply_enc) if s.final_reply_enc else ""
        except Exception:
            final = ""
        try:
            content = decrypt_str(s.user_input_enc) or ""
        except Exception:
            content = ""
        out.append({
            "id": str(s.id),
            "sessionId": str(s.id),
            "riskLevel": s.triage_level or "L3",
            "user": {"name": _display(u.username),
                     "masked_email": _mask_email(u.email)},
            "userContent": content,
            "contentSummary": content[:120],
            "resolution": q.resolution,                 # approve | edit | reject
            "reviewedBy": names.get(s.reviewed_by),
            "resolvedAt": q.resolved_at.isoformat() if q.resolved_at else None,
            "finalResponse": final,
            "technique": s.final_technique,
        })
    return {"items": out}


@router.get("/items/{qid}")
def item_detail(qid: str, _: dict = Depends(auth.require_admin),
                db: Session = Depends(get_db)):
    q, s = _load(qid, db)
    u = db.query(models.User).filter_by(id=s.user_id).first()
    drafts = (db.query(models.Draft).filter_by(session_id=s.id)
              .order_by(models.Draft.idx).all())
    claimer = None
    if q and q.claimed_by:
        cu = db.query(models.User).filter_by(id=q.claimed_by).first()
        claimer = _display(cu.username) if cu else None
    return _item(q, s, u, drafts, claimer_name=claimer)


# ── Actions ──────────────────────────────────────────────────────────────────
@router.patch("/items/{qid}/claim")
def claim(qid: str, request: Request, actor: dict = Depends(auth.require_admin),
          db: Session = Depends(get_db)):
    q, s = _load(qid, db)
    _ensure_claimable(q, actor)
    q.claimed_by = actor["uid"]
    q.claimed_at = datetime.now(timezone.utc)
    audit_mod.audit(db, action="moderation_claim", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="session", resource_id=s.id, detail={})
    return {"ok": True, "id": qid, "status": "claimed"}


@router.patch("/items/{qid}/approve")
def approve(qid: str, body: DecisionIn, request: Request,
            actor: dict = Depends(auth.require_admin),
            db: Session = Depends(get_db)):
    q, s = _load(qid, db)
    _ensure_claimable(q, actor)
    drafts = (db.query(models.Draft).filter_by(session_id=s.id)
              .order_by(models.Draft.idx).all())
    draft = None
    if body.draft_idx is not None:
        draft = next((d for d in drafts
                      if d.idx == body.draft_idx and d.response_enc), None)
    if draft is None:
        draft = next((d for d in drafts if d.response_enc), None)
    if not draft:
        raise HTTPException(400, "No AI draft to approve — use edit-response")
    _finalize(s, q, "approve", decrypt_str(draft.response_enc),
              draft.technique or "approved", actor, db, request)
    return {"ok": True, "id": qid, "resolution": "approve"}


@router.patch("/items/{qid}/edit-response")
def edit_response(qid: str, body: EditIn, request: Request,
                  actor: dict = Depends(auth.require_admin),
                  db: Session = Depends(get_db)):
    q, s = _load(qid, db)
    _ensure_claimable(q, actor)
    if not (body.response or "").strip():
        raise HTTPException(400, "response is required")
    _finalize(s, q, "edit", body.response.strip(), "edited", actor, db, request)
    return {"ok": True, "id": qid, "resolution": "edit"}


@router.patch("/items/{qid}/reject")
def reject(qid: str, body: DecisionIn, request: Request,
           actor: dict = Depends(auth.require_admin),
           db: Session = Depends(get_db)):
    q, s = _load(qid, db)
    _ensure_claimable(q, actor)
    _finalize(s, q, "reject", REFERRAL_REPLY, "clinician_referral",
              actor, db, request)
    return {"ok": True, "id": qid, "resolution": "reject"}


@router.patch("/items/{qid}/need-improvement")
def need_improvement(qid: str, body: DecisionIn, request: Request,
                     actor: dict = Depends(auth.require_admin),
                     db: Session = Depends(get_db)):
    q, s = _load(qid, db)
    if q is None:
        raise HTTPException(404, "No review queue entry for this item")
    if q.resolved_at:
        raise HTTPException(409, "This item is already resolved")
    # Keep the item OPEN (do not set resolved_at) but mark it claimed by the
    # reviewer who flagged it, per design doc §5.3 (need_improvement does not
    # close the queue).
    q.claimed_by = actor["uid"]
    q.claimed_at = q.claimed_at or datetime.now(timezone.utc)
    audit_mod.audit(db, action="moderation_need_improvement", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="session", resource_id=s.id,
                    detail={"note": (body.note or "")[:500]})
    return {"ok": True, "id": qid, "status": "need_improvement"}
