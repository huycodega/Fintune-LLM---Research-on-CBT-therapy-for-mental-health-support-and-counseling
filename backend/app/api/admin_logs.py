"""
Admin — System Logs (LogsAdmin page).

A reporting view over the append-only ``audit_trail``. The legacy
``GET /api/admin/audit`` (admin.py) returns the latest 100 rows unfiltered;
these endpoints add server-side stats, filtering, search and pagination so the
System Logs page can stop falling back to demo data.

  GET  /api/admin/logs          — paginated + filterable feed (+ facets + stats)
  GET  /api/admin/logs/stats    — today's headline counts with trend vs yesterday
  GET  /api/admin/logs/{log_id} — single event detail

`severity` (success | failed | warning) is derived from the action name so the
frontend can colour rows without owning the mapping.
"""
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.core import auth
from app.db import models
from app.db.session import get_db


router = APIRouter(prefix="/api/admin/logs")


# ── Classification ───────────────────────────────────────────────────────────
_FAILED = ("failed", "reject", "error", "denied")
_WARNING = ("unauthorized", "suspend", "delete", "triage_l0", "triage_l1",
            "need_improvement")
_EXPORT = ("export", "dpo", "download")


def _severity(action: str) -> str:
    a = (action or "").lower()
    if any(tok in a for tok in _FAILED):
        return "failed"
    if any(tok in a for tok in _WARNING):
        return "warning"
    return "success"


def _is_admin_action(role: Optional[str]) -> bool:
    return (role or "") in ("admin", "clinician", "manager", "system")


def _serialize(r: models.AuditTrail) -> dict:
    return {
        "id": str(r.id),
        "ts": r.ts.isoformat() if r.ts else None,
        "actor": r.actor_username or "System",
        "role": r.actor_role or "system",
        "action": r.action,
        "resource_type": r.resource_type,
        "resource_id": str(r.resource_id) if r.resource_id else None,
        "ip": str(r.ip_address) if r.ip_address else None,
        "user_agent": r.user_agent,
        "severity": _severity(r.action),
        "detail": r.detail or {},
    }


# ── Time helpers (UTC day boundaries) ────────────────────────────────────────
def _day_bounds(day):
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _count(db: Session, start, end, *predicates) -> int:
    q = (db.query(func.count(models.AuditTrail.id))
         .filter(models.AuditTrail.ts >= start, models.AuditTrail.ts < end))
    for p in predicates:
        q = q.filter(p)
    return q.scalar() or 0


def _trend(today: int, yesterday: int) -> dict:
    if yesterday <= 0:
        pct = 100.0 if today else 0.0
        direction = "up" if today else "flat"
    else:
        change = (today - yesterday) / yesterday * 100.0
        pct = round(abs(change), 1)
        direction = "up" if change > 0 else "down" if change < 0 else "flat"
    return {"pct": pct, "direction": direction}


def _stats(db: Session) -> dict:
    AT = models.AuditTrail
    today = datetime.now(timezone.utc).date()
    t_start, t_end = _day_bounds(today)
    y_start, y_end = _day_bounds(today - timedelta(days=1))

    failed = func.lower(AT.action).like("%failed%")
    admin = AT.actor_role.in_(("admin", "clinician", "manager", "system"))
    export = or_(*[func.lower(AT.action).like(f"%{tok}%") for tok in _EXPORT])

    def block(start, end):
        return {
            "total": _count(db, start, end),
            "failed_logins": _count(db, start, end, failed),
            "admin_actions": _count(db, start, end, admin),
            "data_exports": _count(db, start, end, export),
        }

    cur, prev = block(t_start, t_end), block(y_start, y_end)
    return {
        "total_events": cur["total"],
        "failed_logins": cur["failed_logins"],
        "admin_actions": cur["admin_actions"],
        "data_exports": cur["data_exports"],
        "trends": {k: _trend(cur[k], prev[k]) for k in cur},
    }


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/stats")
def logs_stats(_: dict = Depends(auth.require_admin),
               db: Session = Depends(get_db)):
    return _stats(db)


@router.get("")
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    action: str = Query(""),
    actor: str = Query(""),
    severity: str = Query(""),
    search: str = Query(""),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    _: dict = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    AT = models.AuditTrail
    q = db.query(AT)
    if action:
        q = q.filter(AT.action == action)
    if actor:
        q = q.filter(AT.actor_username == actor)
    if start:
        q = q.filter(AT.ts >= start)
    if end:
        q = q.filter(AT.ts < end)
    if search:
        like = f"%{search.lower()}%"
        q = q.filter(or_(
            func.lower(AT.action).like(like),
            func.lower(func.coalesce(AT.actor_username, "")).like(like),
            func.lower(func.coalesce(AT.resource_type, "")).like(like),
            cast(AT.ip_address, String).ilike(like),
        ))

    # severity is derived, not a column → filter in Python after a bounded
    # fetch (cap the scan so a huge audit trail can't blow up memory).
    rows = q.order_by(AT.ts.desc()).limit(5000).all()
    if severity in ("success", "failed", "warning"):
        rows = [r for r in rows if _severity(r.action) == severity]

    total = len(rows)
    page_count = max(1, (total + page_size - 1) // page_size)
    page = min(page, page_count)
    window = rows[(page - 1) * page_size: page * page_size]

    # Facets are built from the (severity-filtered) result set so the dropdowns
    # only ever offer values that actually return rows.
    actors = sorted({r.actor_username or "System" for r in rows})
    actions = sorted({r.action for r in rows})

    return {
        "logs": [_serialize(r) for r in window],
        "total": total,
        "page": page,
        "page_size": page_size,
        "page_count": page_count,
        "facets": {"actors": actors, "actions": actions},
        "stats": _stats(db),
    }


@router.get("/{log_id}")
def log_detail(log_id: str, _: dict = Depends(auth.require_admin),
               db: Session = Depends(get_db)):
    import uuid
    try:
        uid = uuid.UUID(log_id)
    except ValueError:
        raise HTTPException(404, "Log entry not found")
    r = db.query(models.AuditTrail).filter_by(id=uid).first()
    if not r:
        raise HTTPException(404, "Log entry not found")
    return _serialize(r)
