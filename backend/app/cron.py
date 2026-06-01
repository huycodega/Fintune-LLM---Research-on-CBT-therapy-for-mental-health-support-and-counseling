"""
Cron worker — long-running process for scheduled background jobs.

Currently scheduled:

  1. DPO preference-pairs export  → MinIO   (default every 24h)
  2. Daily metrics summary log    → stdout  (every 24h)

Started by docker-compose as a separate `cron` service so it survives
backend restarts. Uses a simple in-process scheduler (no celery/beat
dependency — overkill for two jobs).
"""
import json
import logging
import os
import signal
import threading
import time
from datetime import datetime
from typing import Callable


log = logging.getLogger("cbt.cron")
logging.basicConfig(level=logging.INFO,
                     format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# ============================================================
# Job 1 — DPO preference-pairs export
# ============================================================
def job_dpo_export() -> dict:
    """Dump the preference_pairs view → MinIO cbt-training-data."""
    # Lazy import so this module loads without psycopg installed
    # (e.g. on a host running tests but not the full backend).
    from sqlalchemy import text as sa_text
    from app.core.crypto import decrypt_str
    from app.db.session import db_session
    from app.services import minio_client

    log.info("[dpo-export] start")
    rows = []
    with db_session() as db:
        rs = db.execute(sa_text(
            "SELECT feedback_id, user_input_hash, chosen_draft_id, "
            "chosen_enc, rejected_draft_id, rejected_enc FROM preference_pairs"
        )).fetchall()
        for r in rs:
            try:
                rows.append({
                    "feedback_id": str(r.feedback_id),
                    "user_input_hash": r.user_input_hash,
                    "chosen": (decrypt_str(r.chosen_enc)
                                if r.chosen_enc else ""),
                    "rejected": (decrypt_str(r.rejected_enc)
                                  if r.rejected_enc else ""),
                })
            except Exception as e:
                log.warning("[dpo-export] skip pair (%s)", e)

    if not rows:
        log.info("[dpo-export] no preference pairs available — skipped upload")
        return {"pairs": 0, "key": None}

    body = "\n".join(json.dumps(r) for r in rows).encode("utf-8")
    key = f"dpo-batches/{datetime.utcnow():%Y-%m-%d_%H%M%S}.jsonl"
    try:
        minio_client.put_bytes("cbt-training-data", key, body,
                                content_type="application/x-ndjson")
        log.info("[dpo-export] wrote %d pairs -> %s", len(rows), key)
        return {"pairs": len(rows), "key": key}
    except Exception as e:
        log.error("[dpo-export] MinIO upload failed: %s", e)
        return {"pairs": len(rows), "key": None, "error": str(e)}


# ============================================================
# Job 2 — daily metrics summary
# ============================================================
def job_daily_summary() -> dict:
    from sqlalchemy import text as sa_text
    from app.db.session import db_session
    with db_session() as db:
        total = db.execute(sa_text(
            "SELECT COUNT(*) FROM sessions")).scalar()
        last_24h = db.execute(sa_text(
            "SELECT COUNT(*) FROM sessions WHERE created_at > NOW() - "
            "INTERVAL '24 hours'")).scalar()
        l0 = db.execute(sa_text(
            "SELECT COUNT(*) FROM sessions WHERE triage_level='L0' "
            "AND created_at > NOW() - INTERVAL '24 hours'")).scalar()
        pending = db.execute(sa_text(
            "SELECT COUNT(*) FROM review_queue WHERE resolved_at IS NULL"
        )).scalar()
    log.info("[daily-summary] total_sessions=%s 24h=%s L0_24h=%s pending=%s",
             total, last_24h, l0, pending)
    return {"total_sessions": total, "sessions_24h": last_24h,
            "L0_24h": l0, "pending_review": pending}


# ============================================================
# Scheduler
# ============================================================
class Schedule:
    """Tiny scheduler: register (job, interval_seconds) tuples and run."""

    def __init__(self):
        self._jobs: list[tuple[Callable, float, float]] = []  # (job, every, next)
        self._stop = threading.Event()

    def every(self, seconds: float, job: Callable) -> None:
        self._jobs.append((job, seconds, time.monotonic() + 30))  # delay 30s on boot

    def run_forever(self) -> None:
        while not self._stop.is_set():
            now = time.monotonic()
            for i, (job, every, next_at) in enumerate(list(self._jobs)):
                if now >= next_at:
                    try:
                        job()
                    except Exception:
                        log.exception("Job %s failed", job.__name__)
                    self._jobs[i] = (job, every, now + every)
            self._stop.wait(timeout=5)

    def stop(self) -> None:
        self._stop.set()


def main():
    log.info("CBT cron worker starting")

    sched = Schedule()
    every_hours = float(os.environ.get("DPO_EXPORT_INTERVAL_HOURS", "24"))
    sched.every(every_hours * 3600.0, job_dpo_export)
    sched.every(24 * 3600.0, job_daily_summary)

    # Graceful shutdown
    def _handler(*_):
        log.info("Cron stopping")
        sched.stop()
    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)

    sched.run_forever()
    log.info("CBT cron worker stopped")


if __name__ == "__main__":
    main()
