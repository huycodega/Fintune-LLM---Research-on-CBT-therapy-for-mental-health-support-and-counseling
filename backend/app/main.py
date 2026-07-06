"""
FastAPI application entry.

On startup:
  1. Wait for Postgres + Redis + MinIO (Docker Compose healthchecks already
     gate this, but we double-check from app code for non-docker runs).
  2. Ensure Postgres schema (Alembic runs separately — `alembic upgrade head`).
  3. Bootstrap MinIO buckets.
  4. Ensure Qdrant collections exist (NEVER recreate the user's data).
  5. Seed users on first boot if missing.
"""
import logging
import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth_intake import router as auth_router
from app.api.chat import router as chat_router
from app.api.admin import router as admin_router
from app.api.admin_users import router as admin_users_router
from app.api.ai_moderation import router as ai_moderation_router
from app.api.admin_reports import router as admin_reports_router
from app.api.admin_logs import router as admin_logs_router
from app.api.admin_settings import router as admin_settings_router
from app.api.admin_cases import router as admin_cases_router
from app.api.admin_dashboard import router as admin_dashboard_router
from app.api.conversations import router as conversations_router
from app.api.me_profile import router as me_profile_router
from app.api.screening import router as screening_router
from app.api.content import router as content_router
from app.api.experts import router as experts_router
from app.core import auth as auth_core
from app.core.config import settings
from app.db import models
from app.db.session import db_session, engine
from app.services import (
    redis_client, minio_client, qdrant_client as qd, llm_client, safety_gate,
    calibration, metrics, agent_client,
)

log = logging.getLogger("cbt")
logging.basicConfig(level=logging.INFO,
                     format="%(asctime)s %(levelname)s %(name)s: %(message)s")


app = FastAPI(title="CBT Assistant v4 API", version="4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                    allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(admin_users_router)
app.include_router(ai_moderation_router)
app.include_router(admin_reports_router)
app.include_router(admin_logs_router)
app.include_router(admin_settings_router)
app.include_router(admin_cases_router)
app.include_router(admin_dashboard_router)
app.include_router(conversations_router)
app.include_router(me_profile_router)
app.include_router(screening_router)
app.include_router(content_router)
app.include_router(experts_router)


@app.on_event("startup")
def boot():
    log.info(
        "CBT v4 booting — MOCK_LLM=%s  responder=%s  safety_gate=%s  qdrant=%s",
        settings.mock_llm, settings.hf_model_repo,
        settings.safety_hf_model_repo, settings.qdrant_local_path)
    # Redis
    try:
        redis_client.bootstrap_redis()
        log.info("Redis OK")
    except Exception as e:
        log.warning("Redis boot failed: %s", e)
    # MinIO
    try:
        minio_client.bootstrap_minio()
        log.info("MinIO buckets OK")
    except Exception as e:
        log.warning("MinIO boot failed: %s", e)
    # Qdrant
    try:
        qd.ensure_collections()
        log.info("Qdrant collections OK")
    except Exception as e:
        log.warning("Qdrant boot failed: %s", e)
    # Calibration  (post-hoc temperature scaling from HF repo)
    try:
        calibration.load_calibration()
        log.info("Temperature calibration: %s", calibration.status())
    except Exception as e:
        log.warning("Calibration load failed: %s — using T=1.0", e)
    # Seed users (idempotent)
    try:
        with db_session() as s:
            for u in settings.seed_users:
                exists = s.query(models.User).filter_by(
                    username=u["username"]).first()
                if not exists:
                    s.add(models.User(
                        username=u["username"],
                        password_hash=auth_core.hash_password(u["password"]),
                        role=u["role"],
                        email_verified=True,   # seed accounts skip OTP
                    ))
            s.flush()
        log.info("Seed users ready")
    except Exception as e:
        log.warning("User seed skipped: %s — run `alembic upgrade head`?", e)
    # Mirror legacy clinician/admin accounts into the v2 RBAC principal table.
    try:
        from app.services.admin_principals import sync_admin_principals
        with db_session() as s:
            staff_count = sync_admin_principals(s)
        log.info("Admin RBAC principals ready: %s", staff_count)
    except Exception as e:
        log.warning("Admin RBAC sync skipped: %s", e)
    # Seed learning content (lessons + resources, idempotent)
    try:
        from app.db.seed_content import seed_content
        with db_session() as s:
            seed_content(s)
        log.info("Seed content ready")
    except Exception as e:
        log.warning("Content seed skipped: %s — run `alembic upgrade head`?", e)
    # Seed demo screenings (idempotent — only when the table is near-empty) so
    # the Screening page / Reports show real rows tied to existing users.
    try:
        from app.db.seed_demo import seed_demo_screenings
        with db_session() as s:
            n = seed_demo_screenings(s)
        log.info("Demo screenings seeded: %s", n)
    except Exception as e:
        log.warning("Demo screening seed skipped: %s", e)
    # Preload the NLI grounding model so the first chat doesn't pay the load
    # cost mid-request (which pushed long agent turns past the gateway timeout).
    try:
        from app.services import hallucination_nli
        hallucination_nli.preload()
        log.info("NLI grounding model preloaded")
    except Exception as e:
        log.warning("NLI preload skipped: %s", e)
    # In-app daily screening-plan sweep. The standalone cron worker isn't
    # deployed on every host (e.g. Railway runs only the web service), so a tiny
    # daemon thread pre-creates today's personalised plans once a day here too.
    if os.environ.get("SCREENING_INAPP_CRON", "1") == "1":
        import threading

        def _screening_sweep_loop():
            import time
            from app.db.session import db_session
            from app.services import screening_planner
            time.sleep(45)   # let boot/migrations settle
            while True:
                try:
                    with db_session() as s:
                        n = screening_planner.sweep(s)
                    log.info("Screening-plan sweep: %s plans", n)
                except Exception as e:                      # noqa: BLE001
                    log.warning("Screening sweep failed: %s", e)
                time.sleep(24 * 3600)

        threading.Thread(target=_screening_sweep_loop, daemon=True).start()
        log.info("In-app screening sweep scheduled (daily)")


@app.get("/api/health")
def health():
    return {
        "api": "ok",
        # which build is actually serving — Railway sets the SHA at build
        # time; live tests were mis-read twice because the new deploy hadn't
        # switched over yet and there was no way to tell.
        "build": os.getenv("RAILWAY_GIT_COMMIT_SHA", "local")[:7],
        "mock_llm": settings.mock_llm,
        "primary_responder": settings.hf_model_repo,        # cbt-qwen2.5-7b-v2
        "safety_gate": settings.safety_hf_model_repo,       # cbt-qwen2.5-7b-v2
        "qdrant_path": settings.qdrant_local_path,
        "llm": llm_client.health(),
        "safety": safety_gate.health(),
        "agent": agent_client.health(),
        "calibration": calibration.status(),
    }


@app.get("/metrics")
def prom_metrics():
    """Prometheus scrape endpoint."""
    return Response(content=metrics.render(),
                    media_type="text/plain; version=0.0.4; charset=utf-8")
