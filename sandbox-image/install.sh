#!/bin/sh
# Install a project's dependencies without running code from the packages themselves:
# JS lifecycle scripts are disabled and Python is wheels-only (no source builds).
# Usage: install.sh <dir>...
set -eu
for dir in "$@"; do
  cd "$dir"
  if [ -f package.json ]; then
    if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile --ignore-scripts
    elif [ -f yarn.lock ]; then yarn install --frozen-lockfile --ignore-scripts --non-interactive
    elif [ -f package-lock.json ]; then npm ci --ignore-scripts --no-audit --no-fund
    else npm install --ignore-scripts --no-audit --no-fund
    fi
    # Stress tests import fast-check; provide it without touching the project's lockfile.
    mkdir -p node_modules
    for pkg in fast-check pure-rand; do
      [ -d "node_modules/$pkg" ] || cp -r "/sandbox/node_modules/$pkg" node_modules/
    done
  fi
  if [ -f pyproject.toml ] || [ -f requirements.txt ]; then
    if [ -f uv.lock ]; then uv sync --frozen --no-build --no-install-project
    elif [ -f pyproject.toml ] && grep -q '^dependencies' pyproject.toml; then
      uv venv -q && uv pip install -q --no-build -r pyproject.toml
    elif [ -f requirements.txt ]; then uv venv -q && uv pip install -q --no-build -r requirements.txt
    else uv venv -q
    fi
    uv pip install -q --python .venv/bin/python --no-build pytest==9.1.1 hypothesis==6.170.1
  fi
done
