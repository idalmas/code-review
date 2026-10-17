# Orbiter: project notes for Claude

## Commits

- Author every commit as the repo owner: `Ian Dalmas <160072332+idalmas@users.noreply.github.com>`
  (set `git config user.name/user.email` in a fresh checkout, or pass `--author`).
- Credit Claude with a `Co-Authored-By:` trailer at the end of the message, never as the author.

## Backend services

Follow `backend/app/services/README.md`: one folder per service with `types.py`,
`interface.py`, `impl.py`; all business logic lives in services; services expose only the
public methods on their `Protocol`. `tests/test_service_boundaries.py` enforces this.

## Checks before pushing

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm build
```
