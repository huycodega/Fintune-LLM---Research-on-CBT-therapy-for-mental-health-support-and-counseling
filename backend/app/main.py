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
from app.core import auth as auth_core
from app.core.config import settings
from app.db import models
from app.db.session import db_session, engine
from app.services import (
    redis_client, minio_client, qdrant_client as qd, llm_client, safety_gate,
    calibration, metrics,
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
                    ))
            s.flush()
        log.info("Seed users ready")
    except Exception as e:
        log.warning("User seed skipped: %s — run `alembic upgrade head`?", e)


@app.get("/api/health")
def health():
    return {
        "api": "ok",
        "mock_llm": settings.mock_llm,
        "primary_responder": settings.hf_model_repo,        # cbt-llama-3.1-8b
        "safety_gate": settings.safety_hf_model_repo,       # cbt-qwen-7b
        "qdrant_path": settings.qdrant_local_path,
        "llm": llm_client.health(),
        "safety": safety_gate.health(),
        "calibration": calibration.status(),
    }


@app.get("/metrics")
def prom_metrics():
    """Prometheus scrape endpoint."""
    return Response(content=metrics.render(),
                    media_type="text/plain; version=0.0.4; charset=utf-8")
