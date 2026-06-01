"""
Session memory writer.

After a session reaches a terminal state (answered/auto_sent/rejected),
embed a compact summary and upsert it to Qdrant `session_memory` so
future sessions for the same user can retrieve their own history as
context (per pipeline v4 "Session memory" + "Session store update").
"""
import logging
from typing import Optional

from qdrant_client.http.models import PointStruct

from app.core.config import settings
from app.core.crypto import decrypt_str
from app.db import models
from app.services import embedder, qdrant_client as qd


log = logging.getLogger(__name__)


def _summarize(session: models.Session) -> str:
    """Plain-text per-session summary — cheap, no LLM call needed.
    Used both as embedding input AND as the human-readable payload.
    """
    user_input = decrypt_str(session.user_input_enc)
    final = decrypt_str(session.final_reply_enc) if session.final_reply_enc else ""
    parts = [
        f"User said: {user_input}",
        f"Triage: {session.triage_level} ({session.severity})",
        f"Technique used: {session.final_technique or '—'}",
    ]
    if final:
        parts.append(f"Reply: {final}")
    return "\n".join(parts)[:1500]


def write_session(session: models.Session) -> Optional[str]:
    """
    Embed + upsert. Returns the Qdrant point id (= session uuid string)
    on success, or None on failure (we never raise — this is best-effort
    background work).
    """
    if not session.final_technique:
        return None
    try:
        summary = _summarize(session)
        vec = embedder.embed_one(summary)
        point = PointStruct(
            id=str(session.id),
            vector=vec,
            payload={
                "user_id": str(session.user_id),
                "triage_level": session.triage_level,
                "severity": session.severity,
                "final_technique": session.final_technique,
                "created_at": session.created_at.isoformat(),
                "text": summary,
            },
        )
        qd.upsert(settings.qdrant_collection_memory, [point])
        log.info("Session memory written: session_id=%s", session.id)
        return str(session.id)
    except Exception as e:
        log.warning("Session memory write failed for %s: %s",
                    session.id, e)
        return None
