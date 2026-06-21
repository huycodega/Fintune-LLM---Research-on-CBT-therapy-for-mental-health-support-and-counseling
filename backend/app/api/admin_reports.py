"""Aggregated reporting endpoints for the admin dashboard."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import auth
from app.db import models
from app.db.session import get_db
from app.services.reporting import (
    ScreeningFact, SessionFact, build_report, report_range, shift_month,
)


router = APIRouter(prefix="/api/admin/reports")


def _range(start_date: Optional[date], end_date: Optional[date]):
    try:
        return report_range(start_date, end_date)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def _load_report(db: Session, start: date, end: date):
    days = (end - start).days + 1
    previous_start = start - timedelta(days=days)
    monthly_start = shift_month(end.replace(day=1), -6)
    history_start = min(previous_start - timedelta(days=6), monthly_start)
    start_dt = datetime.combine(history_start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    screening_rows = (
        db.query(models.Screening.created_at, models.Screening.phq9_level,
                 models.Screening.gad7_level, models.Screening.phq9_answers)
        .filter(models.Screening.created_at >= start_dt,
                models.Screening.created_at < end_dt)
        .all()
    )
    session_rows = (
        db.query(models.Session.created_at, models.Session.completed_at,
                 models.Session.status, models.Session.triage_level,
                 models.Session.analysis, models.ReviewQueue.claimed_by,
                 models.ReviewQueue.resolution, models.ReviewQueue.resolved_at)
        .outerjoin(models.ReviewQueue,
                   models.ReviewQueue.session_id == models.Session.id)
        .filter(or_(
            (models.Session.created_at >= start_dt) &
            (models.Session.created_at < end_dt),
            (models.ReviewQueue.resolved_at >= start_dt) &
            (models.ReviewQueue.resolved_at < end_dt),
        ))
        .all()
    )
    screenings = [ScreeningFact(
        created_at=row.created_at, phq9_level=row.phq9_level,
        gad7_level=row.gad7_level, phq9_answers=row.phq9_answers,
    ) for row in screening_rows]
    sessions = [SessionFact(
        created_at=row.created_at, completed_at=row.completed_at,
        status=row.status, triage_level=row.triage_level,
        analysis=row.analysis, claimed=row.claimed_by is not None,
        resolution=row.resolution, resolved_at=row.resolved_at,
    ) for row in session_rows]
    return build_report(screenings, sessions, start, end)


@router.get("")
def report_analytics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _: dict = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    start, end = _range(start_date, end_date)
    return _load_report(db, start, end)


@router.get("/export")
def export_report(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _: dict = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    start, end = _range(start_date, end_date)
    report = _load_report(db, start, end)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Month", "Screenings", "High Risk Rate", "Avg. Processing Seconds",
                     "AI Approval Rate", "Emergency Cases", "Trend"])
    for row in report["monthly_summary"]:
        writer.writerow([
            row["month"], row["screenings"], row["high_risk_rate"],
            row["avg_processing_seconds"], row["ai_approval_rate"],
            row["emergency_cases"],
            f'{"-" if row["trend_direction"] == "down" else "+"}{row["trend_pct"]}%',
        ])
    body = stream.getvalue().encode("utf-8-sig")
    filename = f"mindcare-report-{start.isoformat()}-{end.isoformat()}.csv"
    return StreamingResponse(
        iter([body]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
