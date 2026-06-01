"""
Retrieval orchestrator — hybrid dense + BM25 sparse with RRF fusion.

Pipeline (per rag-data-fixed.ipynb):
  1. Dense search   — BAAI/bge-m3 embeddings in Qdrant (both collections)
  2. Sparse search  — BM25Okapi loaded from cbt_rag_final/rag_outputs/*.pkl
  3. RRF fusion     — score = Σ 1/(RRF_K + rank) across dense + sparse hits
  4. Cross-encoder reranking — BAAI/bge-reranker-v2-m3 on top-N fused results

Collections:
  cbt_knowledge   — 2,824 pts: intents.json + CounselChat Q&A
  cbt_examples    — 19,537 pts: MentalChat16K + Amod conversation examples
  session_memory  — per-user prior sessions (app-managed)

BM25 indexes are pickled as:
  {bm25: BM25Okapi, chunks: [{"id":..., "text":..., "source":...}, ...]}
and live at settings.bm25_rag1_path / settings.bm25_rag2_path.

Graceful degradation:
  - Missing BM25 files → dense-only (logged warning)
  - Qdrant collection missing → collection skipped (logged warning)
  - Reranker unavailable → RRF-scored order used directly
"""
import logging
import os
import pickle
import re
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.core.config import settings
from app.services import qdrant_client as qd
from app.services import embedder


log = logging.getLogger(__name__)

_TEXT_PAYLOAD_KEYS = ("text", "content", "chunk", "body", "passage")

# ─────────────────────────────────────────────────────────────────────────────
# BM25 lazy loader
# ─────────────────────────────────────────────────────────────────────────────
_bm25_rag1 = None
_bm25_rag1_chunks: List[Dict] = []
_bm25_rag2 = None
_bm25_rag2_chunks: List[Dict] = []
_bm25_loaded = False


def _tokenize(text: str) -> List[str]:
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return [t for t in text.split() if len(t) > 2]


def _load_bm25() -> None:
    global _bm25_rag1, _bm25_rag1_chunks, _bm25_rag2, _bm25_rag2_chunks, _bm25_loaded
    if _bm25_loaded:
        return
    _bm25_loaded = True

    for attr_bm25, attr_chunks, path, label in [
        ("_bm25_rag1", "_bm25_rag1_chunks", settings.bm25_rag1_path, "RAG1"),
        ("_bm25_rag2", "_bm25_rag2_chunks", settings.bm25_rag2_path, "RAG2"),
    ]:
        if not os.path.exists(path):
            log.warning("BM25 pickle not found at %s (%s) — dense-only fallback",
                        path, label)
            continue
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            globals()[attr_bm25] = data["bm25"]
            globals()[attr_chunks] = data["chunks"]
            log.info("BM25 %s loaded: %d docs from %s", label,
                     len(data["chunks"]), path)
        except Exception as e:
            log.warning("BM25 %s load failed (%s) — dense-only fallback", label, e)


# ─────────────────────────────────────────────────────────────────────────────
# Per-collection search helpers
# ─────────────────────────────────────────────────────────────────────────────
def _extract_text(payload: Dict) -> str:
    for k in _TEXT_PAYLOAD_KEYS:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return str(payload)[:500]


def _dense_hits(query: str, collection: str, limit: int) -> List[Dict]:
    q_vec = embedder.embed_one(query)
    try:
        hits = qd.search(collection, q_vec, limit=limit)
    except Exception as e:
        log.warning("Qdrant search failed on %s: %s", collection, e)
        return []
    return [
        {"id": str(h.id), "score": float(h.score),
         "payload": dict(h.payload or {})}
        for h in hits
    ]


def _bm25_hits(query: str, bm25_obj, chunks: List[Dict],
               limit: int) -> List[Dict]:
    if bm25_obj is None or not chunks:
        return []
    tokens = _tokenize(query)
    scores = bm25_obj.get_scores(tokens)
    top_idx = np.argsort(scores)[::-1][:limit]
    return [
        {"id": chunks[i].get("id", f"bm25_{i}"),
         "score": float(scores[i]),
         "payload": chunks[i]}
        for i in top_idx
        if scores[i] > 0
    ]


