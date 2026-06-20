"""
Dense embedder (bge-m3) + cross-encoder reranker (bge-reranker-v2-m3).

bge-m3 is 1024-dim, multilingual, max 8192 tokens. The user's existing
Qdrant collections (cbt_knowledge, cbt_examples) were built with bge-m3
so dim/space are guaranteed compatible at retrieval time.

Both models load lazily on first use to keep cold-start fast.
"""
import json
import logging
import urllib.request
from typing import Any, List, Tuple, Optional

from app.core.config import settings


log = logging.getLogger(__name__)
_device: Optional[str] = None
_embedder: Optional[Any] = None
_reranker: Optional[Any] = None


def _ml_runtime():
    """Load optional ML dependencies only when retrieval actually needs them."""
    try:
        import torch
        from sentence_transformers import SentenceTransformer, CrossEncoder
    except ImportError as e:
        raise RuntimeError(
            "ML retrieval dependencies are not installed. "
            "Use requirements.txt for full RAG, or run with MOCK_LLM=true "
            "to allow graceful no-context responses."
        ) from e
    return torch, SentenceTransformer, CrossEncoder


def _get_device() -> str:
    global _device
    if _device is None:
        torch, _, _ = _ml_runtime()
        _device = "cuda" if torch.cuda.is_available() else "cpu"
    return _device


def get_embedder():
    global _embedder
    if _embedder is None:
        _, SentenceTransformer, _ = _ml_runtime()
        device = _get_device()
        log.info("Loading embedder %s on %s",
                 settings.embedding_model, device)
        _embedder = SentenceTransformer(settings.embedding_model,
                                          device=device)
    return _embedder


def get_reranker():
    global _reranker
    if _reranker is None:
        _, _, CrossEncoder = _ml_runtime()
        device = _get_device()
        log.info("Loading reranker %s on %s",
                 settings.reranker_model, device)
        _reranker = CrossEncoder(settings.reranker_model, device=device,
                                   max_length=512)
    return _reranker


def _embed_modal(texts: List[str]) -> Optional[List[List[float]]]:
    """Fetch normalized embeddings from the Modal cbt-embedder service.
    Returns None on any failure so the caller can fall back to local encoding."""
    url = settings.modal_embedder_endpoint
    if not url:
        return None
    try:
        body = json.dumps({"texts": texts}).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=settings.modal_call_timeout) as r:
            data = json.loads(r.read().decode())
        vecs = data.get("vectors")
        if isinstance(vecs, list) and len(vecs) == len(texts):
            return [[float(x) for x in row] for row in vecs]
        log.warning("Modal embedder returned %d vectors for %d texts",
                    len(vecs or []), len(texts))
    except Exception as e:
        log.warning("Modal embedder call failed (%s) — local fallback", e)
    return None


def embed(texts: List[str]) -> List[List[float]]:
    """Returns dense vectors (list of 1024-float lists).

    When MODAL_EMBEDDER_ENDPOINT is set the vectors come from the Modal CPU
    service (keeps the 2.2 GB bge-m3 out of a low-RAM backend); otherwise the
    model is loaded and run in-process. Modal vectors are already L2-normalized,
    matching the local path."""
    if not texts:
        return []
    vecs = _embed_modal(texts)
    if vecs is not None:
        return vecs
    local = get_embedder().encode(texts, normalize_embeddings=True,
                                   convert_to_numpy=True)
    return local.tolist()


def embed_one(text: str) -> List[float]:
    return embed([text])[0]


def _sigmoid(x: float) -> float:
    import math
    # clamp to avoid overflow on large-magnitude logits
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _rerank_scores_modal(query: str, candidates: List[str]) -> Optional[List[float]]:
    """Fetch raw reranker logits from the Modal cbt-reranker service.
    Returns None on any failure so the caller can fall back to local rerank."""
    url = settings.modal_reranker_endpoint
    if not url:
        return None
    try:
        body = json.dumps({"query": query, "candidates": candidates}).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=settings.modal_call_timeout) as r:
            data = json.loads(r.read().decode())
        scores = data.get("scores")
        if isinstance(scores, list) and len(scores) == len(candidates):
            return [float(s) for s in scores]
        log.warning("Modal reranker returned %d scores for %d candidates",
                    len(scores or []), len(candidates))
    except Exception as e:
        log.warning("Modal reranker call failed (%s) — local fallback", e)
    return None


def rerank(query: str, candidates: List[str],
           top_k: Optional[int] = None,
           apply_sigmoid: bool = True) -> List[Tuple[int, float]]:
    """Returns [(original_index, score), ...] sorted descending by score.

    bge-reranker-v2-m3 outputs a raw relevance logit; with apply_sigmoid
    (default) we map it to a 0–1 probability so scores are comparable to the
    M3/M4 eval gate (rag_min_score=0.65).

    When MODAL_RERANKER_ENDPOINT is set the raw logits come from the Modal CPU
    service (keeps the heavy cross-encoder out of a low-RAM local container);
    otherwise the model is loaded and run in-process."""
    if not candidates:
        return []
    scores = _rerank_scores_modal(query, candidates)
    if scores is None:
        scores = [float(s) for s in get_reranker().predict(
            [(query, c) for c in candidates])]
    out = []
    for i, s in enumerate(scores):
        v = _sigmoid(s) if apply_sigmoid else s
        out.append((i, v))
    ranked = sorted(out, key=lambda x: -x[1])
    if top_k:
        ranked = ranked[:top_k]
    return ranked
