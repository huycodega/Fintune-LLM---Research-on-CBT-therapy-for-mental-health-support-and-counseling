"""Privacy-conscious aggregation for the admin Reports dashboard.

The service operates on small, normalized facts so calculations can be tested
without a database and the API never needs to decrypt message content.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional


RISK_ORDER = ("low", "medium", "high", "emergency")
RISK_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "emergency": "Emergency",
}
TOPICS = ("Stress", "Anxiety", "Depression", "Relationships",
          "Academic Pressure", "Other")


@dataclass(frozen=True)
class ScreeningFact:
    created_at: datetime
    phq9_level: Optional[str] = None
    gad7_level: Optional[str] = None
    phq9_answers: Optional[list] = None


@dataclass(frozen=True)
class SessionFact:
    created_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "pending_review"
    triage_level: Optional[str] = None
    analysis: Optional[dict] = None
    claimed: bool = False
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None


def report_range(start_date: Optional[date], end_date: Optional[date],
                 today: Optional[date] = None) -> tuple[date, date]:
    end = end_date or today or datetime.now(timezone.utc).date()
    start = start_date or end - timedelta(days=7)
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    if (end - start).days > 365:
        raise ValueError("Report range cannot exceed 366 days")
    return start, end


def _day(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()


def _seconds(start: datetime, end: Optional[datetime]) -> Optional[float]:
    if end is None:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    value = (end - start).total_seconds()
    return value if value >= 0 else None


def _pct(value: float, total: float, digits: int = 2) -> float:
    return round((value / total) * 100, digits) if total else 0.0


def _change(current: float, previous: float) -> float:
    if not previous:
        return 0.0
    return round(((current - previous) / previous) * 100, 2)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def shift_month(value: date, amount: int) -> date:
    month_index = value.year * 12 + value.month - 1 + amount
    return date(month_index // 12, month_index % 12 + 1, 1)


def classify_screening(row: ScreeningFact) -> str:
    """Map PHQ-9/GAD-7 output to the four dashboard risk bands.

    A positive PHQ-9 item 9 is treated as emergency for reporting and review.
    It is checked before score bands so urgent signals are never diluted.
    """
    answers = row.phq9_answers or []
    try:
        if len(answers) >= 9 and int(answers[8]) > 0:
            return "emergency"
    except (TypeError, ValueError):
        pass
    if row.phq9_level in ("moderately_severe", "severe") or row.gad7_level == "severe":
        return "high"
    if row.phq9_level == "moderate" or row.gad7_level == "moderate":
        return "medium"
    return "low"


def _session_bucket(row: SessionFact) -> str:
    if row.status == "pending_review":
        return "in_progress" if row.claimed else "new"
    if row.status == "crisis":
        return "pending"
    if row.status in ("answered", "auto_sent"):
        return "completed"
    return "closed"


def _topic(row: SessionFact) -> str:
    analysis = row.analysis if isinstance(row.analysis, dict) else {}
    raw = " ".join(str(analysis.get(key, "")) for key in (
        "topic", "primary_topic", "emotion", "severity"))
    value = raw.lower()
    if any(word in value for word in ("relationship", "partner", "family", "isolation")):
        return "Relationships"
    if any(word in value for word in ("academic", "school", "study", "exam")):
        return "Academic Pressure"
    if any(word in value for word in ("depression", "sadness", "hopeless")):
        return "Depression"
    if any(word in value for word in ("anxiety", "fear", "panic", "worried")):
        return "Anxiety"
    if any(word in value for word in ("stress", "anger", "shame", "distress")):
        return "Stress"
    return "Other"


def _period_screenings(rows: Iterable[ScreeningFact], start: date, end: date):
    return [row for row in rows if start <= _day(row.created_at) <= end]


def _period_sessions(rows: Iterable[SessionFact], start: date, end: date):
    return [row for row in rows if start <= _day(row.created_at) <= end]


def _processing_average(rows: Iterable[SessionFact], end: Optional[date] = None) -> float:
    values = [_seconds(row.created_at, row.completed_at) for row in rows
              if row.completed_at is not None and
              (end is None or _day(row.completed_at) <= end)]
    valid = [value for value in values if value is not None]
    return sum(valid) / len(valid) if valid else 0.0


def _approval_rate(rows: Iterable[SessionFact], start: date, end: date) -> float:
    resolved = [row for row in rows if row.resolved_at and
                start <= _day(row.resolved_at) <= end and row.resolution]
    approved = sum(1 for row in resolved if row.resolution == "approve")
    return _pct(approved, len(resolved))


def _risk_rate(rows: Iterable[ScreeningFact]) -> float:
    rows = list(rows)
    elevated = sum(1 for row in rows if classify_screening(row) in ("high", "emergency"))
    return _pct(elevated, len(rows))


def _monthly_summary(screenings, sessions, end: date) -> list[dict[str, Any]]:
    output = []
    anchor = _month_start(end)
    for offset in range(6):
        start = shift_month(anchor, -offset)
        month_end = shift_month(start, 1) - timedelta(days=1)
        current_screenings = _period_screenings(screenings, start, month_end)
        current_sessions = _period_sessions(sessions, start, month_end)
        previous_start = shift_month(start, -1)
        previous_end = start - timedelta(days=1)
        previous_count = len(_period_screenings(screenings, previous_start, previous_end))
        trend = _change(len(current_screenings), previous_count)
        output.append({
            "month": start.strftime("%m/%Y"),
            "screenings": len(current_screenings),
            "high_risk_rate": _risk_rate(current_screenings),
            "avg_processing_seconds": round(_processing_average(current_sessions, month_end)),
            "ai_approval_rate": _approval_rate(sessions, start, month_end),
            "emergency_cases": sum(1 for row in current_sessions if row.triage_level == "L0"),
            "trend_pct": abs(trend),
            "trend_direction": "down" if trend < 0 else "up",
        })
    return output


def _insights(kpis: dict[str, Any]) -> list[dict[str, str]]:
    total_change = kpis["total_screenings"]["change_pct"]
    risk_change = kpis["high_risk_rate"]["change_points"]
    processing_change = kpis["average_processing_time"]["change_pct"]
    approval_change = kpis["ai_approval_rate"]["change_points"]
    processing_word = "decreased" if processing_change <= 0 else "increased"
    return [
        {"icon": "arrowUp" if total_change >= 0 else "arrowDown", "tone": "green",
         "title": "Screenings Increased" if total_change >= 0 else "Screenings Decreased",
         "text": f"Total screenings changed by {abs(total_change):.1f}% compared with the previous period. Demand trends should be monitored."},
        {"icon": "alert", "tone": "orange",
         "title": "High Risk Rate Increased" if risk_change >= 0 else "High Risk Rate Decreased",
         "text": f"High-risk rate changed by {abs(risk_change):.2f} percentage points. Review users showing elevated-risk signals."},
        {"icon": "clock", "tone": "blue",
         "title": "Processing Time Improved" if processing_change <= 0 else "Processing Time Increased",
         "text": f"Average processing time {processing_word} by {abs(processing_change):.1f}% across completed cases."},
        {"icon": "users", "tone": "purple",
         "title": "AI Performance Improved" if approval_change >= 0 else "AI Performance Needs Attention",
         "text": f"AI approval rate changed by {abs(approval_change):.2f} percentage points based on resolved reviews."},
    ]


def build_report(screenings: Iterable[ScreeningFact],
                 sessions: Iterable[SessionFact], start: date, end: date,
                 updated_at: Optional[datetime] = None) -> dict[str, Any]:
    screenings = list(screenings)
    sessions = list(sessions)
    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    current_screenings = _period_screenings(screenings, start, end)
    previous_screenings = _period_screenings(screenings, previous_start, previous_end)
    current_sessions = _period_sessions(sessions, start, end)
    previous_sessions = _period_sessions(sessions, previous_start, previous_end)

    current_risk = _risk_rate(current_screenings)
    previous_risk = _risk_rate(previous_screenings)
    current_processing = _processing_average(current_sessions, end)
    previous_processing = _processing_average(previous_sessions, previous_end)
    current_approval = _approval_rate(sessions, start, end)
    previous_approval = _approval_rate(sessions, previous_start, previous_end)
    kpis = {
        "total_screenings": {
            "value": len(current_screenings),
            "change_pct": _change(len(current_screenings), len(previous_screenings)),
        },
        "high_risk_rate": {
            "value_percent": current_risk,
            "change_points": round(current_risk - previous_risk, 2),
        },
        "average_processing_time": {
            "value_seconds": round(current_processing),
            "change_pct": _change(current_processing, previous_processing),
        },
        "ai_approval_rate": {
            "value_percent": current_approval,
            "change_points": round(current_approval - previous_approval, 2),
        },
    }

    daily_counts = {}
    for row in screenings:
        day = _day(row.created_at)
        daily_counts[day] = daily_counts.get(day, 0) + 1
    daily = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        average_start = day - timedelta(days=6)
        average = sum(daily_counts.get(average_start + timedelta(days=i), 0)
                      for i in range(7)) / 7
        daily.append({
            "date": day.isoformat(),
            "label": day.strftime("%d/%m"),
            "screenings": daily_counts.get(day, 0),
            "seven_day_average": round(average, 1),
        })

    distribution = []
    risk_counts = {key: 0 for key in RISK_ORDER}
    for row in current_screenings:
        risk_counts[classify_screening(row)] += 1
    for key in RISK_ORDER:
        distribution.append({
            "key": key, "label": RISK_LABELS[key], "count": risk_counts[key],
            "percentage": _pct(risk_counts[key], len(current_screenings), 1),
        })

    topic_counts = {topic: 0 for topic in TOPICS}
    for row in current_sessions:
        topic_counts[_topic(row)] += 1
    topic_total = sum(topic_counts.values())
    popular_topics = [{
        "topic": topic, "count": topic_counts[topic],
        "percentage": _pct(topic_counts[topic], topic_total, 1),
    } for topic in TOPICS]

    case_status = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        day_rows = [row for row in current_sessions if _day(row.created_at) == day]
        counts = {key: 0 for key in ("new", "in_progress", "pending", "completed", "closed")}
        for row in day_rows:
            counts[_session_bucket(row)] += 1
        total = len(day_rows)
        case_status.append({
            "date": day.isoformat(), "label": day.strftime("%d/%m"),
            **{key: _pct(value, total, 1) for key, value in counts.items()},
        })

    report = {
        "updated_at": (updated_at or datetime.now(timezone.utc)).isoformat(),
        "range": {"start_date": start.isoformat(), "end_date": end.isoformat(), "days": days},
        "kpis": kpis,
        "daily_screenings": daily,
        "risk_distribution": distribution,
        "popular_topics": popular_topics,
        "case_status": case_status,
        "monthly_summary": _monthly_summary(screenings, sessions, end),
    }
    report["insights"] = _insights(kpis)
    return report
