"""
Admin system settings — defaults + persistence helpers.

The Settings page (admin_app/src/pages/SettingsAdmin.jsx) is organised into
sections. Each section is stored as a single row in ``app_settings`` keyed by
the section name; ``value`` is a JSON blob. Reads merge stored overrides on top
of DEFAULTS so a fresh database (no rows yet) still returns a complete,
well-formed payload, and newly-added keys get a sane default automatically.

NOT PHI — system configuration only.
"""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import models


# ── Defaults (mirror SettingsAdmin.jsx INITIAL / INITIAL_THRESHOLDS / RULES) ──
DEFAULTS: Dict[str, Any] = {
    "general": {
        "systemName": "MindCare AI",
        "timeZone": "(UTC+07:00) Bangkok, Hanoi, Jakarta",
        "language": "Vietnamese",
        "dateFormat": "DD/MM/YYYY",
        "timeFormat": "24-hour",
        "registration": True,
        "emailVerification": True,
    },
    "privacy": {
        "twoFactor": True,
        "timeout": "30 minutes",
        "passwordPolicy": True,
        "hideSensitive": True,
    },
    "notifications": {
        "email": True,
        "inApp": True,
        "emergencies": True,
        "dailySummary": False,
        "recipients": "admin@mindcare.ai, manager@mindcare.ai",
    },
    "hotline": {
        "primary": "1900 1234",
        "backup": "1900 5678",
        "workflow": "Call hotline → Notify specialist → Send email",
        "email": "crisis@mindcare.ai",
    },
    "backup": {
        "automatic": True,
        "retention": "30 days",
    },
    "thresholds": [
        {"level": "Low", "range": "0–24", "color": "#22C55E",
         "action": "Record Only", "tone": "low"},
        {"level": "Moderate", "range": "25–49", "color": "#F59E0B",
         "action": "Send Support Resources", "tone": "moderate"},
        {"level": "High", "range": "50–74", "color": "#EF4444",
         "action": "Notify Specialist", "tone": "high"},
        {"level": "Crisis", "range": "75–100", "color": "#DC2626",
         "action": "Trigger Emergency Workflow", "tone": "crisis"},
    ],
    "rules": [
        {"name": "Self-harm / Suicide", "icon": "alert", "tone": "red",
         "action": "Block Content & Trigger Emergency"},
        {"name": "Violence / Threats", "icon": "shield", "tone": "amber",
         "action": "Block Content & Forward to Specialist"},
        {"name": "Adult Content", "icon": "users", "tone": "purple",
         "action": "Block Content"},
        {"name": "Personal Information", "icon": "lock", "tone": "blue",
         "action": "Hide & Warn User"},
    ],
}

# Sections whose value is a JSON object (vs. a list); object sections get a
# shallow merge with their defaults, list sections are replaced wholesale.
OBJECT_SECTIONS = {"general", "privacy", "notifications", "hotline", "backup"}
LIST_SECTIONS = {"thresholds", "rules"}
SECTIONS = OBJECT_SECTIONS | LIST_SECTIONS


def _rows(db: Session) -> Dict[str, models.AppSetting]:
    return {row.section: row for row in db.query(models.AppSetting).all()}


def _stored(db: Session) -> Dict[str, Any]:
    return {section: row.value for section, row in _rows(db).items()}


def _merge_section(section: str, stored: Any) -> Any:
    default = DEFAULTS[section]
    if section in OBJECT_SECTIONS:
        merged = dict(default)
        if isinstance(stored, dict):
            merged.update({k: v for k, v in stored.items() if k in default})
        return merged
    # list section — use the stored list verbatim when present.
    if isinstance(stored, list) and stored:
        return stored
    return default


def get_all(db: Session) -> Dict[str, Any]:
    """Full settings payload: DEFAULTS overlaid with any stored overrides."""
    rows = _rows(db)
    out: Dict[str, Any] = {
        section: _merge_section(section, rows[section].value
                                if section in rows else None)
        for section in DEFAULTS
    }
    latest = max(rows.values(),
                 key=lambda r: r.updated_at.timestamp() if r.updated_at else 0.0,
                 default=None)
    out["meta"] = {
        "updated_at": (latest.updated_at.isoformat()
                       if latest and latest.updated_at else None),
        "updated_by": latest.updated_by if latest else None,
    }
    return out


def get_section(db: Session, section: str) -> Any:
    if section not in DEFAULTS:
        raise KeyError(section)
    stored = _stored(db).get(section)
    return _merge_section(section, stored)


def save_section(db: Session, section: str, value: Any,
                 updated_by: str | None) -> Any:
    """Upsert one section. For object sections the incoming value is merged
    onto the current effective value (partial updates allowed); list sections
    replace the whole list. Returns the merged effective value."""
    if section not in DEFAULTS:
        raise KeyError(section)

    if section in OBJECT_SECTIONS:
        if not isinstance(value, dict):
            raise ValueError(f"Section '{section}' expects an object")
        current = get_section(db, section)
        merged = dict(current)
        merged.update({k: v for k, v in value.items() if k in DEFAULTS[section]})
    else:
        if not isinstance(value, list):
            raise ValueError(f"Section '{section}' expects a list")
        merged = value

    row = db.query(models.AppSetting).filter_by(section=section).first()
    if row is None:
        row = models.AppSetting(section=section, value=merged,
                                updated_by=updated_by)
        db.add(row)
    else:
        row.value = merged
        row.updated_by = updated_by
        row.updated_at = func.now()
    db.flush()
    return merged
