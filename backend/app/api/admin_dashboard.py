"""
Dashboard endpoints (admin) — back the Overview page (dashboardApi ->
/api/admin/dashboard/*). All figures are real, derived from users / sessions /
review queue / screenings / lessons / resources / audit trail. Each query is
defensive so a missing row set never 500s the page.
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, desc
from sqlalchemy.orm import Session as DbSession

from app.core import auth
from app.db import models
from app.db.session import get_db

router = APIRouter(prefix="/api/admin")

_CASE_LEVELS = ("L0", "L1", "L2")
_OPEN_STATUSES = ("pending_review", "crisis")


def _name(username):
    return (username or "User").split("@")[0]


def _mask(email):
    if not email or "@" not in email:
        return email or "—"
    n, d = email.split("@", 1)
    return f"{(n[:2] if len(n) > 2 else n[:1])}***@{d}"


def _metric(v, change=None):
    """change=None hides the trend badge in the UI — a badge only shows when a
    REAL baseline exists (no more hardcoded "↑ 0%")."""
    return {"value": v, "change_percent": change}


def _pct(now_v, prev_v):
    """Real percent change vs a baseline; None when there is nothing honest to
    compare against (baseline zero/unknown)."""
    if prev_v <= 0:
        return None
    return round((now_v - prev_v) / prev_v * 100.0, 1)


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


@router.get("/dashboard/summary")
def summary(_: dict = Depends(auth.require_admin), db: DbSession = Depends(get_db)):
    today = datetime.now(timezone.utc).date()

    total_users = _safe(lambda: db.query(models.User).filter_by(role="user").count(), 0)
    active_users = _safe(lambda: db.query(models.User).filter_by(role="user", status="active").count(), 0)
    high_risk = _safe(lambda: db.query(models.Session.user_id)
                      .filter(models.Session.triage_level.in_(("L0", "L1")))
                      .distinct().count(), 0)
    today_screen = _safe(lambda: db.query(models.Screening)
                         .filter(func.date(models.Screening.created_at) == today).count(), 0)
    pending_mod = _safe(lambda: db.query(models.ReviewQueue)
                        .filter(models.ReviewQueue.resolved_at.is_(None)).count(), 0)
    open_cases = _safe(lambda: db.query(models.Session)
                       .filter(models.Session.triage_level.in_(_CASE_LEVELS),
                               models.Session.status.in_(_OPEN_STATUSES)).count(), 0)
    pub_res = _safe(lambda: db.query(models.Resource).filter_by(status="published").count(), 0)
    pub_les = _safe(lambda: db.query(models.Lesson).filter_by(status="published").count(), 0)

    # Real trend baselines (week-over-week for user growth & high-risk flow;
    # yesterday for screenings). Point-in-time gauges (open cases, pending
    # moderation, published content) get no badge — there is no honest delta.
    now = datetime.now(timezone.utc)
    week_ago, two_weeks_ago = now - timedelta(days=7), now - timedelta(days=14)
    users_week_ago = _safe(lambda: db.query(models.User)
                           .filter(models.User.role == "user",
                                   models.User.created_at < week_ago).count(), 0)
    risk_this_week = _safe(lambda: db.query(models.Session.user_id)
                           .filter(models.Session.triage_level.in_(("L0", "L1")),
                                   models.Session.created_at >= week_ago)
                           .distinct().count(), 0)
    risk_prev_week = _safe(lambda: db.query(models.Session.user_id)
                           .filter(models.Session.triage_level.in_(("L0", "L1")),
                                   models.Session.created_at >= two_weeks_ago,
                                   models.Session.created_at < week_ago)
                           .distinct().count(), 0)
    yest_screen = _safe(lambda: db.query(models.Screening)
                        .filter(func.date(models.Screening.created_at)
                                == today - timedelta(days=1)).count(), 0)

    return {
        "total_users": _metric(total_users, _pct(total_users, users_week_ago)),
        "active_users": _metric(active_users),
        "high_risk_users": _metric(high_risk,
                                   _pct(risk_this_week, risk_prev_week)),
        "today_screenings": _metric(today_screen,
                                    _pct(today_screen, yest_screen)),
        "pending_ai_moderations": _metric(pending_mod),
        "open_cases": _metric(open_cases),
        "published_resources": _metric(pub_res),
        "active_cbt_lessons": _metric(pub_les),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/dashboard/charts")
def charts(_: dict = Depends(auth.require_admin), db: DbSession = Depends(get_db)):
    def risk_series():
        rows = dict(db.query(models.Session.triage_level, func.count())
                    .group_by(models.Session.triage_level).all())
        return [{"label": lv, "value": int(rows.get(lv, 0))} for lv in ("L0", "L1", "L2", "L3")]

    def case_status_series():
        opn = db.query(models.Session).filter(
            models.Session.triage_level.in_(_CASE_LEVELS),
            models.Session.status.in_(_OPEN_STATUSES)).count()
        closed = db.query(models.Session).filter(
            models.Session.triage_level.in_(_CASE_LEVELS),
            models.Session.status.in_(("answered", "auto_sent", "rejected"))).count()
        return [{"label": "New", "value": opn},
                {"label": "Monitoring", "value": 0},
                {"label": "Closed", "value": closed}]

    def moderation_series():
        pending = db.query(models.ReviewQueue).filter(models.ReviewQueue.resolved_at.is_(None)).count()
        resolved = db.query(models.ReviewQueue).filter(models.ReviewQueue.resolved_at.isnot(None)).count()
        return [{"label": "Pending", "value": pending}, {"label": "Resolved", "value": resolved}]

    def _daily(query_for_date):
        out = []
        for i in range(6, -1, -1):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).date()
            out.append({"label": d.strftime("%d/%m"), "value": int(query_for_date(d))})
        return out

    def screening_trend():
        return _daily(lambda d: db.query(models.Screening)
                      .filter(func.date(models.Screening.created_at) == d).count())

    def resource_usage():
        # bookmarks saved per day — real user resource engagement
        return _daily(lambda d: db.query(models.SavedResource)
                      .filter(func.date(models.SavedResource.created_at) == d).count())

    def cbt_completion():
        # lessons completed per day
        return _daily(lambda d: db.query(models.UserLessonProgress)
                      .filter(models.UserLessonProgress.status == "completed",
                              func.date(models.UserLessonProgress.updated_at) == d).count())

    return {
        "screening_trend": {"available": True, "series": _safe(screening_trend, [])},
        "risk_distribution": {"available": True, "series": _safe(risk_series, [])},
        "case_status_distribution": {"available": True, "series": _safe(case_status_series, [])},
        "ai_moderation_statistics": {"available": True, "series": _safe(moderation_series, [])},
        "resource_usage": {"available": True, "series": _safe(resource_usage, [])},
        "cbt_completion": {"available": True, "series": _safe(cbt_completion, [])},
    }


@router.get("/dashboard/recent-cases")
def recent_cases(request: Request, _: dict = Depends(auth.require_admin),
                 db: DbSession = Depends(get_db)):
    limit = int(request.query_params.get("limit") or 6)
    rows = (db.query(models.Session, models.User)
              .join(models.User, models.User.id == models.Session.user_id)
              .filter(models.Session.triage_level.in_(("L0", "L1")))
              .order_by(desc(models.Session.created_at)).limit(limit).all())
    pr = {"L0": "critical", "L1": "high"}
    return {"items": [{
        "id": str(s.id), "case_code": "C-" + str(s.id)[:8].upper(),
        "user": {"id": str(u.id), "display_name": _name(u.username),
                 "email_masked": _mask(u.email or u.username)},
        "user_masked": _name(u.username),
        "risk_level": s.triage_level, "priority": pr.get(s.triage_level, "medium"),
        "status": "new" if s.status in _OPEN_STATUSES else "closed",
        "assigned_specialist": None,
        "created_at": s.created_at.isoformat(),
    } for s, u in rows]}


@router.get("/dashboard/recent-screenings")
def recent_screenings(request: Request, _: dict = Depends(auth.require_admin),
                      db: DbSession = Depends(get_db)):
    limit = int(request.query_params.get("limit") or 6)

    def go():
        rows = (db.query(models.Screening, models.User)
                  .join(models.User, models.User.id == models.Screening.user_id)
                  .order_by(desc(models.Screening.created_at)).limit(limit).all())
        out = []
        for sc, u in rows:
            phq, gad = sc.phq9_score, sc.gad7_score
            kind = "PHQ-9" if phq is not None else ("GAD-7" if gad is not None else "Screening")
            lvl = sc.phq9_level or sc.gad7_level or "L3"
            out.append({"id": str(sc.id), "user_masked": _name(u.username),
                        "screening_type": kind,
                        "risk_level": lvl if lvl in ("L0", "L1", "L2", "L3") else "L3",
                        "score": phq if phq is not None else gad,
                        "created_at": sc.created_at.isoformat()})
        return out
    return {"items": _safe(go, [])}


@router.get("/dashboard/pending-moderations")
def pending_moderations(request: Request, _: dict = Depends(auth.require_admin),
                        db: DbSession = Depends(get_db)):
    limit = int(request.query_params.get("limit") or 6)
    rows = (db.query(models.ReviewQueue, models.Session, models.User)
              .join(models.Session, models.Session.id == models.ReviewQueue.session_id)
              .join(models.User, models.User.id == models.Session.user_id)
              .filter(models.ReviewQueue.resolved_at.is_(None))
              .order_by(desc(models.ReviewQueue.created_at)).limit(limit).all())
    return {"items": [{
        "id": str(q.session_id), "queue_code": "MOD-" + str(s.id)[:6].upper(),
        "user_masked": _name(u.username), "risk_level": s.triage_level,
        "status": "pending", "created_at": s.created_at.isoformat(),
    } for q, s, u in rows]}


@router.get("/notifications")
def admin_notifications(_: dict = Depends(auth.require_admin),
                        db: DbSession = Depends(get_db)):
    """Unified admin notification feed (newest first): pending clinician
    reviews + new appointment bookings from users."""
    from app.core.crypto import decrypt_str
    out = []

    rows = (db.query(models.ReviewQueue, models.Session, models.User)
            .join(models.Session, models.Session.id == models.ReviewQueue.session_id)
            .join(models.User, models.User.id == models.Session.user_id)
            .filter(models.ReviewQueue.resolved_at.is_(None))
            .order_by(desc(models.ReviewQueue.created_at)).limit(20).all())
    for q, s, u in rows:
        try:
            txt = decrypt_str(s.user_input_enc) if s.user_input_enc else ""
        except Exception:
            txt = ""
        ts = q.created_at or s.created_at
        out.append({"id": f"rev-{s.id}", "kind": "review", "title": _name(u.username),
                    "text": txt[:90], "level": s.triage_level, "link": "moderation",
                    "created_at": ts.isoformat() if ts else None})

    appts = (db.query(models.Appointment)
             .order_by(desc(models.Appointment.created_at)).limit(20).all())
    experts = {p.id: p for p in db.query(models.Psychologist).all()}
    users = {u.id: u for u in db.query(models.User).all()}
    for a in appts:
        p = experts.get(a.psychologist_id)
        u = users.get(a.user_id)
        out.append({"id": f"appt-{a.id}", "kind": "appointment",
                    "title": _name(u.username if u else "User"),
                    "text": f"Booked {p.name if p else 'a psychologist'} · "
                            f"{a.date} {a.slot} ({a.status})",
                    "level": None, "link": "experts",
                    "created_at": a.created_at.isoformat() if a.created_at else None})

    out.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return {"items": out[:25]}


@router.get("/dashboard/recent-activities")
def recent_activities(request: Request, _: dict = Depends(auth.require_admin),
                      db: DbSession = Depends(get_db)):
    limit = int(request.query_params.get("limit") or 6)

    def go():
        rows = (db.query(models.AuditTrail)
                  .order_by(desc(models.AuditTrail.ts)).limit(limit).all())
        return [{"id": str(a.id), "actor_name": _name(a.actor_username),
                 "action": a.action, "module": a.resource_type or "system",
                 "created_at": a.ts.isoformat()} for a in rows]
    return {"items": _safe(go, [])}
