"""
MinIO/S3 client + bucket bootstrap.

Buckets (all created on first boot if missing):
  cbt-models           — LoRA + SafetyGate weights
  cbt-training-data    — DPO preference pairs, feedback snapshots
  cbt-soap-notes       — encrypted SOAP PDFs
  cbt-transcripts      — session transcripts (encrypted)
  cbt-audit-archive    — append-only audit dumps
"""
import io
import logging
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


log = logging.getLogger(__name__)

REQUIRED_BUCKETS = [
    "cbt-models",
    "cbt-training-data",
    "cbt-soap-notes",
    "cbt-transcripts",
    "cbt-audit-archive",
]

_client: Optional[Minio] = None


def get_minio() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def bootstrap_minio() -> None:
    """Create required buckets idempotently."""
    cli = get_minio()
    for b in REQUIRED_BUCKETS:
        try:
            if not cli.bucket_exists(b):
                cli.make_bucket(b)
                log.info("Created MinIO bucket: %s", b)
        except S3Error as e:
            log.warning("MinIO bucket %s: %s", b, e)


def put_bytes(bucket: str, key: str, data: bytes,
              content_type: str = "application/octet-stream") -> str:
    """Upload raw bytes; returns the object key."""
    cli = get_minio()
    cli.put_object(bucket, key, io.BytesIO(data), length=len(data),
                    content_type=content_type)
    return key


def get_bytes(bucket: str, key: str) -> bytes:
    """Download object bytes."""
    cli = get_minio()
    resp = cli.get_object(bucket, key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()
