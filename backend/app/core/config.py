"""
Centralized settings — read everything from environment variables so
the same image works in Docker Compose, on Modal, and on a bare host.
"""
import os
import base64
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- service endpoints ----
    database_url: str = "postgresql+psycopg://cbt:cbt_dev_pw@localhost:5432/cbt"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "cbt_minio"
    minio_secret_key: str = "cbt_minio_dev_pw"
    minio_secure: bool = False
    # Qdrant local path — the actual Qdrant DB lives one level deeper:
    # models/cbt_rag_final/qdrant_storage/ (extracted from the notebook zip)
    qdrant_local_path: str = "/app/models/cbt_rag_final/qdrant_storage"

    # ---- safety gate — Huysun29/cbt-qwen-7b (QWen2.5-7B + LoRA) ----
    # When MODAL_SAFETY_ENDPOINT is set, calls the Modal-hosted QWen model.
    # Falls back to local heuristic when endpoint is unset or unreachable.
    safety_hf_model_repo: str = "Huysun29/cbt-qwen-7b"
    safety_hf_base_model: str = "Qwen/Qwen2.5-7B-Instruct"
    modal_safety_endpoint: Optional[str] = None
    modal_safety_health_endpoint: Optional[str] = None
    # Legacy local .pt path kept for gradual migration
    safety_gate_path: str = "/app/models/safety_gate_multitask.pt"
    safety_gate_base: str = "mental/mental-roberta-base"

    # ---- primary CBT LLM — Huysun29/cbt-llama-3.1-8b (Llama-3.1-8B + LoRA) ----
    mock_llm: bool = True
    modal_llm_endpoint: Optional[str] = None
    modal_health_endpoint: Optional[str] = None
    hf_model_repo: str = "Huysun29/cbt-llama-3.1-8b"
    hf_base_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"

    # ---- retrieval ----
    # BAAI/bge-m3: 1024-dim multilingual, max 8192 tokens.
    # Collections match cbt_rag_final built in rag-data-fixed.ipynb.
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    qdrant_collection_kb: str = "cbt_knowledge"
    qdrant_collection_dialogues: str = "cbt_examples"
    qdrant_collection_memory: str = "session_memory"
    retrieval_top_k: int = 20
    retrieval_rerank_top_k: int = 5
    # BM25 hybrid indexes — produced by rag-data-fixed.ipynb, stored under
    # cbt_rag_final/rag_outputs/ after the zip is extracted into models/.
    bm25_rag1_path: str = "/app/models/cbt_rag_final/rag_outputs/bm25_rag1.pkl"
    bm25_rag2_path: str = "/app/models/cbt_rag_final/rag_outputs/bm25_rag2.pkl"
    bm25_rrf_k: int = 60  # RRF constant — higher = smoother rank weighting

    # ---- security ----
    jwt_secret: str = "change-me-in-prod-please"
    jwt_ttl_hours: int = 12
    phi_aes_key_b64: str = ""        # 32 raw bytes, base64

    # ---- generation ----
    n_responses: int = 3
    max_new_tokens: int = 400
    temperature: float = 0.8
    top_p: float = 0.9

    # ---- rate limit ----
    rate_limit_per_minute: int = 30
    rate_limit_per_ip_per_minute: int = 60

    # ---- triage thresholds (when SafetyGate confidence vs heuristic) ----
    triage_crisis_threshold: float = 0.85
    triage_high_threshold: float = 0.65
    triage_mod_threshold: float = 0.40

    # ---- seed accounts (created on first boot) ----
    seed_users: list = [
        {"username": "user", "password": "user123", "role": "user"},
        {"username": "clinician", "password": "clinic123", "role": "admin"},
    ]

    def phi_key(self) -> bytes:
        """32-byte AES key. Auto-generate on first boot if env empty so
        a fresh checkout boots; in real prod set PHI_AES_KEY_B64 explicitly."""
        if not self.phi_aes_key_b64:
            self.phi_aes_key_b64 = base64.b64encode(os.urandom(32)).decode()
        key = base64.b64decode(self.phi_aes_key_b64)
        if len(key) != 32:
            raise RuntimeError("PHI_AES_KEY_B64 must decode to 32 bytes")
        return key


settings = Settings()
