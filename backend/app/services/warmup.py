"""
Best-effort Modal warm-up.

Opening the Chat page fires POST /api/warmup, which pokes every configured
Modal service with the smallest valid request, so the GPU containers cold-start
WHILE the user is still typing their first message instead of when they hit
send. A Redis lock collapses stampedes (one warm-up per window cluster-wide),
and everything is fire-and-forget: a warm-up failure can never break chat.
"""
import json
import logging
import threading
import urllib.request

from app.core.config import settings
from app.services import redis_client as rc

log = logging.getLogger("cbt.warmup")

_LOCK_KEY = "warmup:lock"
_LOCK_TTL = 240          # one cluster-wide warm-up per 4 min (< scaledown 5 min)
_PING_TIMEOUT = 600      # cold start can take minutes; the thread just waits


def _targets():
    """(name, url, tiny-valid-body) per configured service. Bodies must parse
    far enough to reach `.remote()`, or the GPU class never boots."""
    ping = [{"role": "user", "content": "hi"}]
    return [
        ("llm", settings.modal_llm_endpoint,
         {"messages": ping, "n_responses": 1, "max_new_tokens": 1}),
        ("safety", settings.modal_safety_endpoint,
         {"messages": ping, "max_new_tokens": 1}),
        ("agent", settings.modal_agent_endpoint,
         {"messages": ping, "tools": [], "max_new_tokens": 1}),
        ("embedder", settings.modal_embedder_endpoint, {"texts": ["hi"]}),
        ("reranker", settings.modal_reranker_endpoint,
         {"query": "hi", "candidates": ["hi"]}),
    ]


def _ping(name: str, url: str, body: dict) -> None:
    try:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=_PING_TIMEOUT):
            pass
        log.info("warmup: %s awake", name)
    except Exception as e:  # noqa: BLE001 — warm-up is strictly best-effort
        log.info("warmup: %s ping failed (%s)", name, e)


def fire() -> bool:
    """Kick one warm-up round in daemon threads. Returns False when another
    round already ran within the lock window (or Redis says no)."""
    try:
        if not rc.get_redis().set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL):
            return False
    except Exception:
        pass  # Redis down → still warm up; worst case is a duplicate ping
    started = False
    for name, url, body in _targets():
        if not url:
            continue
        threading.Thread(target=_ping, args=(name, url, body),
                         daemon=True, name=f"warmup-{name}").start()
        started = True
    return started
