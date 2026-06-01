# `models/` — host-mounted assets

This folder is bind-mounted into the backend container at `/app/models/`.

```
models/
├── safety_gate_multitask.pt        ← optional; SafetyGate .pt
├── temperature_calibration.json    ← optional; falls back to HF download
├── qdrant_storage/                 ← required for your RAG data
│   ├── .lock
│   ├── meta.json
│   └── collection/
│       ├── cbt_knowledge/
│       │   └── storage.sqlite      ← 2,824 points, bge-m3, cosine
│       └── cbt_examples/
│           └── storage.sqlite      ← 19,537 points, bge-m3, cosine
└── README.md                       (this file)
```

## What goes where

### `safety_gate_multitask.pt` — optional
Your local SafetyGate (mental-roberta-base + 2 heads). If missing, the
backend falls back to a regex heuristic for triage. The fine-tuned `.pt`
gives noticeably better L0/L1/L2/L3 calibration on real conversations.

### `temperature_calibration.json` — optional
Post-hoc T-scaling JSON from your `Huysun29/cbt-gemma2-9b` HF repo.
- **Local present** → load from disk (offline-friendly)
- **Local missing** → auto-download from HF (needs `HF_TOKEN` in `.env`)
- **Neither** → T=1.0 (no calibration)

### `qdrant_storage/` — required (for your retrieval data)
The `qdrant-client` local-mode storage you shipped — keeps your two
collections **exactly as-is**, no re-indexing, no migration.

The backend reads this directly through `QdrantClient(path=...)` — there
is **no separate Qdrant container**. The folder must stay at exactly
this path; the backend writes session_memory upserts back to it during
runtime, which is why `docker-compose.yml` mounts `./models` as
**read-write** (not `:ro`).

## After you boot

Verify Qdrant sees your data:

```bash
docker compose exec backend python -c "
from qdrant_client import QdrantClient
c = QdrantClient(path='/app/models/qdrant_storage')
for col in c.get_collections().collections:
    info = c.get_collection(col.name)
    print(f'{col.name}: {info.points_count} points, '
          f'{info.config.params.vectors.size}-dim')
"
```

Expected output:
```
cbt_knowledge: 2824 points, 1024-dim
cbt_examples: 19537 points, 1024-dim
session_memory: 0 points, 1024-dim
```
