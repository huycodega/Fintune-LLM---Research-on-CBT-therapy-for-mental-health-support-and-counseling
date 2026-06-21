"""
Learning content — CBT lessons + support resources.

Public (any authenticated user — powers BaiHoc / TaiNguyen):
  GET  /api/lessons                — published lessons (filterable)
  GET  /api/lessons/{lid}          — one lesson (bumps view count)
  GET  /api/resources              — published resources (filterable)
  GET  /api/resources/{rid}        — one resource

Admin (require_admin — powers LessonsAdmin / ResourcesAdmin):
  GET    /api/admin/lessons        — ALL lessons incl. drafts (+ stats)
  POST   /api/admin/lessons        — create
  PATCH  /api/admin/lessons/{lid}  — update
  DELETE /api/admin/lessons/{lid}  — delete
  GET    /api/admin/resources      — ALL resources incl. drafts (+ stats)
  POST   /api/admin/resources      — create
  PATCH  /api/admin/resources/{rid}— update
  DELETE /api/admin/resources/{rid}— delete

NOT PHI — public educational content, stored as plain text. All admin writes
are audited.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.core import auth, audit as audit_mod
from app.db import models
from app.db.session import get_db
from app.schemas.api import (
    LessonIn, LessonUpdateIn, ResourceIn, ResourceUpdateIn, LessonProgressIn,
)


router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────────────────
# serializers
# ─────────────────────────────────────────────────────────────────────────────
def _lesson_out(l: models.Lesson) -> dict:
    return {
        "id": str(l.id),
        "title": l.title,
        "description": l.description or "",
        "category": l.category or "",
        "level": l.level,
        "duration": l.duration or "",
        "content": l.content or "",
        "objectives": l.objectives or [],
        "tags": l.tags or [],
        "status": l.status,
        "author": l.author or "",
        "views": l.views,
        "created_at": l.created_at.isoformat() if l.created_at else None,
        "updated_at": l.updated_at.isoformat() if l.updated_at else None,
    }


def _resource_out(r: models.Resource) -> dict:
    return {
        "id": str(r.id),
        "type": r.type,
        "title": r.title,
        "description": r.description or "",
        "category": r.category or "",
        "duration": r.duration or "",
        "url": r.url or "",
        "content": r.content or "",
        "status": r.status,
        "urgent": r.urgent,
        "owner": r.owner or "",
        "tags": r.tags or [],
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _get_lesson(db: Session, lid: str) -> models.Lesson:
    try:
        uid = uuid.UUID(lid)
    except ValueError:
        raise HTTPException(404, "Lesson not found")
    l = db.query(models.Lesson).filter_by(id=uid).first()
    if not l:
        raise HTTPException(404, "Lesson not found")
    return l


def _get_resource(db: Session, rid: str) -> models.Resource:
    try:
        uid = uuid.UUID(rid)
    except ValueError:
        raise HTTPException(404, "Resource not found")
    r = db.query(models.Resource).filter_by(id=uid).first()
    if not r:
        raise HTTPException(404, "Resource not found")
    return r


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC — lessons
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/lessons")
def list_lessons(category: str = Query(""), level: str = Query(""),
                 _: dict = Depends(auth.current_user),
                 db: Session = Depends(get_db)):
    q = db.query(models.Lesson).filter_by(status="published")
    if category:
        q = q.filter(models.Lesson.category == category)
    if level:
        q = q.filter(models.Lesson.level == level)
    rows = q.order_by(models.Lesson.created_at.desc()).all()
    return {"lessons": [_lesson_out(l) for l in rows]}


@router.get("/lessons/{lid}")
def get_lesson(lid: str, _: dict = Depends(auth.current_user),
               db: Session = Depends(get_db)):
    l = _get_lesson(db, lid)
    if l.status != "published":
        raise HTTPException(404, "Lesson not found")
    l.views = (l.views or 0) + 1
    db.flush()
    return _lesson_out(l)


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC — resources
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/resources")
def list_resources(type: str = Query(""), category: str = Query(""),
                   _: dict = Depends(auth.current_user),
                   db: Session = Depends(get_db)):
    q = db.query(models.Resource).filter(
        models.Resource.status != "draft")
    if type:
        q = q.filter(models.Resource.type == type)
    if category:
        q = q.filter(models.Resource.category == category)
    rows = q.order_by(models.Resource.created_at.desc()).all()
    return {"resources": [_resource_out(r) for r in rows]}


@router.get("/resources/{rid}")
def get_resource(rid: str, _: dict = Depends(auth.current_user),
                 db: Session = Depends(get_db)):
    r = _get_resource(db, rid)
    if r.status == "draft":
        raise HTTPException(404, "Resource not found")
    return _resource_out(r)


# ═════════════════════════════════════════════════════════════════════════════
# PER-USER lesson progress
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/my/lesson-progress")
def my_lesson_progress(user: dict = Depends(auth.current_user),
                       db: Session = Depends(get_db)):
    """All of THIS user's lesson progress, keyed by lesson id."""
    rows = (db.query(models.UserLessonProgress)
              .filter_by(user_id=user["uid"]).all())
    return {"progress": {str(r.lesson_id): {
        "progress_pct": r.progress_pct,
        "status": r.status,
        "completed_steps": r.completed_steps or [],
    } for r in rows}}


