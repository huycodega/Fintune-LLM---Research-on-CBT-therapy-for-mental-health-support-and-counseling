"""
Case Management endpoints (admin) — backs the teammates' Case Management UI
(services/casesApi.js -> /api/admin/cases*).

A "case" is a real user Session that needed attention (triage L0/L1/L2). The
case lifecycle overlay (status / assigned specialist / notes / timeline /
version) is stored inside the session's existing `analysis` JSONB under the
"_case" key, so no schema migration is required.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import desc

from app.core import auth, audit as audit_mod
from app.core.crypto import decrypt_str
from app.db import models
from app.db.session import get_db

router = APIRouter(prefix="/api/admin")

# Which triage levels surface as manageable cases.
_CASE_LEVELS = ("L0", "L1", "L2")
_PRIORITY = {"L0": "critical", "L1": "high", "L2": "medium", "L3": "low"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return email or "—"
    name, dom = email.split("@", 1)
    head = name[:2] if len(name) > 2 else name[:1]
    return f"{head}***@{dom}"


def _display_name(username: str) -> str:
    if not username:
        return "User"
    return username.split("@")[0]


def _default_status(sess) -> str:
    return {
        "pending_review": "new",
        "crisis": "new",
        "answered": "closed",
        "auto_sent": "closed",
        "rejected": "closed",
    }.get(sess.status, "new")


def _case_state(sess) -> dict:
    """Lifecycle overlay stored in analysis['_case'] (defaults derived from
    the session when not yet set)."""
    analysis = sess.analysis or {}
    st = dict(analysis.get("_case") or {})
    st.setdefault("status", _default_status(sess))
    st.setdefault("version", 1)
    st.setdefault("notes", [])
    st.setdefault("events", [])
    st.setdefault("assigned_specialist", None)
    st.setdefault("closed_at", None)
    return st


def _save_state(db, sess, st):
    sess.analysis = {**(sess.analysis or {}), "_case": st}


def _case_code(sess) -> str:
    return "C-" + str(sess.id)[:8].upper()


def _list_item(sess, user):
    st = _case_state(sess)
    summary = ""
    try:
        summary = (decrypt_str(sess.user_input_enc) or "")[:140]
    except Exception:
        summary = ""
    return {
        "id": str(sess.id),
        "case_code": _case_code(sess),
        "user": {
            "id": str(user.id) if user else None,
            "display_name": _display_name(user.username) if user else "User",
            "email_masked": _mask_email(user.email or (user.username if user else "")),
        },
        "detected_signal_summary": summary,
        "priority": _PRIORITY.get(sess.triage_level, "low"),
        "risk_level": sess.triage_level,
        "status": st["status"],
        "assigned_specialist": st["assigned_specialist"],
        "created_at": sess.created_at.isoformat(),
        "version": st["version"],
    }


def _candidates(db):
    return (db.query(models.Session, models.User)
              .join(models.User, models.User.id == models.Session.user_id)
              .filter(models.Session.triage_level.in_(_CASE_LEVELS))
              .order_by(desc(models.Session.created_at)))


def _get_case(db, cid):
    sess = db.query(models.Session).filter_by(id=cid).first()
    if not sess:
        raise HTTPException(404, "Case not found")
    user = db.query(models.User).filter_by(id=sess.user_id).first()
    return sess, user


# ── list / stats ────────────────────────────────────────────────────────────
@router.get("/cases")
def list_cases(request: Request, _: dict = Depends(auth.require_admin),
               db: DbSession = Depends(get_db)):
    p = request.query_params
    q = (p.get("q") or "").lower().strip()
    f_priority = p.get("priority") or ""
    f_status = p.get("status") or ""
    f_specialist = p.get("specialist_id") or ""
    page = max(1, int(p.get("page") or 1))
    size = max(1, min(100, int(p.get("page_size") or 20)))

    rows = _candidates(db).all()
    items = [_list_item(s, u) for s, u in rows]
    if q:
        items = [it for it in items if q in it["case_code"].lower()
                 or q in (it["user"]["display_name"] or "").lower()
                 or q in (it["user"]["email_masked"] or "").lower()
                 or q in (it["detected_signal_summary"] or "").lower()]
    if f_priority:
        items = [it for it in items if it["priority"] == f_priority]
    if f_status:
        items = [it for it in items if it["status"] == f_status]
    if f_specialist:
        items = [it for it in items if (it["assigned_specialist"] or {}).get("id") == f_specialist]

    total = len(items)
    start = (page - 1) * size
    return {"items": items[start:start + size], "total": total,
            "page": page, "page_size": size}


@router.get("/cases/stats")
def case_stats(_: dict = Depends(auth.require_admin),
               db: DbSession = Depends(get_db)):
    rows = _candidates(db).all()
    items = [_list_item(s, u) for s, u in rows]
    specialists = [
        {"id": str(u.id), "display_name": _display_name(u.username)}
        for u in db.query(models.User)
                   .filter(models.User.role.in_(("admin", "clinician"))).all()
    ]
    return {
        "new": sum(1 for it in items if it["status"] == "new"),
        "critical": sum(1 for it in items if it["priority"] == "critical" and it["status"] != "closed"),
        "monitoring": sum(1 for it in items if it["status"] == "monitoring"),
        "closed": sum(1 for it in items if it["status"] == "closed"),
        "specialists": specialists,
    }


# ── detail / history ────────────────────────────────────────────────────────
@router.get("/cases/{cid}")
def case_detail(cid: str, _: dict = Depends(auth.require_admin),
                db: DbSession = Depends(get_db)):
    sess, user = _get_case(db, cid)
    st = _case_state(sess)
    base = _list_item(sess, user)
    content = ""
    try:
        content = decrypt_str(sess.user_input_enc) or ""
    except Exception:
        content = ""
    q = (db.query(models.ReviewQueue)
           .filter_by(session_id=sess.id).first())
    base.update({
        "ai_confidence": sess.confidence,
        "sla_due_at": q.sla_due_at.isoformat() if q and q.sla_due_at else None,
        "source_type": "ai_message",
        "source": {"content": content, "created_at": sess.created_at.isoformat(),
                   "session_id": str(sess.id)},
        "signals": [],
        "actions": [],
        "notes": st["notes"],
        "attachments": [],
        "closed_at": st["closed_at"],
        "triage_reason": sess.triage_reason,
    })
    return base


@router.get("/cases/{cid}/history")
def case_history(cid: str, _: dict = Depends(auth.require_admin),
                 db: DbSession = Depends(get_db)):
    sess, _user = _get_case(db, cid)
    st = _case_state(sess)
    events = list(st["events"])
    # Always show the case creation as the first (oldest) event.
    events = events + [{
        "id": "created", "event_type": "created", "actor_name": "system",
        "from_status": None, "to_status": _default_status(sess),
        "created_at": sess.created_at.isoformat(),
    }]
    return {"items": events, "total": len(events)}


# ── mutations (version-checked) ─────────────────────────────────────────────
def _check_version(st, body):
    v = body.get("version") if isinstance(body, dict) else None
    if v is not None and int(v) != int(st["version"]):
        raise HTTPException(409, "Case was updated by someone else — refresh")


def _push_event(st, event_type, actor, from_status):
    st["events"].insert(0, {
        "id": str(uuid.uuid4()), "event_type": event_type,
        "actor_name": actor, "from_status": from_status,
        "to_status": st["status"], "created_at": _now(),
    })
    st["version"] = int(st["version"]) + 1


async def _body(request: Request) -> dict:
    try:
        return await request.json()
    except Exception:
        return {}


def _actor_name(actor):
    return _display_name(actor.get("username", "")) or "clinician"


def _apply(db, sess, st, request, actor):
    _save_state(db, sess, st)
    audit_mod.audit(db, action="case_update", actor=actor,
                    ip=auth.client_ip(request), resource_type="session",
                    resource_id=sess.id, detail={"status": st["status"]})


@router.patch("/cases/{cid}")
async def case_update(cid: str, request: Request,
                      actor: dict = Depends(auth.require_admin),
                      db: DbSession = Depends(get_db)):
    body = await _body(request)
    sess, user = _get_case(db, cid)
    st = _case_state(sess)
    _check_version(st, body)
    prev = st["status"]
    st["status"] = body.get("status", st["status"])
    _push_event(st, "status_changed", _actor_name(actor), prev)
    _apply(db, sess, st, request, actor)
    return case_detail_payload(sess, user, st, db)


@router.post("/cases/{cid}/assign")
async def case_assign(cid: str, request: Request,
                      actor: dict = Depends(auth.require_admin),
                      db: DbSession = Depends(get_db)):
    body = await _body(request)
    sess, user = _get_case(db, cid)
    st = _case_state(sess)
    _check_version(st, body)
    spec = db.query(models.User).filter_by(id=body.get("specialist_id")).first()
    st["assigned_specialist"] = ({"id": str(spec.id),
                                  "display_name": _display_name(spec.username)}
                                 if spec else None)
    prev = st["status"]
    st["status"] = "assigned"
    _push_event(st, "assigned", _actor_name(actor), prev)
    _apply(db, sess, st, request, actor)
    return case_detail_payload(sess, user, st, db)


@router.post("/cases/{cid}/escalate")
async def case_escalate(cid: str, request: Request,
                        actor: dict = Depends(auth.require_admin),
                        db: DbSession = Depends(get_db)):
    body = await _body(request)
    sess, user = _get_case(db, cid)
    st = _case_state(sess)
    _check_version(st, body)
    prev = st["status"]
    st["status"] = "escalated"
    _push_event(st, "escalated", _actor_name(actor), prev)
    _apply(db, sess, st, request, actor)
    return case_detail_payload(sess, user, st, db)


@router.post("/cases/{cid}/close")
async def case_close(cid: str, request: Request,
                     actor: dict = Depends(auth.require_admin),
                     db: DbSession = Depends(get_db)):
    body = await _body(request)
    sess, user = _get_case(db, cid)
    st = _case_state(sess)
    _check_version(st, body)
    prev = st["status"]
    st["status"] = "closed"
    st["closed_at"] = _now()
    st["resolution_note"] = body.get("resolution_note")
    _push_event(st, "closed", _actor_name(actor), prev)
    _apply(db, sess, st, request, actor)
    return case_detail_payload(sess, user, st, db)


@router.post("/cases/{cid}/reopen")
async def case_reopen(cid: str, request: Request,
                      actor: dict = Depends(auth.require_admin),
                      db: DbSession = Depends(get_db)):
    body = await _body(request)
    sess, user = _get_case(db, cid)
    st = _case_state(sess)
    _check_version(st, body)
    prev = st["status"]
    st["status"] = "monitoring"
    st["closed_at"] = None
    _push_event(st, "reopened", _actor_name(actor), prev)
    _apply(db, sess, st, request, actor)
    return case_detail_payload(sess, user, st, db)


@router.post("/cases/{cid}/note")
async def case_note(cid: str, request: Request,
                    actor: dict = Depends(auth.require_admin),
                    db: DbSession = Depends(get_db)):
    body = await _body(request)
    sess, user = _get_case(db, cid)
    st = _case_state(sess)
    st["notes"].insert(0, {
        "id": str(uuid.uuid4()), "author_name": _actor_name(actor),
        "content": body.get("content", ""), "created_at": _now(),
    })
    _push_event(st, "note_added", _actor_name(actor), st["status"])
    _apply(db, sess, st, request, actor)
    return case_detail_payload(sess, user, st, db)


def case_detail_payload(sess, user, st, db):
    """Detail payload reused by mutation responses."""
    content = ""
    try:
        content = decrypt_str(sess.user_input_enc) or ""
    except Exception:
        content = ""
    base = _list_item(sess, user)
    base.update({
        "ai_confidence": sess.confidence,
        "source_type": "ai_message",
        "source": {"content": content, "created_at": sess.created_at.isoformat(),
                   "session_id": str(sess.id)},
        "signals": [], "actions": [], "notes": st["notes"],
        "attachments": [], "closed_at": st["closed_at"],
    })
    return base
