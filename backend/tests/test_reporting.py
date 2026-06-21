from datetime import date, datetime, timezone

import pytest

from app.services.reporting import (
    ScreeningFact, SessionFact, build_report, classify_screening, report_range,
)


def dt(day: int, hour: int = 12, month: int = 6):
    return datetime(2024, month, day, hour, tzinfo=timezone.utc)


@pytest.mark.parametrize("fact,expected", [
    (ScreeningFact(dt(7), "normal", "normal", [0] * 9), "low"),
    (ScreeningFact(dt(7), "moderate", "normal", [0] * 9), "medium"),
    (ScreeningFact(dt(7), "severe", "normal", [0] * 9), "high"),
    (ScreeningFact(dt(7), "normal", "normal", [0] * 8 + [1]), "emergency"),
])
def test_classify_screening(fact, expected):
    assert classify_screening(fact) == expected


def test_build_report_aggregates_kpis_charts_and_statuses():
    screenings = [
        ScreeningFact(dt(7), "normal", "normal", [0] * 9),
        ScreeningFact(dt(8), "moderate", "normal", [0] * 9),
        ScreeningFact(dt(9), "severe", "normal", [0] * 9),
        ScreeningFact(dt(10), "normal", "normal", [0] * 8 + [1]),
        ScreeningFact(dt(5), "normal", "normal", [0] * 9),
        ScreeningFact(dt(6), "normal", "normal", [0] * 9),
    ]
    sessions = [
        SessionFact(dt(7), dt(7, 12), "auto_sent", "L3",
                    {"emotion": "fear"}, resolution="approve", resolved_at=dt(7)),
        SessionFact(dt(8), status="pending_review", triage_level="L2",
                    analysis={"emotion": "sadness"}),
        SessionFact(dt(9), status="pending_review", triage_level="L2",
                    analysis={"topic": "academic"}, claimed=True),
        SessionFact(dt(10), status="crisis", triage_level="L0",
                    analysis={}),
        SessionFact(dt(11), dt(11, 12), "rejected", "L1",
                    {"topic": "relationship"}, resolution="reject", resolved_at=dt(11)),
        SessionFact(dt(6), dt(6, 13), "auto_sent", "L3",
                    {"emotion": "stress"}, resolution="approve", resolved_at=dt(6)),
    ]

    report = build_report(screenings, sessions, date(2024, 6, 7), date(2024, 6, 14),
                          updated_at=dt(14))

    assert report["range"]["days"] == 8
    assert report["kpis"]["total_screenings"] == {"value": 4, "change_pct": 100.0}
    assert report["kpis"]["high_risk_rate"]["value_percent"] == 50.0
    assert report["kpis"]["ai_approval_rate"]["value_percent"] == 50.0
    assert report["daily_screenings"][0]["screenings"] == 1
    assert [row["count"] for row in report["risk_distribution"]] == [1, 1, 1, 1]
    assert sum(row["percentage"] for row in report["risk_distribution"]) == 100.0
    assert report["popular_topics"][1]["topic"] == "Anxiety"
    assert report["popular_topics"][1]["count"] == 1

    by_date = {row["date"]: row for row in report["case_status"]}
    assert by_date["2024-06-08"]["new"] == 100.0
    assert by_date["2024-06-09"]["in_progress"] == 100.0
    assert by_date["2024-06-10"]["pending"] == 100.0
    assert by_date["2024-06-11"]["closed"] == 100.0
    assert len(report["monthly_summary"]) == 6
    assert len(report["insights"]) == 4


def test_processing_time_ignores_incomplete_and_negative_durations():
    sessions = [
        SessionFact(dt(7, 10), dt(7, 10), "answered"),
        SessionFact(dt(8), None, "pending_review"),
        SessionFact(dt(9, 12), dt(9, 11), "answered"),
    ]
    report = build_report([], sessions, date(2024, 6, 7), date(2024, 6, 14))
    assert report["kpis"]["average_processing_time"]["value_seconds"] == 0


def test_report_range_defaults_and_validation():
    start, end = report_range(None, date(2024, 6, 14))
    assert start == date(2024, 6, 7)
    assert end == date(2024, 6, 14)
    with pytest.raises(ValueError, match="start_date"):
        report_range(date(2024, 6, 15), date(2024, 6, 14))