@router.post("/my/lesson-progress/{lid}")
def set_lesson_progress(lid: str, body: LessonProgressIn,
                        user: dict = Depends(auth.current_user),
                        db: Session = Depends(get_db)):
    """Upsert this user's progress on a lesson (>=100% => completed)."""
    lesson = db.query(models.Lesson).filter_by(id=lid).first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    pct = max(0, min(100, int(body.progress_pct)))
    steps = body.completed_steps or []
    status = "completed" if pct >= 100 else "in_progress"
    row = (db.query(models.UserLessonProgress)
             .filter_by(user_id=user["uid"], lesson_id=lid).first())
    if row is None:
        row = models.UserLessonProgress(
            user_id=user["uid"], lesson_id=lid,
            progress_pct=pct, completed_steps=steps, status=status)
        db.add(row)
    else:
        row.progress_pct = pct
        row.completed_steps = steps
        row.status = status
    db.flush()
    return {"ok": True, "lesson_id": lid,
            "progress_pct": pct, "status": status}


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN — lessons CRUD
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/admin/lessons")
def admin_list_lessons(_: dict = Depends(auth.require_admin),
                       db: Session = Depends(get_db)):
    rows = (db.query(models.Lesson)
              .order_by(models.Lesson.created_at.desc()).all())
    published = sum(1 for l in rows if l.status == "published")
    return {
        "lessons": [_lesson_out(l) for l in rows],
        "stats": {
            "total": len(rows),
            "published": published,
            "draft": len(rows) - published,
            "views": sum(l.views or 0 for l in rows),
        },
    }


@router.post("/admin/lessons")
def admin_create_lesson(body: LessonIn, request: Request,
                        actor: dict = Depends(auth.require_admin),
                        db: Session = Depends(get_db)):
    l = models.Lesson(
        title=body.title, description=body.description,
        category=body.category, level=body.level, duration=body.duration,
        content=body.content, objectives=body.objectives, tags=body.tags,
        status=body.status, author=body.author or actor.get("username"),
    )
    db.add(l)
    db.flush()
    audit_mod.audit(db, action="lesson_create", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="lesson", resource_id=l.id,
                    detail={"title": l.title})
    return _lesson_out(l)


@router.patch("/admin/lessons/{lid}")
def admin_update_lesson(lid: str, body: LessonUpdateIn, request: Request,
                        actor: dict = Depends(auth.require_admin),
                        db: Session = Depends(get_db)):
    l = _get_lesson(db, lid)
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(l, k, v)
    db.flush()
    audit_mod.audit(db, action="lesson_update", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="lesson", resource_id=l.id,
                    detail={"fields": list(changes.keys())})
    return _lesson_out(l)


@router.delete("/admin/lessons/{lid}")
def admin_delete_lesson(lid: str, request: Request,
                        actor: dict = Depends(auth.require_admin),
                        db: Session = Depends(get_db)):
    l = _get_lesson(db, lid)
    title = l.title
    db.delete(l)
    db.flush()
    audit_mod.audit(db, action="lesson_delete", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="lesson", resource_id=None,
                    detail={"title": title})
    return {"ok": True, "id": lid}


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN — resources CRUD
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/admin/resources")
def admin_list_resources(_: dict = Depends(auth.require_admin),
                         db: Session = Depends(get_db)):
    rows = (db.query(models.Resource)
              .order_by(models.Resource.created_at.desc()).all())
    by_type = {}
    for r in rows:
        by_type[r.type] = by_type.get(r.type, 0) + 1
    return {
        "resources": [_resource_out(r) for r in rows],
        "stats": {
            "total": len(rows),
            "urgent": sum(1 for r in rows if r.urgent),
            "by_type": by_type,
        },
    }


@router.post("/admin/resources")
def admin_create_resource(body: ResourceIn, request: Request,
                          actor: dict = Depends(auth.require_admin),
                          db: Session = Depends(get_db)):
    r = models.Resource(
        type=body.type, title=body.title, description=body.description,
        category=body.category, duration=body.duration, url=body.url,
        content=body.content, status=body.status, urgent=body.urgent,
        owner=body.owner or actor.get("username"), tags=body.tags,
    )
    db.add(r)
    db.flush()
    audit_mod.audit(db, action="resource_create", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="resource", resource_id=r.id,
                    detail={"title": r.title, "type": r.type})
    return _resource_out(r)


@router.patch("/admin/resources/{rid}")
def admin_update_resource(rid: str, body: ResourceUpdateIn, request: Request,
                          actor: dict = Depends(auth.require_admin),
                          db: Session = Depends(get_db)):
    r = _get_resource(db, rid)
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(r, k, v)
    db.flush()
    audit_mod.audit(db, action="resource_update", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="resource", resource_id=r.id,
                    detail={"fields": list(changes.keys())})
    return _resource_out(r)


@router.delete("/admin/resources/{rid}")
def admin_delete_resource(rid: str, request: Request,
                          actor: dict = Depends(auth.require_admin),
                          db: Session = Depends(get_db)):
    r = _get_resource(db, rid)
    title = r.title
    db.delete(r)
    db.flush()
    audit_mod.audit(db, action="resource_delete", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="resource", resource_id=None,
                    detail={"title": title})
    return {"ok": True, "id": rid}