# ─────────────────────────────────────────────────────────────────────────────
# RRF fusion
# ─────────────────────────────────────────────────────────────────────────────
def _rrf_fuse(dense: List[Dict], sparse: List[Dict],
              k: int) -> List[Dict]:
    """
    Pure Reciprocal Rank Fusion.  score(d) = Σ 1 / (k + rank(d, list))
    Scale-invariant: works regardless of whether dense scores are cosine
    similarities (0–1) or BM25 raw counts.
    """
    combined: Dict[str, Dict] = {}

    for rank, h in enumerate(dense):
        cid = h["id"]
        combined[cid] = {
            "rrf_score": 1.0 / (k + rank),
            "payload": h["payload"],
            "id": cid,
        }

    for rank, h in enumerate(sparse):
        cid = h["id"]
        payload = h["payload"]
        if cid in combined:
            combined[cid]["rrf_score"] += 1.0 / (k + rank)
        else:
            combined[cid] = {
                "rrf_score": 1.0 / (k + rank),
                "payload": {
                    "id": cid,
                    "text": payload.get("text", ""),
                    "source": payload.get("source", ""),
                    "client_text": payload.get("client_text", ""),
                    "counselor_text": payload.get("counselor_text", ""),
                },
                "id": cid,
            }

    return sorted(combined.values(), key=lambda x: x["rrf_score"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# Public retrieval API
# ─────────────────────────────────────────────────────────────────────────────
def retrieve(query: str,
             top_k_per_collection: int = 10,
             rerank_top_k: int = 5) -> List[Dict]:
    """
    Returns:
      [
        {
          "id": str,
          "score_dense": float,
          "score_rerank": float,
          "text": str,
          "source_collection": "cbt_knowledge" | "cbt_examples",
          "payload": {...full payload...}
        },
        ...
      ]

    Method:
      For each collection: dense_search(top_k*3) + bm25_search(top_k*3)
      → RRF fuse → take top_k per collection
      → pool both collections → cross-encoder rerank → rerank_top_k
    """
    _load_bm25()

    fetch_k = top_k_per_collection * 3   # wider net for RRF / reranker
    rrf_k = settings.bm25_rrf_k

    pool: List[Dict] = []

    # ── cbt_knowledge ──────────────────────────────────────────────────────
    dense_kb = _dense_hits(query, settings.qdrant_collection_kb, fetch_k)
    sparse_kb = _bm25_hits(query, _bm25_rag1, _bm25_rag1_chunks, fetch_k)
    fused_kb = _rrf_fuse(dense_kb, sparse_kb, rrf_k)

    for item in fused_kb[:top_k_per_collection]:
        pool.append({
            "id": item["id"],
            "score_dense": item["rrf_score"],
            "text": _extract_text(item["payload"]),
            "source_collection": settings.qdrant_collection_kb,
            "payload": item["payload"],
        })

    # ── cbt_examples ───────────────────────────────────────────────────────
    dense_ex = _dense_hits(query, settings.qdrant_collection_dialogues, fetch_k)
    sparse_ex = _bm25_hits(query, _bm25_rag2, _bm25_rag2_chunks, fetch_k)
    fused_ex = _rrf_fuse(dense_ex, sparse_ex, rrf_k)

    for item in fused_ex[:top_k_per_collection]:
        payload = item["payload"]
        # For dialogue examples prefer the richer combined text
        text = (payload.get("text") or
                _build_dialogue_text(payload) or
                _extract_text(payload))
        pool.append({
            "id": item["id"],
            "score_dense": item["rrf_score"],
            "text": text,
            "source_collection": settings.qdrant_collection_dialogues,
            "payload": payload,
        })

    if not pool:
        return []

    # ── cross-encoder rerank ────────────────────────────────────────────────
    cands = [p["text"] for p in pool]
    try:
        ranked: List[Tuple[int, float]] = embedder.rerank(query, cands,
                                                           top_k=rerank_top_k)
        out = []
        for orig_idx, score in ranked:
            item = pool[orig_idx]
            item["score_rerank"] = score
            out.append(item)
        return out
    except Exception as e:
        log.warning("Reranker failed (%s) — returning RRF order", e)
        # Fallback: return pool sorted by RRF score, no rerank score
        for item in pool:
            item["score_rerank"] = item["score_dense"]
        return pool[:rerank_top_k]


def _build_dialogue_text(payload: Dict) -> str:
    """Format a dialogue-collection payload as 'Client: ...\nCounselor: ...'."""
    client = payload.get("client_text", "")
    counselor = payload.get("counselor_text", "")
    if client and counselor:
        return f"Client: {client}\nCounselor: {counselor}"
    return ""
