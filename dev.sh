#!/usr/bin/env bash
# Runs the API on :8000 and the web app on :3000. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")"

(cd backend && uv sync -q && uv run uvicorn app.main:app --reload --port 8000) &
(cd frontend && pnpm install --silent && pnpm dev --port 3000) &

trap 'kill 0' EXIT INT TERM
wait
