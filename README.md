# CBT Assistant v4

Hệ thống CBT clinician AI — kết hợp vai trò **trợ lý CBT** và **nhà trị liệu lâm sàng** trong một pipeline hoàn chỉnh.

```
┌─────────────────────────────────────────────────────────────────┐
│  user_app :5173 ──┐                        ┌── :5174 admin_app  │
└───────────────────┴──── /api ──► backend :8000 ─────────────────┘
                                        │
          ┌──────────┬──────────┬────────┴──────┬────────────────┐
          ▼          ▼          ▼               ▼                ▼
      postgres    redis      minio         cbt_rag_final      Modal
       :5432      :6379      :9000        (Qdrant local)    (LLM + Safety)
```

## Models

| Role | Model | Deploy |
|------|-------|--------|
| Primary CBT responder | `Huysun29/cbt-llama-3.1-8b` | Modal A10G |
| Safety / crisis gate | `Huysun29/cbt-qwen-7b` | Modal T4 |
| Embedder | `BAAI/bge-m3` | Local CPU |
| Reranker | `BAAI/bge-reranker-v2-m3` | Local CPU |

## Pipeline v4

```
Client message
      │
      ▼
[Safety Gate — cbt-qwen-7b]  →  L0/L1: crisis resources / clinician queue
      │
   L2/L3
      │
      ▼
[Hybrid RAG]  dense (bge-m3 + Qdrant) + sparse (BM25) → RRF → rerank
      │
      ▼
[Prompt Builder]  intake 6 sections + session ctx + analysis + retrieved
      │
      ▼
[Primary LLM — cbt-llama-3.1-8b]  →  3 drafts (Technique/Rationale/Plan/Response)
      │
      ▼
[Post-process]  parse + hallucination check + pre-flight
      │
   L2: clinician review queue (HITL)
   L3: auto-send + session memory write
```

---

## Yêu cầu

- Docker Desktop (Windows/Mac/Linux)
- Node.js 18+ (cho frontend)
- Git

---

## 1. Chuẩn bị models folder

Giải nén `cbt_rag_final.zip` (output của `rag-data-fixed.ipynb`) vào thư mục `models/`:

```
cbt_v4/
└── models/
    ├── safety_gate_multitask.pt          ← (optional, legacy fallback)
    └── cbt_rag_final/
        ├── qdrant_storage/               ← Qdrant DB (cbt_knowledge + cbt_examples)
        │   ├── .lock
        │   ├── meta.json
        │   └── collection/
        └── rag_outputs/
            ├── bm25_rag1.pkl             ← BM25 index cho cbt_knowledge
            ├── bm25_rag2.pkl             ← BM25 index cho cbt_examples
            ├── rag1_chunks.jsonl
            └── rag2_chunks.jsonl
```

---

## 2. Cấu hình môi trường

Tạo file `.env` cạnh `docker-compose.yml` (copy từ `.env.example` nếu có):

```bash
# Mock mode (mặc định = true, không cần GPU)
MOCK_LLM=true

# Khi deploy Modal xong, flip sang false và điền URLs:
# MOCK_LLM=false
# MODAL_LLM_ENDPOINT=https://<workspace>--cbt-llm-generate.modal.run
# MODAL_HEALTH_ENDPOINT=https://<workspace>--cbt-llm-health.modal.run
# MODAL_SAFETY_ENDPOINT=https://<workspace>--cbt-safety-assess.modal.run
# MODAL_SAFETY_HEALTH_ENDPOINT=https://<workspace>--cbt-safety-health.modal.run

# Security (tự generate nếu để trống)
# PHI_AES_KEY_B64=<base64 của 32 bytes ngẫu nhiên>
# JWT_SECRET=<random hex>
```

---

## 3. Khởi động (lần đầu)

```powershell
cd cbt_v4

# Build và start tất cả services
docker compose up -d --build

# Chờ ~10s cho postgres/redis/minio healthy, rồi chạy migration
docker compose exec backend alembic upgrade head
```

### Từ lần 2 trở đi

```powershell
docker compose up -d
```

---

## 4. Start frontend

Mở **2 terminal riêng**:

```powershell
# Terminal 1 — Patient app
cd cbt_v4\user_app
npm install      # chỉ cần lần đầu
npm run dev      # http://localhost:5173
```

```powershell
# Terminal 2 — Clinician app
cd cbt_v4\admin_app
npm install      # chỉ cần lần đầu
npm run dev      # http://localhost:5174
```

---

## 5. Truy cập

