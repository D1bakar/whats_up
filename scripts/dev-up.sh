#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

docker compose -f docker/docker-compose.dev.yml up -d postgres redis

echo "Waiting for infrastructure..."
sleep 3

cd backend
uv sync --extra dev
uv run alembic upgrade head

echo "Foundation services are up."
echo "  API:      uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo "  Frontend: cd frontend && npm install && npm run dev"
