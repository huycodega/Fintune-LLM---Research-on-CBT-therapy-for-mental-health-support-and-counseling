"""
NLI-based hallucination grounding check.

Replaces the lexical-overlap baseline in post_process.grounding_score().
We use a small cross-encoder NLI model (cross-encoder/nli-deberta-v3-base)
that scores each (premise=retrieved_chunk, hypothesis=response_sentence)
pair on the 3-class NLI label space:

    contradiction / neutral / entailment

For each response sentence we take the MAX entailment probability across
all retrieved chunks (a sentence is grounded if ANY chunk supports it).
The overall grounding score is the MEAN of per-sentence entailment.

Why this model:
  - Small (~184M, runs CPU at ~50ms/pair); we batch all pairs.
  - Domain-agnostic (NLI training), so it generalizes to CBT content
    without needing fine-tuning on our retrieval corpus.
  - Cross-encoder beats bi-encoder for short-text NLI by ~5-8 F1.

If the model can't be loaded (offline / OOM / etc.), we fall back to
the lexical-overlap baseline so the pipeline stays alive.
"""
import logging
import re
import threading
from typing import List, Optional, Tuple

from app.core.config import settings


log = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()

# NLI label order varies across checkpoints. We auto-detect from id2label.
_NLI_MODEL_ID = "cross-encoder/nli-deberta-v3-base"


def _load() -> Optional[Tuple[object, int]]:
    """Lazy load. Returns (model, entail_idx) or None on failure."""
    global _model
    with _lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import CrossEncoder
            # The cross-encoder wrapper exposes raw logits via predict().
            m = CrossEncoder(_NLI_MODEL_ID, max_length=384)
            # Auto-detect which logit index is "entailment"
            try:
                id2label = m.model.config.id2label
                entail_idx = next(
                    i for i, label in id2label.items()
                    if str(label).lower().startswith("entail")
                )
            except (AttributeError, StopIteration):
                # cross-encoder/nli-deberta-v3-base order is
                # [contradiction, entailment, neutral] (HF docs);
                # default to index 1.
                entail_idx = 1
            _model = (m, entail_idx)
            log.info("NLI hallucination check loaded: %s (entail_idx=%d)",
                     _NLI_MODEL_ID, entail_idx)
            return _model
        except Exception as e:
            log.warning("NLI model unavailable (%s) — using lexical fallback",
                        e)
            _model = (None, -1)
            return _model


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _split_sentences(text: str) -> List[str]:
    """Cheap sentence splitter — adequate for CBT replies (1-5 sentences)."""
    text = (text or "").strip()
    if not text:
        return []
    sents = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    # filter ultra-short ("OK." etc) — they're not meaningful claims
    return [s for s in sents if len(s) >= 12]


def _softmax3(logits):
    import math
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps)
    return [e / s for e in exps]


def grounding_nli(response: str, retrieved: List[dict]) -> float:
    """
    Returns a grounding score in [0, 1]:
      mean over response-sentences of (max entailment-prob across chunks).
    """
    if not response or not retrieved:
        return 0.0

    loaded = _load()
    if loaded is None or loaded[0] is None:
        return _lexical_fallback(response, retrieved)
    model, entail_idx = loaded

    sentences = _split_sentences(response)
    if not sentences:
        return 0.0

    # Build all (premise, hypothesis) pairs at once for batched inference.
    chunks = [r.get("text", "")[:1500] for r in retrieved if r.get("text")]
    if not chunks:
        return 0.0

    pairs = [(chunk, sent) for sent in sentences for chunk in chunks]
    try:
        # CrossEncoder.predict returns shape (N, 3) for NLI heads.
        scores = model.predict(pairs, batch_size=8,
                                convert_to_numpy=True, show_progress_bar=False)
    except Exception as e:
        log.warning("NLI predict failed (%s) — lexical fallback", e)
        return _lexical_fallback(response, retrieved)

    # scores[i] = logits over 3 NLI classes for pair i.
    # We want entailment probability via softmax.
    n_chunks = len(chunks)
    per_sentence_max_entail = []
    for s_idx in range(len(sentences)):
        chunk_entails = []
        for c_idx in range(n_chunks):
            row = scores[s_idx * n_chunks + c_idx]
            probs = _softmax3(list(row))
            chunk_entails.append(probs[entail_idx])
        per_sentence_max_entail.append(max(chunk_entails))

    return round(sum(per_sentence_max_entail) / len(per_sentence_max_entail), 3)


# --------------------------------------------------------------
# Lexical fallback — same as the v4 baseline, used when NLI unavailable
# --------------------------------------------------------------
_WORD = re.compile(r"\b[a-zA-Z][a-zA-Z\-']{2,}\b")


def _lexical_fallback(response: str, retrieved: List[dict]) -> float:
    resp_tokens = {w.lower() for w in _WORD.findall(response)}
    if not resp_tokens:
        return 0.0
    ctx_tokens = set()
    for item in retrieved:
        ctx_tokens |= {w.lower() for w in _WORD.findall(item.get("text", ""))}
    return round(len(resp_tokens & ctx_tokens) / len(resp_tokens), 3)
