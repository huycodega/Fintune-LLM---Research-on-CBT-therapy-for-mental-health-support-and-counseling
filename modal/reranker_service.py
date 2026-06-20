"""
Modal Reranker service — BAAI/bge-reranker-v2-m3 cross-encoder.

Why this exists: the embedder (bge-m3) + reranker (bge-reranker-v2-m3) both ran
locally in the backend container. On a low-RAM host (≈3.7 GB to the container)
loading BOTH overflows memory and the reranker OOM-kills the worker. Moving the
reranker to a Modal CPU container keeps the embedder local (needed on every
query) while the heavier reranker runs in the cloud with plenty of RAM.

Runs on CPU (the cross-encoder is light — no GPU needed), so it's cheap.

Endpoint used by backend/app/services/embedder.py:
    POST /rerank  { query, candidates }  → { scores }   (raw logits, same order)
    GET  /health  → { status, model }

Deploy:
    modal deploy modal/reranker_service.py

After deploy, the backend derives the URL from MODAL_WORKSPACE automatically
(zilex-nikke--cbt-reranker-rerank.modal.run), or set MODAL_RERANKER_ENDPOINT.
"""
import os
import time

import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.1",
        "transformers==4.45.2",
        "sentence-transformers==3.1.1",
        "huggingface-hub==0.25.2",
        "fastapi==0.115.0",
        "pydantic==2.9.2",
    )
)

app = modal.App("cbt-reranker")

RERANKER_REPO = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# Shared cache volume so the reranker weights download once and are reused.
model_cache = modal.Volume.from_name("cbt-model-cache", create_if_missing=True)


@app.cls(
    image=image,
    cpu=2.0,
    memory=4096,            # 4 GB — plenty for the 2.27 GB cross-encoder
    scaledown_window=300,
    timeout=300,
    startup_timeout=900,
    volumes={"/root/.cache/huggingface": model_cache},
)
class CBTRerankerService:
    @modal.enter()
    def load(self):
        from sentence_transformers import CrossEncoder
        print(f"Loading reranker: {RERANKER_REPO} (cpu)")
        self.model = CrossEncoder(RERANKER_REPO, device="cpu", max_length=512)
        print("Reranker ready.")

    @modal.method()
    def rerank(self, query: str, candidates: list) -> dict:
        t0 = time.time()
        if not candidates:
            return {"scores": [], "latency_ms": 0}
        pairs = [(query, c) for c in candidates]
        scores = self.model.predict(pairs)          # raw logits
        return {
            "scores": [float(s) for s in scores],   # same order as candidates
            "latency_ms": round((time.time() - t0) * 1000),
            "model": RERANKER_REPO,
        }


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def rerank(body: dict):
    """POST /rerank — { query, candidates } → { scores } (raw logits)."""
    svc = CBTRerankerService()
    return svc.rerank.remote(
        query=body.get("query", ""),
        candidates=body.get("candidates", []),
    )


# NOTE: no /health endpoint — Modal free tier caps web functions at 8, and the
# backend only health-checks llm/safety/agent. Drop reranker health to free a
# slot for the embedder service.


@app.local_entrypoint()
def debug():
    svc = CBTRerankerService()
    out = svc.rerank.remote(
        query="exam anxiety",
        candidates=["I worry about failing my exam", "I love pizza"])
    print(out)
