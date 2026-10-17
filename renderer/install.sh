#!/bin/sh
# Install a JS project's dependencies without running any package lifecycle scripts.
# Usage: install.sh <dir>...   (each dir contains the lockfile)
set -eu
for dir in "$@"; do
  cd "$dir"
  if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile --ignore-scripts
  elif [ -f yarn.lock ]; then yarn install --frozen-lockfile --ignore-scripts --non-interactive
  elif [ -f package-lock.json ]; then npm ci --ignore-scripts --no-audit --no-fund
  else npm install --ignore-scripts --no-audit --no-fund
  fi
done
