"""
Centralized settings — read everything from environment variables so
the same image works in Docker Compose, on Modal, and on a bare host.
"""
import os
import base64
from typing import Optional
from pydantic import model_validator
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
    # Qdrant local path — v2 RAG built in rag-new.ipynb. Mount the directory
    # produced under `data new/qdrant_local` here. It holds the three
    # cbt_rag_bge_m3__* collections; session_memory is created on first boot.
    qdrant_local_path: str = "/app/data/qdrant_local"
    # Qdrant Cloud (managed) — when QDRANT_URL is set the client connects to the
    # hosted cluster (url + api_key) instead of the local file directory. Lets
    # the backend run on a stateless host (Railway/Render) with no local volume.
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None

    # ---- Modal workspace (single knob to switch deployment account) ----
    # Set MODAL_WORKSPACE (e.g. "zilex-nikke") and the six Modal endpoint URLs
    # below are derived automatically — no need to edit each one when you switch
    # Modal accounts. An explicitly-set MODAL_*_ENDPOINT still wins (override).
    # Modal deploy names are fixed: cbt-{llm,safety,agent} with functions
    # generate/assess/chat + health.
    modal_workspace: Optional[str] = None

    # ---- safety gate — Huysun29/cbt-qwen2.5-7b-v2 (QWen2.5-7B fine-tuned v2) ----
    # When MODAL_SAFETY_ENDPOINT is set, calls the Modal-hosted QWen model.
    # Falls back to local heuristic when endpoint is unset or unreachable.
    safety_hf_model_repo: str = "Huysun29/cbt-qwen2.5-7b-v2"
    safety_hf_base_model: str = "Qwen/Qwen2.5-7B-Instruct"
    modal_safety_endpoint: Optional[str] = None
    modal_safety_health_endpoint: Optional[str] = None
    # Legacy local .pt path kept for gradual migration
    safety_gate_path: str = "/app/models/safety_gate_multitask.pt"
    safety_gate_base: str = "mental/mental-roberta-base"

    # ---- primary CBT LLM — Huysun29/cbt-qwen2.5-7b-v2 (best model @ M4 eval) ----
    # v2 is a FULL MERGED model (Qwen2.5-7B + CBT SFT merged), NOT a LoRA
    # adapter — Modal loads it directly via AutoModelForCausalLM (llm_is_merged).
    mock_llm: bool = True
    modal_llm_endpoint: Optional[str] = None
    modal_health_endpoint: Optional[str] = None
    hf_model_repo: str = "Huysun29/cbt-qwen2.5-7b-v2"
    hf_base_model: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_is_merged: bool = True   # True → load full model; False → base + LoRA

    # ---- agent orchestrator — Huysun29/cbt-qwen2.5-7b-v2 (your fine-tuned model)
    # The orchestrator "brain" runs the ReAct loop: it decides which tools to
    # call (retrieve / analyze / recall memory / generate / clarify / escalate).
    # We run the SAME fine-tuned model for both orchestration and response, so
    # the whole system stays on your weights end-to-end (matches the M4 eval).
    # It ONLY operates in the L2/L3 zone — L0/L1 stay deterministic in chat.py.
    # When agent_enabled is False or modal_agent_endpoint is unset, the system
    # transparently falls back to the fixed pipeline (which still runs in mock).
    agent_enabled: bool = False
    modal_agent_endpoint: Optional[str] = None
    modal_agent_health_endpoint: Optional[str] = None
    agent_model_repo: str = "Huysun29/cbt-qwen2.5-7b-v2"
    agent_max_steps: int = 6
    agent_temperature: float = 0.3   # low: orchestrator should route, not riff

    # ---- reranker offload to Modal (optional) ----
    # bge-reranker-v2-m3 is ~2.3 GB; loading it locally alongside the embedder
    # OOMs a low-RAM container. When MODAL_RERANKER_ENDPOINT is set (or derived
    # from MODAL_WORKSPACE), embedder.rerank() calls the cbt-reranker Modal CPU
    # service instead of loading the model in-process. Unset → reranks locally.
    modal_reranker_endpoint: Optional[str] = None
    modal_reranker_health_endpoint: Optional[str] = None

    # ---- embedder offload to Modal (optional) ----
    # bge-m3 is ~2.2 GB; loading it in-process OOMs a free-tier / low-RAM host.
    # When MODAL_EMBEDDER_ENDPOINT is set (or derived from MODAL_WORKSPACE),
    # embedder.embed() calls the cbt-embedder Modal CPU service instead of
    # loading the model locally. Unset → embeds in-process.
    modal_embedder_endpoint: Optional[str] = None
    modal_embedder_health_endpoint: Optional[str] = None

    # ---- Modal call timeout (seconds) ----
    # A cold Modal container loading a 7B model can take 2-4 minutes. Keep this
    # generous so the FIRST request after a scale-to-zero waits for the model to
    # warm up instead of tripping the timeout and falling back to the heuristic /
    # fixed pipeline. Once warm, calls return in seconds. Override via env.
    modal_call_timeout: int = 600

    # ---- retrieval (v2 — risk-aware 3-store router, matches M3/M4 eval) ----
    # BAAI/bge-m3: 1024-dim multilingual. Reranker bge-reranker-v2-m3 (sigmoid).
    # Three role-tagged stores under one prefix; routing by predicted risk:
    #   cbt_rag_bge_m3__cbt_knowledge_base      (normal/moderate)
    #   cbt_rag_bge_m3__response_template_base  (all risks)
    #   cbt_rag_bge_m3__safety_policy_base      (all risks, k=3)
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rag_collection_prefix: str = "cbt_rag_bge_m3"
    qdrant_collection_memory: str = "session_memory"
    # retriever params (mirror cbt_rag_eval_pipeline defaults)
    rag_prefetch_k: int = 20           # dense candidates per store before rerank
    rag_final_top_k: int = 5           # chunks kept after rerank
    rag_safety_top_k: int = 3          # safety_policy_base is capped tighter
    rag_min_score: float = 0.65        # gate: inject context only if top-1 ≥ this
    rag_hit_tau: float = 0.5           # reranker threshold for hit@k proxy
    rag_ctx_char_budget: int = 3500    # total context chars injected
    rag_per_chunk_chars: int = 900     # per-chunk cap before budget
    # legacy retrieval knobs kept for callers that still pass them
    retrieval_top_k: int = 20
    retrieval_rerank_top_k: int = 5

    # ---- security ----
    jwt_secret: str = "change-me-in-prod-please"
    jwt_ttl_hours: int = 12
    phi_aes_key_b64: str = ""        # 32 raw bytes, base64

    # ---- Gmail self-registration + OTP email verification ----
    # Only @gmail.com addresses may self-register (student wellbeing scope).
    allowed_email_domains: list = ["gmail.com"]
    otp_length: int = 6
    otp_ttl_seconds: int = 600          # 10 min
    otp_resend_cooldown_seconds: int = 60
    otp_max_attempts: int = 5
    # SMTP — when smtp_host is empty the system runs in DEV mode: the OTP is
    # NOT emailed but logged to the server console (and returned by the API
    # only when otp_dev_echo is True) so local testing works without a mail
    # server. In production set SMTP_* and leave otp_dev_echo False.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "CBT Wellbeing <no-reply@cbt.local>"
    smtp_use_tls: bool = True
    otp_dev_echo: bool = True           # echo OTP in API response in DEV only

    # ---- generation ----
    n_responses: int = 3
    max_new_tokens: int = 400
    # 0.65: fine-tuned model already carries CBT style — lower T gives
    # more coherent clinical responses without losing natural empathy.
    temperature: float = 0.65
    top_p: float = 0.92

    # ---- rate limit ----
    rate_limit_per_minute: int = 30
    rate_limit_per_ip_per_minute: int = 60

    # ---- triage thresholds (when SafetyGate confidence vs heuristic) ----
    triage_crisis_threshold: float = 0.85
    triage_high_threshold: float = 0.65
    triage_mod_threshold: float = 0.40

    # ---- L3 auto-send anti-fabrication gate ----
    # A poorly-formed or rule-violating reply must never be auto-sent to a
    # client without a human. When the best L3 draft fails preflight (or, if a
    # grounding floor > 0 is set, scores below it against retrieved knowledge),
    # the turn is downgraded to clinician review instead of auto-sending.
    # The effect is always safe — it only routes MORE to humans, never less.
    autosend_require_preflight: bool = True
    autosend_grounding_floor: float = 0.0   # 0 = off (grounding-vs-KB is noisy)
    # Hard guarantee: when durable USER MEMORY is injected into the prompt, the
    # model can narrate it as a fabricated shared history ("our talks about…").
    # No automated check reliably catches that, so when memory is present an L3
    # reply is NOT auto-sent — it's held for a clinician. Trades more review for
    # certainty. New users (no memory yet) still get instant L3 replies.
    autosend_block_with_memory: bool = True
    # Require the draft's Technique to be a recognized CBT technique; a made-up
    # name (e.g. "Eight-step-reality-recheck") fails preflight → held for review.
    enforce_canonical_technique: bool = True

    # ---- safety context window ----
    # Feed the prior client turns of the thread to the safety model. Reading
    # each message in ISOLATION caused L1 over-triage with hallucinated reasons;
    # the A/B/C experiment (scripts/triage_context_experiment.py) showed context
    # + a "don't downgrade real intent" hint fixes the false positives AND still
    # escalates a regex-evading crisis to L0. The regex hard-override remains a
    # backstop. Toggle off here to revert to isolated-message triage.
    safety_use_context: bool = True
    safety_context_turns: int = 4

    # ---- triage decision log (foundation for the eval set) ----
    # One JSONL line per triage decision: raw model output, heuristic vs
    # model level, confidences, source, disagreement flag. NO raw PHI text —
    # only a sha256 hash — so the log is safe to keep and replay for tuning.
    triage_log_enabled: bool = True
    triage_log_path: str = "/app/data/triage_log.jsonl"
    # When the heuristic hard-overrides to L0/L1, STILL call the model (in
    # non-mock mode) to RECORD what it would have said. The override stands —
    # this only captures the regex's false-positive rate as data. Costs one
    # extra Modal call on L0/L1 turns; set False to disable.
    triage_shadow_model_on_override: bool = True

    # ---- seed accounts (created on first boot) ----
    seed_users: list = [
        {"username": "user", "password": "user123", "role": "user"},
        {"username": "clinician", "password": "clinic123", "role": "admin"},
    ]

    @model_validator(mode="after")
    def _normalize_db_url(self):
        """Railway/Render inject DATABASE_URL as 'postgresql://' (or Heroku-style
        'postgres://'), which SQLAlchemy maps to the psycopg2 driver. This app
        uses psycopg3, so rewrite the scheme to 'postgresql+psycopg://'."""
        url = self.database_url
        if url.startswith("postgresql+"):
            return self
        if url.startswith("postgresql://"):
            self.database_url = "postgresql+psycopg://" + url[len("postgresql://"):]
        elif url.startswith("postgres://"):
            self.database_url = "postgresql+psycopg://" + url[len("postgres://"):]
        return self

    @model_validator(mode="after")
    def _derive_modal_endpoints(self):
        """When MODAL_WORKSPACE is set, fill any Modal endpoint that wasn't given
        explicitly. Switching Modal accounts then only needs one env var.
        Deploy names are fixed by the modal/*_service.py apps."""
        ws = (self.modal_workspace or "").strip()
        if not ws:
            return self
        base = f"https://{ws}--"
        derived = {
            "modal_llm_endpoint":          f"{base}cbt-llm-generate.modal.run",
            "modal_health_endpoint":       f"{base}cbt-llm-health.modal.run",
            "modal_safety_endpoint":       f"{base}cbt-safety-assess.modal.run",
            "modal_safety_health_endpoint": f"{base}cbt-safety-health.modal.run",
            "modal_agent_endpoint":        f"{base}cbt-agent-chat.modal.run",
            "modal_agent_health_endpoint": f"{base}cbt-agent-health.modal.run",
            "modal_reranker_endpoint":     f"{base}cbt-reranker-rerank.modal.run",
            "modal_reranker_health_endpoint": f"{base}cbt-reranker-health.modal.run",
            "modal_embedder_endpoint":     f"{base}cbt-embedder-embed.modal.run",
            "modal_embedder_health_endpoint": f"{base}cbt-embedder-health.modal.run",
        }
        for field, url in derived.items():
            # derive only when not set (None or empty) so an explicit endpoint wins
            if not getattr(self, field):
                setattr(self, field, url)
        return self

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
