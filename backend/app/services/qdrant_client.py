"""
Qdrant client wrapper — LOCAL FILE MODE.

Reads/writes the directory at settings.qdrant_local_path
(default `/app/models/cbt_rag_final` inside the container, mounted
from `./models/cbt_rag_final` on the host).

The Qdrant DB lives at settings.qdrant_local_path (mount `data new/qdrant_local`).
Layout (built in rag-new.ipynb):
  qdrant_local/.lock + meta.json
  qdrant_local/collection/cbt_rag_bge_m3__cbt_knowledge_base/
  qdrant_local/collection/cbt_rag_bge_m3__response_template_base/
  qdrant_local/collection/cbt_rag_bge_m3__safety_policy_base/

Stores (per the v2 risk-aware retriever):
  cbt_rag_bge_m3__cbt_knowledge_base      — CBT concepts / techniques / psychoeducation
  cbt_rag_bge_m3__response_template_base  — response structures / communication templates
  cbt_rag_bge_m3__safety_policy_base      — crisis / safety / boundary policy
  session_memory                          — per-user prior sessions — created on first boot

`ensure_collections()` NEVER overwrites an existing collection. The three
RAG stores ship pre-built; it only creates `session_memory` if missing
(bge-m3 dim 1024, cosine).

LIMITATION: local mode is single-writer (file lock). The backend is the
only writer. The cron service must NOT touch Qdrant — it doesn't.
"""
import logging
import os
import threading
from typing import Optional, List

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from app.core.config import settings


log = logging.getLogger(__name__)
_client: Optional[QdrantClient] = None
# Serialize all access from FastAPI workers in this single process.
# Local mode uses a file lock too, but the in-process lock avoids
# unnecessary file-lock contention under load.
_lock = threading.RLock()


def get_qdrant() -> QdrantClient:
    """Lazy singleton. Qdrant Cloud (url + api_key) when QDRANT_URL is set,
    otherwise local file-mode at qdrant_local_path."""
    global _client
    if _client is None:
        if settings.qdrant_url:
            log.info("Qdrant remote mode at %s", settings.qdrant_url)
            _client = QdrantClient(url=settings.qdrant_url,
                                   api_key=settings.qdrant_api_key)
        else:
            path = settings.qdrant_local_path
            os.makedirs(path, exist_ok=True)
            log.info("Qdrant local mode at %s", path)
            _client = QdrantClient(path=path)
    return _client


def ensure_collections() -> None:
    """Idempotent — never overwrites an existing collection.
    Only creates session_memory (the auto-managed collection) if missing.
    """
    with _lock:
        cli = get_qdrant()
        existing = {c.name for c in cli.get_collections().collections}

        prefix = settings.rag_collection_prefix
        rag_stores = {
            f"{prefix}__cbt_knowledge_base",
            f"{prefix}__response_template_base",
            f"{prefix}__safety_policy_base",
        }
        # RAG stores are pre-built — warn (don't create) if any are missing,
        # so a misconfigured mount is loud rather than silently empty.
        for name in rag_stores:
            if name in existing:
                log.info("Qdrant RAG store present: %s (preserved)", name)
            else:
                log.warning("Qdrant RAG store MISSING: %s — check that "
                            "qdrant_local_path points at the v2 RAG data", name)

        # Only the app-managed memory collection is auto-created.
        mem = settings.qdrant_collection_memory
        if mem in existing:
            log.info("Qdrant collection present: %s (preserved)", mem)
        else:
            log.info("Creating Qdrant collection %s (dim=%d, cosine)",
                     mem, settings.embedding_dim)
            cli.create_collection(
                collection_name=mem,
                vectors_config=VectorParams(size=settings.embedding_dim,
                                              distance=Distance.COSINE),
            )


def search(collection: str, query_vec: List[float], limit: int = 20,
           filter_dict: Optional[dict] = None):
    """Vector search. Uses query_points() — the .search() method was REMOVED in
    qdrant-client 1.12+. Returns a list of ScoredPoint (.id/.score/.payload), so
    callers that iterate hits keep working unchanged."""
    with _lock:
        return get_qdrant().query_points(
            collection_name=collection,
            query=query_vec,
            limit=limit,
            query_filter=filter_dict,
            with_payload=True,
        ).points


def upsert(collection: str, points: List[PointStruct]) -> None:
    with _lock:
        get_qdrant().upsert(collection_name=collection, points=points)
