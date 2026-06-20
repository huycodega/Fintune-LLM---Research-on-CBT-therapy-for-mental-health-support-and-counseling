"""
Modal Embedder service — BAAI/bge-m3 dense embedder (1024-dim, multilingual).

Why this exists: the backend loaded bge-m3 (~2.2 GB) in-process, which OOMs any
free-tier / low-RAM host. Moving the embedder to a Modal CPU container keeps the
backend lightweight (just FastAPI + HTTP calls), so it fits a free Railway /
Render instance. Runs on CPU — bge-m3 inference is fine without a GPU.

Endpoint used by backend/app/services/embedder.py:
    POST /embed   { texts: [str, ...] }  → { vectors: [[float, ...], ...] }
    GET  /health  → { status, model, dim }

Vectors are L2-normalized (normalize_embeddings=True) so they match the vectors
the Qdrant collections were built with and are cosine-ready.

Deploy:
    modal deploy modal/embedder_service.py

After deploy the backend derives the URL from MODAL_WORKSPACE automatically
(<workspace>--cbt-embedder-embed.modal.run), or set MODAL_EMBEDDER_ENDPOINT.
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

app = modal.App("cbt-embedder")

EMBEDDER_REPO = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBED_DIM = 1024

# Shared cache volume so the weights download once and are reused (also shared
# with the reranker service — same bge family files).
model_cache = modal.Volume.from_name("cbt-model-cache", create_if_missing=True)


@app.cls(
    image=image,
    cpu=2.0,
    memory=4096,            # 4 GB — comfortable for the ~2.2 GB bge-m3
    scaledown_window=300,
    timeout=300,
    startup_timeout=900,
    volumes={"/root/.cache/huggingface": model_cache},
)
class CBTEmbedderService:
    @modal.enter()
    def load(self):
        from sentence_transformers import SentenceTransformer
        print(f"Loading embedder: {EMBEDDER_REPO} (cpu)")
        self.model = SentenceTransformer(EMBEDDER_REPO, device="cpu")
        print("Embedder ready.")

    @modal.method()
    def embed(self, texts: list) -> dict:
        t0 = time.time()
        if not texts:
            return {"vectors": [], "dim": EMBED_DIM, "latency_ms": 0}
        vecs = self.model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True)
        return {
            "vectors": [[float(x) for x in row] for row in vecs.tolist()],
            "dim": int(vecs.shape[1]),
            "latency_ms": round((time.time() - t0) * 1000),
            "model": EMBEDDER_REPO,
        }


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def embed(body: dict):
    """POST /embed — { texts: [...] } → { vectors: [[...], ...] } (normalized)."""
    svc = CBTEmbedderService()
    return svc.embed.remote(texts=body.get("texts", []))


# NOTE: no /health endpoint — Modal free tier caps web functions at 8, and the
# backend only health-checks llm/safety/agent. The embedder exposes just /embed.


@app.local_entrypoint()
def debug():
    svc = CBTEmbedderService()
    out = svc.embed.remote(texts=["I worry about failing my exam", "hello"])
    print({"dim": out["dim"], "n": len(out["vectors"]),
           "latency_ms": out["latency_ms"]})
