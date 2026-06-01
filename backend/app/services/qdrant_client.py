"""
Qdrant client wrapper — LOCAL FILE MODE.

Reads/writes the directory at settings.qdrant_local_path
(default `/app/models/cbt_rag_final` inside the container, mounted
from `./models/cbt_rag_final` on the host).

The actual Qdrant DB lives at models/cbt_rag_final/qdrant_storage/.
Full layout (from the notebook zip extraction):
  models/cbt_rag_final/qdrant_storage/.lock + meta.json
  models/cbt_rag_final/qdrant_storage/collection/{cbt_knowledge,cbt_examples}/
  models/cbt_rag_final/rag_outputs/bm25_rag1.pkl   ← BM25 for retrieval.py
  models/cbt_rag_final/rag_outputs/bm25_rag2.pkl   ← BM25 for retrieval.py

Three collections (per pipeline v4 retrieval layer):
  cbt_knowledge   — 2,824 pts (intents.json + CounselChat Q&A)
  cbt_examples    — 19,537 pts (MentalChat16K + Amod dialogues)
  session_memory  — per-user prior sessions — created on first boot

`ensure_collections()` NEVER overwrites an existing collection. It only
creates `session_memory` if missing, with bge-m3 dim (1024) cosine.

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
    """Lazy singleton — local file-mode client."""
    global _client
    if _client is None:
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

        wanted = {
            settings.qdrant_collection_kb,
            settings.qdrant_collection_dialogues,
            settings.qdrant_collection_memory,
        }
        for name in wanted:
            if name in existing:
                log.info("Qdrant collection present: %s (preserved)", name)
                continue
            log.info("Creating Qdrant collection %s (dim=%d, cosine)",
                     name, settings.embedding_dim)
            cli.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=settings.embedding_dim,
                                              distance=Distance.COSINE),
            )


def search(collection: str, query_vec: List[float], limit: int = 20,
           filter_dict: Optional[dict] = None):
    with _lock:
        return get_qdrant().search(
            collection_name=collection,
            query_vector=query_vec,
            limit=limit,
            query_filter=filter_dict,
            with_payload=True,
        )


def upsert(collection: str, points: List[PointStruct]) -> None:
    with _lock:
        get_qdrant().upsert(collection_name=collection, points=points)