| Service | URL | Tài khoản |
|---------|-----|-----------|
| Patient app | http://localhost:5173 | `user / user123` |
| Clinician dashboard | http://localhost:5174 | `clinician / clinic123` |
| API health | http://localhost:8000/api/health | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | `admin / cbt_admin` |
| MinIO console | http://localhost:9001 | `cbt_minio / cbt_minio_dev_pw` |

---

## 6. Deploy LLM lên Modal (production)

```bash
pip install modal
modal token new
modal secret create hf-secret HF_TOKEN=hf_xxxxxxxxxx

# Deploy primary CBT LLM (Llama-3.1-8B + LoRA)
modal deploy modal/llm_service.py

# Deploy safety gate (QWen-7B + LoRA)
modal deploy modal/safety_service.py
```

Sau deploy Modal in ra 4 URLs → paste vào `.env` → `docker compose restart backend`.

Chi tiết xem [modal/README.md](modal/README.md).

---

## 7. Kiểm tra hệ thống

```powershell
# Health check API
curl http://localhost:8000/api/health

# Test safety gate
docker compose exec backend python -c "
from app.services import safety_gate
print(safety_gate.assess('I feel anxious about everything'))
print(safety_gate.assess('I want to end my life'))
"

# Test retrieval (BM25 + dense + RRF)
docker compose exec backend python -c "
from app.services import retrieval
results = retrieval.retrieve('I keep thinking everyone hates me', rerank_top_k=3)
for r in results:
    print(r['source_collection'], '|', r['text'][:100])
"

# Kiểm tra Qdrant collections
docker compose exec backend python -c "
from qdrant_client import QdrantClient
c = QdrantClient(path='/app/models/cbt_rag_final/qdrant_storage')
for col in c.get_collections().collections:
    info = c.get_collection(col.name)
    print(col.name, '->', info.points_count, 'points')
"

# Chạy unit tests
docker compose exec backend pytest -q tests/
```

---

## 8. Dừng hệ thống

```powershell
# Dừng containers (giữ data)
docker compose down

# Dừng và xóa toàn bộ data (reset hoàn toàn)
docker compose down -v
```

---

## 9. Cấu trúc project

```
cbt_v4/
├── backend/                  FastAPI backend
│   ├── app/
│   │   ├── api/              chat.py, admin.py, auth_intake.py
│   │   ├── core/             config, auth, crypto, audit
│   │   ├── db/               models, session, migrations
│   │   ├── services/
│   │   │   ├── safety_gate.py     ← cbt-qwen-7b (Modal) + heuristic fallback
│   │   │   ├── retrieval.py       ← BM25 + dense + RRF + rerank
│   │   │   ├── llm_client.py      ← cbt-llama-3.1-8b (Modal) + mock
│   │   │   ├── prompt_builder.py  ← CBT clinician system prompt
│   │   │   └── ...
│   └── requirements.txt
├── modal/
│   ├── llm_service.py        Llama-3.1-8B + LoRA (A10G)
│   ├── safety_service.py     QWen-7B + LoRA (T4)
│   └── README.md
├── user_app/                 Vite + React — Patient UI
├── admin_app/                Vite + React — Clinician dashboard
├── models/
│   └── cbt_rag_final/        Qdrant DB + BM25 pickles (từ rag-data-fixed.ipynb)
├── infra/
│   ├── prometheus/
│   └── grafana/
├── docker-compose.yml
└── rag-data-fixed.ipynb      Notebook build Qdrant + BM25 trên Kaggle
```

---

## 10. Pipeline v4 — mapping với code

| Pipeline stage | File |
|----------------|------|
| Consent + privacy gate | `api/auth_intake.py` |
| Rate limit + abuse detection | `services/redis_client.py` |
| PII scrubbing | `services/pii_scrubber.py` |
| PHI encryption | `core/crypto.py` |
| Intake form parser (6 sections) | `services/intake_parser.py` |
| Safety triage L0–L3 | `services/safety_gate.py` |
| Psychological analysis | `services/analyzer.py` |
| Hybrid retrieval (BM25 + dense + RRF) | `services/retrieval.py` |
| Prompt builder (CBT clinician) | `services/prompt_builder.py` |
| Pre-flight clinical check | `services/preflight.py` |
| LLM generation (3 drafts) | `services/llm_client.py` |
| Post-processing + hallucination check | `services/post_process.py` |
| Human-in-the-loop review | `api/admin.py` |
| SOAP note export | `services/soap_export.py` |
| Session memory (Qdrant) | `services/session_memory.py` |
| Feedback + DPO signal | `db/models.py` + `app/cron.py` |
| Observability | `services/metrics.py` + Grafana |
