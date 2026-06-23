"""
Admin — System Settings (SettingsAdmin page).

  GET   /api/admin/settings              — all sections (defaults + overrides)
  GET   /api/admin/settings/{section}    — one section
  PUT   /api/admin/settings/{section}    — upsert one section (partial for
                                            object sections; full list replace
                                            for thresholds/rules)
  POST  /api/admin/settings/backup       — record a "Back Up Now" action
  POST  /api/admin/settings/restore      — record a "Restore Data" action

Section value shapes are owned by app.services.settings_store. All writes are
audited. NOT PHI — system configuration only.
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import auth, audit as audit_mod
from app.core.config import settings as cfg
from app.db import models
from app.db.session import get_db
from app.services import settings_store


router = APIRouter(prefix="/api/admin/settings")


def _roles(db: Session) -> list[dict]:
    """Real role membership from the users table (no mock counts)."""
    counts = dict(
        db.query(models.User.role, func.count(models.User.id))
        .filter(models.User.deleted_at.is_(None))
        .group_by(models.User.role).all()
    )
    return [
        {"role": "Administrator", "permission": "Full Access",
         "users": int(counts.get("admin", 0)), "tone": "green"},
        {"role": "Clinician", "permission": "Review & Counselling",
         "users": int(counts.get("clinician", 0)), "tone": "purple"},
        {"role": "User", "permission": "Standard Access",
         "users": int(counts.get("user", 0)), "tone": "blue"},
    ]


def _integrations() -> list[dict]:
    """Connection status derived from the running configuration (no mock)."""
    return [
        {"name": "Email (SMTP)", "icon": "mail", "tone": "blue",
         "connected": bool(cfg.smtp_host)},
        {"name": "Google Sign-In (OAuth)", "icon": "key", "tone": "indigo",
         "connected": bool(cfg.google_oauth_client_id)},
        {"name": "SMS Gateway", "icon": "message", "tone": "green",
         "connected": False},
        {"name": "Google Analytics 4", "icon": "bars", "tone": "orange",
         "connected": False},
    ]


@router.get("")
def get_settings(_: dict = Depends(auth.require_admin),
                 db: Session = Depends(get_db)):
    data = settings_store.get_all(db)
    data["roles"] = _roles(db)
    data["integrations"] = _integrations()
    return data


@router.get("/{section}")
def get_section(section: str, _: dict = Depends(auth.require_admin),
                db: Session = Depends(get_db)):
    try:
        return {"section": section, "value": settings_store.get_section(db, section)}
    except KeyError:
        raise HTTPException(404, f"Unknown settings section '{section}'")


@router.put("/{section}")
def update_section(section: str, request: Request,
                   value: Any = Body(..., embed=False),
                   actor: dict = Depends(auth.require_admin),
                   db: Session = Depends(get_db)):
    try:
        merged = settings_store.save_section(
            db, section, value, updated_by=actor.get("username"))
    except KeyError:
        raise HTTPException(404, f"Unknown settings section '{section}'")
    except ValueError as e:
        raise HTTPException(422, str(e))
    audit_mod.audit(db, action="settings_update", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="settings", resource_id=None,
                    detail={"section": section})
    return {"ok": True, "section": section, "value": merged}


@router.post("/backup")
def backup_now(request: Request, actor: dict = Depends(auth.require_admin),
               db: Session = Depends(get_db)):
    ts = datetime.now(timezone.utc)
    audit_mod.audit(db, action="settings_backup", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="settings", resource_id=None,
                    detail={"at": ts.isoformat()})
    return {"ok": True, "action": "backup", "at": ts.isoformat()}


@router.post("/restore")
def restore_data(request: Request, actor: dict = Depends(auth.require_admin),
                 db: Session = Depends(get_db)):
    ts = datetime.now(timezone.utc)
    audit_mod.audit(db, action="settings_restore", actor=actor,
                    ip=auth.client_ip(request),
                    resource_type="settings", resource_id=None,
                    detail={"at": ts.isoformat()})
    return {"ok": True, "action": "restore", "at": ts.isoformat()}
