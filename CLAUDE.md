# Cypher: project notes for Claude

Local setup, demo mode, and how UI feedback maps to code: see `AGENTS.md`.

## Commits

- Author every commit as the repo owner: `Ian Dalmas <160072332+idalmas@users.noreply.github.com>`
  (set `git config user.name/user.email` in a fresh checkout, or pass `--author`).
- Credit Claude with a `Co-Authored-By:` trailer at the end of the message, never as the author.

## Product direction

Cypher owns the review surface (reading, rendering, commenting) and plugs into review bots
for bug-finding rather than competing with them. See ROADMAP.md before adding features.

## Backend services

Follow `backend/app/services/README.md`: one folder per service with `types.py`,
`interface.py`, `impl.py`; all business logic lives in services; services expose only the
public methods on their `Protocol`. `tests/test_service_boundaries.py` enforces this.

## Checks before pushing

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm build
```
