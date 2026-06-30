"""
LLM-backed rolling summaries — richer conversation context + durable memory.

Two outputs, both refreshed in a BACKGROUND task after a real L2/L3 turn so the
chat response is never delayed:

  (A) thread summary  → Redis (read into session_ctx["summary"] next turn)
  (B) user-memory gist → UserMemory.summary (replaces the heuristic one)

Best-effort by design: every LLM call goes through llm_client (PII-scrubbed),
and when the model is mock / unavailable / degraded the functions return None and
nothing is overwritten — so mock mode and offline hosts keep the heuristic
keyword memory. Any exception is swallowed; this must never break a turn.
"""
import logging

from app.core.config import settings
from app.core.crypto import decrypt_str
from app.db import models
from app.db.session import db_session
from app.services import llm_client, pii_scrubber, redis_client as rc, user_memory

log = logging.getLogger(__name__)

_THREAD_SYS = (
    "You summarise a CBT support conversation for the assistant's own working "
    "memory. In 1-2 plain sentences, state what the client is working on, the "
    "main feelings, and where the conversation is now. Be factual and neutral — "
    "no advice, no diagnosis, no names. If there is too little to summarise, "
    "reply with exactly: none.")

_USER_SYS = (
    "You write a short, durable note about a RETURNING client for a CBT "
    "assistant's memory. In 1-2 plain sentences, summarise their recurring "
    "concerns and anything that has helped, based only on the data given. "
    "Factual and neutral — no advice, no diagnosis, no names.")

_MAX = 600


def _gen(system: str, user: str):
    """One best-effort LLM completion → trimmed string, or None."""
    if not user.strip():
        return None
    try:
        gen = llm_client.generate(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}],
            n=1, temperature=0.2)
        # Skip degraded (circuit open / Modal error) AND pure mock mode — a mock
        # reply would store a garbage summary.
        if not gen or gen.get("degraded") or gen.get("mode") == "mock":
            return None
        out = (gen.get("responses") or [""])[0].strip()
        if not out or out.strip().lower().rstrip(".") == "none":
            return None
        return out[:_MAX]
    except Exception as e:
        log.warning("summarizer LLM call failed: %s", e)
        return None


def _history_text(rows) -> str:
    lines = []
    for s in rows:
        u = decrypt_str(s.user_input_enc) if s.user_input_enc else ""
        a = decrypt_str(s.final_reply_enc) if s.final_reply_enc else ""
        if u:
            lines.append("Client: " + u)
        if a:
            lines.append("Assistant: " + a)
    return pii_scrubber.scrub("\n".join(lines))[:2500]


def summarize_thread(rows) -> "str | None":
    if not rows:
        return None
    return _gen(_THREAD_SYS, _history_text(rows))


def summarize_user_memory(mem: dict, thread_summary: str = "") -> "str | None":
    if not mem or not mem.get("turn_count"):
        return None
    themes = ", ".join(mem.get("recurring_themes") or []) or "none"
    techs = ", ".join(mem.get("techniques_used") or []) or "none"
    body = (f"Turns so far: {mem.get('turn_count', 0)}\n"
            f"Recurring themes: {themes}\n"
            f"Techniques tried: {techs}")
    if thread_summary:
        body += f"\nMost recent session: {thread_summary}"
    return _gen(_USER_SYS, body)


def refresh_after_turn(user_id, conversation_id) -> None:
    """Background entrypoint — opens its OWN DB session (the request's is gone by
    now). Refreshes the thread summary (Redis) and the user-memory gist. No-op
    when memory_llm_summary is off or the LLM is unavailable."""
    if not getattr(settings, "memory_llm_summary", False):
        return
    try:
        with db_session() as db:
            rows = (db.query(models.Session)
                    .filter_by(conversation_id=conversation_id)
                    .order_by(models.Session.created_at.asc()).all())[-6:]
            ts = summarize_thread(rows)
            if ts:
                rc.thread_summary_set(
                    str(conversation_id), ts,
                    ttl=getattr(settings, "memory_thread_summary_ttl", 604800))
            mem = user_memory.load_for_prompt(db, user_id)
            us = summarize_user_memory(mem, ts or "")
            if us:
                user_memory.set_summary(db, user_id, us)
    except Exception as e:
        log.warning("refresh_after_turn failed (%s): %s", conversation_id, e)
