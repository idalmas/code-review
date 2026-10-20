#!/usr/bin/env bash
# Runs Cypher locally: API on :8000, web app on :3000. Ctrl+C stops everything.
#
#   ./dev.sh        against real GitHub, using backend/.env (see AGENTS.md)
#   ./dev.sh demo   against a built-in fake GitHub + LLM with sample PRs; no accounts needed
set -euo pipefail
cd "$(dirname "$0")"

trap 'kill 0' EXIT INT TERM

if [ "${1:-}" = "demo" ]; then
  python3 demo/server.py &
  export GITHUB_API_URL=http://127.0.0.1:9999 GITHUB_WEB_URL=http://127.0.0.1:9999
  export GITHUB_CLIENT_ID=demo GITHUB_CLIENT_SECRET=demo GITHUB_APP_SLUG=
  export ANTHROPIC_API_KEY=demo ANTHROPIC_BASE_URL=http://127.0.0.1:9999 OPENAI_API_KEY=
  export LLM_PROVIDER=anthropic SESSION_SECRET=cypher-demo APP_URL=http://localhost:3000
  if docker image inspect cypher-sandbox >/dev/null 2>&1; then
    export SANDBOX_ENABLED=true
  else
    echo "Renders are off: start Docker and run 'docker build -t cypher-sandbox sandbox-image'."
    export SANDBOX_ENABLED=false
  fi
  echo "Demo PRs: http://localhost:3000/acme/web/pull/43  http://localhost:3000/acme/shop/pull/42"
fi

(cd backend && uv sync -q && uv run uvicorn app.main:app --reload --port 8000) &
(cd frontend && pnpm install --silent && pnpm dev --port 3000) &

wait
