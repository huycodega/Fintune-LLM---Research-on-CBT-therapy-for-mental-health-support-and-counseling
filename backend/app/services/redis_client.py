"""
Redis utilities: rate limiting, circuit breaker, session lock, triage cache.

All keys are short-TTL — Redis is the "hot working memory" of the stack.
Persistent state always lives in Postgres.
"""
import json
import time
from typing import Optional

import redis
from fastapi import HTTPException

from app.core.config import settings


# Global client — Redis client is thread-safe.
_r: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _r
    if _r is None:
        _r = redis.Redis.from_url(settings.redis_url,
                                    decode_responses=True,
                                    socket_timeout=2)
    return _r


# ============================================================
# Rate limit (sliding-window per minute)
# ============================================================
def rate_limit_check(user_id: str, ip: str) -> None:
    """Raise 429 if user or IP exceeds limit. Otherwise increment."""
    r = get_redis()
    minute = int(time.time() // 60)
    keys = [
        (f"rate:{user_id}:{minute}", settings.rate_limit_per_minute),
        (f"rate:ip:{ip}:{minute}", settings.rate_limit_per_ip_per_minute),
    ]
    for key, limit in keys:
        try:
            n = r.incr(key)
            if n == 1:
                r.expire(key, 70)   # slightly > 60s for safety
            if n > limit:
                raise HTTPException(
                    429, f"Rate limit exceeded ({n}/{limit} per minute)")
        except redis.RedisError:
            return                   # fail-open: never block on Redis outage


# ============================================================
# Triage cache (skip safety-gate on identical recent input)
# ============================================================
def triage_cache_get(input_hash: str) -> Optional[dict]:
    try:
        v = get_redis().get(f"triage:cache:{input_hash}")
        return json.loads(v) if v else None
    except (redis.RedisError, json.JSONDecodeError):
        return None


def triage_cache_set(input_hash: str, result: dict, ttl: int = 300) -> None:
    try:
        get_redis().setex(f"triage:cache:{input_hash}", ttl,
                            json.dumps(result))
    except redis.RedisError:
        pass


# ============================================================
# Session lock (prevent two clinicians grabbing the same case)
# ============================================================
def acquire_review_lock(session_id: str, clinician_id: str) -> bool:
    """SET NX with 30s TTL. Return True if we got the lock."""
    try:
        return bool(get_redis().set(
            f"session:lock:{session_id}", clinician_id,
            nx=True, ex=30))
    except redis.RedisError:
        return True                  # fail-open


def release_review_lock(session_id: str) -> None:
    try:
        get_redis().delete(f"session:lock:{session_id}")
    except redis.RedisError:
        pass


# ============================================================
# Circuit breaker (for Modal LLM endpoint)
# ============================================================
_BREAKER_OPEN_SECONDS = 60
_BREAKER_FAIL_THRESHOLD = 5


def circuit_should_call() -> bool:
    """Closed/half-open -> True, fully open -> False."""
    try:
        r = get_redis()
        state = r.get("circuit:modal:state") or "closed"
        if state == "open":
            opened_at = float(r.get("circuit:modal:opened_at") or 0)
            if time.time() - opened_at > _BREAKER_OPEN_SECONDS:
                r.set("circuit:modal:state", "half-open")
                return True
            return False
        return True
    except redis.RedisError:
        return True


def circuit_record_success() -> None:
    try:
        r = get_redis()
        r.set("circuit:modal:state", "closed")
        r.delete("circuit:modal:failures")
    except redis.RedisError:
        pass


def circuit_record_failure() -> None:
    try:
        r = get_redis()
        n = r.incr("circuit:modal:failures")
        r.expire("circuit:modal:failures", 120)
        if n >= _BREAKER_FAIL_THRESHOLD:
            r.set("circuit:modal:state", "open")
            r.set("circuit:modal:opened_at", time.time())
    except redis.RedisError:
        pass


# ============================================================
# Bootstrap (called once on FastAPI startup)
# ============================================================
def bootstrap_redis() -> None:
    """Ping + clear stale half-open state on boot."""
    r = get_redis()
    r.ping()
    if r.get("circuit:modal:state") == "half-open":
        r.set("circuit:modal:state", "closed")
