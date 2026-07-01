"""
Redis utilities: rate limiting, circuit breaker, session lock, triage cache.

All keys are short-TTL — Redis is the "hot working memory" of the stack.
Persistent state always lives in Postgres.
"""
import json
import time
import hashlib
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
# Rolling conversation summary (LLM-written, per thread)
# ============================================================
def thread_summary_get(conversation_id: str) -> Optional[str]:
    try:
        v = get_redis().get(f"thread:summary:{conversation_id}")
        if v is None:
            return None
        return v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
    except redis.RedisError:
        return None


def thread_summary_set(conversation_id: str, summary: str,
                       ttl: int = 604800) -> None:
    try:
        get_redis().setex(f"thread:summary:{conversation_id}", ttl, summary)
    except redis.RedisError:
        pass


# ============================================================
# Per-conversation style preferences ("be brief", "don't ask questions", …)
# ============================================================
def chat_prefs_get(conversation_id: str) -> list:
    try:
        v = get_redis().get(f"chat:prefs:{conversation_id}")
        return json.loads(v) if v else []
    except (redis.RedisError, json.JSONDecodeError):
        return []


def chat_prefs_set(conversation_id: str, prefs: list,
                   ttl: int = 604800) -> None:
    try:
        get_redis().setex(f"chat:prefs:{conversation_id}", ttl,
                          json.dumps(list(prefs)))
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
# OTP store (Gmail registration email verification)
# ============================================================
# Stored hashed (never the raw code) with a short TTL. A separate counter
# tracks failed attempts so we can lock out brute force. A cooldown key
# rate-limits resends.
def _otp_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def otp_set(email: str, code: str) -> None:
    r = get_redis()
    e = email.lower()
    r.setex(f"otp:code:{e}", settings.otp_ttl_seconds, _otp_hash(code))
    r.delete(f"otp:tries:{e}")
    r.setex(f"otp:cooldown:{e}", settings.otp_resend_cooldown_seconds, "1")


def otp_can_resend(email: str) -> bool:
    """False while still within the resend cooldown window."""
    try:
        return not get_redis().exists(f"otp:cooldown:{email.lower()}")
    except redis.RedisError:
        return True


def otp_verify(email: str, code: str) -> tuple[bool, str]:
    """Return (ok, reason). On success the code is consumed."""
    r = get_redis()
    e = email.lower()
    stored = r.get(f"otp:code:{e}")
    if not stored:
        return False, "expired"
    tries = r.incr(f"otp:tries:{e}")
    if tries == 1:
        r.expire(f"otp:tries:{e}", settings.otp_ttl_seconds)
    if tries > settings.otp_max_attempts:
        r.delete(f"otp:code:{e}")
        return False, "too_many_attempts"
    if _otp_hash(code) != stored:
        return False, "mismatch"
    r.delete(f"otp:code:{e}")
    r.delete(f"otp:tries:{e}")
    return True, "ok"


# ============================================================
# Bootstrap (called once on FastAPI startup)
# ============================================================
def bootstrap_redis() -> None:
    """Ping + clear stale half-open state on boot."""
    r = get_redis()
    r.ping()
    if r.get("circuit:modal:state") == "half-open":
        r.set("circuit:modal:state", "closed")
