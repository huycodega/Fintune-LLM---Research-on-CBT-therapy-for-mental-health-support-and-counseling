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
from sqlalchemy.orm import Session

from app.core import auth, audit as audit_mod
from app.db.session import get_db
from app.services import settings_store


router = APIRouter(prefix="/api/admin/settings")


@router.get("")
def get_settings(_: dict = Depends(auth.require_admin),
                 db: Session = Depends(get_db)):
    return settings_store.get_all(db)


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
