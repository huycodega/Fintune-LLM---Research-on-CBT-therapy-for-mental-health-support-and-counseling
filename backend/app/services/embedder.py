"""
Dense embedder (bge-m3) + cross-encoder reranker (bge-reranker-v2-m3).

bge-m3 is 1024-dim, multilingual, max 8192 tokens. The user's existing
Qdrant collections (cbt_knowledge, cbt_examples) were built with bge-m3
so dim/space are guaranteed compatible at retrieval time.

Both models load lazily on first use to keep cold-start fast.
"""
import logging
from typing import List, Tuple, Optional

import torch
from sentence_transformers import SentenceTransformer, CrossEncoder

from app.core.config import settings


log = logging.getLogger(__name__)
_device = "cuda" if torch.cuda.is_available() else "cpu"
_embedder: Optional[SentenceTransformer] = None
_reranker: Optional[CrossEncoder] = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        log.info("Loading embedder %s on %s",
                 settings.embedding_model, _device)
        _embedder = SentenceTransformer(settings.embedding_model,
                                          device=_device)
    return _embedder


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        log.info("Loading reranker %s on %s",
                 settings.reranker_model, _device)
        _reranker = CrossEncoder(settings.reranker_model, device=_device,
                                   max_length=512)
    return _reranker


def embed(texts: List[str]) -> List[List[float]]:
    """Returns dense vectors (list of 1024-float lists)."""
    if not texts:
        return []
    vecs = get_embedder().encode(texts, normalize_embeddings=True,
                                   convert_to_numpy=True)
    return vecs.tolist()


def embed_one(text: str) -> List[float]:
    return embed([text])[0]


def rerank(query: str, candidates: List[str],
           top_k: Optional[int] = None) -> List[Tuple[int, float]]:
    """Returns [(original_index, score), ...] sorted descending by score."""
    if not candidates:
        return []
    pairs = [(query, c) for c in candidates]
    scores = get_reranker().predict(pairs)
    ranked = sorted(enumerate(scores), key=lambda x: -x[1])
    if top_k:
        ranked = ranked[:top_k]
    return [(i, float(s)) for i, s in ranked]
