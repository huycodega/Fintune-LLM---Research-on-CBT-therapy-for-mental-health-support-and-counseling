#!/usr/bin/env bash
# ============================================================
# CBT Assistant v4 — end-to-end one-command boot
#   1. docker compose up (postgres/redis/minio/qdrant/backend/prom/grafana/cron)
#   2. wait for backend health
#   3. alembic upgrade head (idempotent)
#   4. seed Qdrant (idempotent — skip if user has data)
#   5. optional smoke test (--smoke)
#   6. start both frontends (npm run dev)
# ============================================================
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

SMOKE=0
SKIP_FRONTEND=0
for arg in "$@"; do
  case "$arg" in
    --smoke) SMOKE=1 ;;
    --no-frontend) SKIP_FRONTEND=1 ;;
    -h|--help)
      echo "Usage: ./run.sh [--smoke] [--no-frontend]"
      exit 0 ;;
  esac
done

if [ ! -f .env ]; then
  echo "▶ No .env found — copying from .env.example"
  cp .env.example .env
fi

echo "▶ docker compose up -d  (8 services)…"
docker compose up -d --build

echo "▶ Waiting for backend health (up to 60s)…"
for i in {1..30}; do
  if curl -sf --max-time 2 http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "  Backend ready."
    break
  fi
  sleep 2
done

echo "▶ Running Alembic migration (idempotent)…"
docker compose exec -T backend alembic upgrade head

echo "▶ Seeding Qdrant collections (idempotent, preserves user data)…"
docker compose exec -T backend python scripts/seed_qdrant.py || \
  echo "  (seed skipped — likely Qdrant volume already has data)"

if [ "$SMOKE" -eq 1 ]; then
  echo "▶ End-to-end smoke test…"
  docker compose exec -T backend python scripts/smoke_test.py
fi

if [ "$SKIP_FRONTEND" -eq 0 ]; then
  for APP in user_app admin_app; do
    if [ ! -d "$APP/node_modules" ]; then
      echo "▶ Installing $APP deps (first run)…"
      (cd "$APP" && npm install --no-audit --no-fund)
    fi
  done

  echo "▶ Starting user web on :5173…"
  (cd user_app && npm run dev > /tmp/cbt_user.log 2>&1) &
  USR=$!
  echo "▶ Starting admin web on :5174…"
  (cd admin_app && npm run dev > /tmp/cbt_admin.log 2>&1) &
  ADM=$!

  cleanup() {
    echo; echo "▶ Stopping frontends (Docker stack keeps running)…"
    kill $USR $ADM 2>/dev/null || true
    echo "  Run \`docker compose down\` to stop the backend stack."
  }
  trap cleanup EXIT
fi

cat <<EOF

  ┌─────────────────────────────────────────────────────┐
  │  PATIENT app  →  http://localhost:5173              │
  │      user / user123                                 │
  │                                                     │
  │  CLINICIAN app→  http://localhost:5174              │
  │      clinician / clinic123                          │
  │                                                     │
  │  API          →  http://localhost:8000/api/health   │
  │  Prom metrics →  http://localhost:8000/metrics      │
  │  Prometheus UI→  http://localhost:9090              │
  │  Grafana      →  http://localhost:3000              │
  │      admin / cbt_admin                              │
  │  MinIO UI     →  http://localhost:9001              │
  └─────────────────────────────────────────────────────┘

  Background: cbt_cron (DPO export every 24h)
  Logs: /tmp/cbt_user.log  /tmp/cbt_admin.log

  Useful next steps:
    • Run smoke test:   ./run.sh --smoke --no-frontend
    • Stop everything:  docker compose down
    • Deploy LLM:       see modal/README.md

EOF

if [ "$SKIP_FRONTEND" -eq 0 ]; then
  echo "  Ctrl-C stops the frontends."
  wait
fi
