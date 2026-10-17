# Code Review

A web tool that makes reviewing large GitHub pull requests manageable.

Paste a PR link (or swap `github.com` for this app's host in any PR URL) and you get:

- **A collapsible file tree** instead of one endless page. Single-child folders are merged.
- **Noise set aside**: lockfiles, generated and vendored code are hidden by default and counted
  separately, so a "+12,000" PR that's really 400 lines of code looks like it.
- **Viewed tracking that survives reloads**, with progress by files *and* by lines. A viewed
  file un-views itself if a later push changes its diff stats.
- **Keyboard flow**: `j`/`k` next/previous file, `v` mark viewed and jump to the next
  unviewed file, `/` filter.
- **Lazy per-file diffs** with the next file prefetched, so thousands of files stay fast.
- **Sign in with GitHub**: every request runs as the signed-in user, so you see exactly the
  repos you can see on GitHub. Sessions are encrypted httpOnly cookies, with no database.

## Layout

```
backend/   FastAPI REST API (Python 3.12+, uv)
  app/
    main.py          app factory, CORS, router wiring
    config.py        settings from env / .env
    api/             thin HTTP layer: routes, dependency wiring, error mapping
    services/        ALL business logic (see backend/app/services/README.md)
      auth/          Sign in with GitHub (OAuth), encrypted cookie sessions
      links/         GitHub URL → PR reference
      github/        GitHub REST client with caching + pagination
      diff/          unified-diff parser and file classifier
      review/        builds the review model from the services above
  tests/
frontend/  Next.js (App Router, TypeScript, Tailwind)
  src/app/[owner]/[repo]/pull/[number]/[[...tab]]   mirrors GitHub's PR URLs
```

Each service folder has `types.py`, `interface.py` (everything a caller needs: a `Protocol`,
re-exported types and a `create_*` factory) and `impl.py`. Code outside a service only imports
its package; a test fails if anything reaches into another service's internals.

## REST API

| Method | Path                                                    | Returns                                  |
| ------ | ------------------------------------------------------- | ---------------------------------------- |
| GET    | `/api/health`                                           | `{status}`                               |
| GET    | `/api/auth/login?return_to=`                            | redirect to GitHub sign-in               |
| GET    | `/api/auth/callback`                                    | sets session cookie, redirects back      |
| GET    | `/api/auth/me`                                          | `{login_enabled, user}` (never the token)|
| POST   | `/api/auth/logout`                                      | clears session                           |
| POST   | `/api/links/resolve` `{url}`                            | owner, repo, number, `app_path`          |
| GET    | `/api/repos/{owner}/{repo}/pulls/{number}/review`       | PR metadata, classified file list, stats |
| GET    | `/api/repos/{owner}/{repo}/pulls/{number}/files/{path}` | parsed hunks for one file                |

Interactive docs at http://localhost:8000/docs. The browser only talks to `/api/*` on the
Next.js origin, which proxies to FastAPI (`BACKEND_URL`).

## Running locally

Needs [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/).

```bash
cp backend/.env.example backend/.env
./dev.sh                               # API on :8000, web on :3000
```

To enable sign-in (needed for private repos, and for more than 60 GitHub requests/hour), create
a GitHub OAuth app at **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**
with callback URL `http://localhost:3000/api/auth/callback`, then fill in `GITHUB_CLIENT_ID`,
`GITHUB_CLIENT_SECRET` and `SESSION_SECRET` in `backend/.env`.

Then open http://localhost:3000.

Checks:

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm build
```
