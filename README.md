# Orbiter

A review surface for GitHub pull requests: read big diffs calmly, see UI changes rendered, and comment right where it matters. Works alongside AI reviewers like Claude Code Review and Greptile, whose comments show up inline.

Paste a PR link (or swap `github.com` for this app's host in any PR URL) and you get:

- **A collapsible file tree** instead of one endless page. Single-child folders are merged.
- **Noise set aside**: lockfiles, generated and vendored code are hidden by default and counted
  separately, so a "+12,000" PR that's really 400 lines of code looks like it.
- **Viewed tracking that survives reloads**, with progress by files *and* by lines. A viewed
  file un-views itself if a later push changes its diff stats.
- **Keyboard flow**: `j`/`k` next/previous file, `v` mark viewed and jump to the next
  unviewed file, `/` filter.
- **Lazy per-file diffs** with the next file prefetched, so thousands of files stay fast.
- **AI summaries per file** with a Cheap / Balanced / Best picker. Bring your own Anthropic
  or OpenAI key; with no key, AI features stay hidden.
- **Review threads inline**, including comments from Claude Code Review, Greptile and other
  review bots. Hover any diff line to comment, reply in place; everything posts to GitHub as you.
- **Before/after renders of changed React components**, side by side, in typical and stress
  states (very long text, empty, many items, emoji/RTL, phone width), with automatic checks
  for crashes, console errors and overflowing layout. An LLM writes the props; the PR's code
  runs in a locked-down Docker container.
- **Click to comment on a render**: click any element of the live render and comment on the
  line of code that produced it.
- **Sign in with a GitHub App**: every request runs as the signed-in user, so you see exactly
  the repos you can see on GitHub. Sessions are encrypted httpOnly cookies, with no database.

See [ROADMAP.md](ROADMAP.md) for what's next. Experimental and off by default: LLM-written
stress tests for changed backend code (`STRESS_TESTS_ENABLED=true`).

## Layout

```
backend/   FastAPI REST API (Python 3.12+, uv)
  app/
    main.py          app factory, CORS, router wiring
    config.py        settings from env / .env
    api/             thin HTTP layer: routes, dependency wiring, error mapping
    services/        ALL business logic (see backend/app/services/README.md)
      auth/          Sign in with GitHub (GitHub App), encrypted cookie sessions
      links/         GitHub URL → PR reference
      llm/           Anthropic or OpenAI behind three tiers (cheap / balanced / best)
      github/        GitHub REST client with caching + pagination
      diff/          unified-diff parser and file classifier
      review/        builds the review model from the services above
      sandbox/       runs untrusted code in locked-down Docker containers
      render/        before/after component renders (downloads both commits, LLM harness)
      stress/        experimental: property-based stress tests of changed backend code
sandbox-image/  Docker image for the sandbox: Vite + Chromium renderer, pytest/Hypothesis,
                node:test/fast-check
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
| POST   | `/api/repos/{owner}/{repo}/pulls/{number}/summaries` `{path, tier}` | AI summary of one file (signed in) |
| GET    | `/api/llm`                                              | whether AI is on, model per tier         |
| POST   | `/api/repos/{owner}/{repo}/pulls/{number}/renders` `{path, tier}` | start a before/after render (signed in) |
| GET    | `/api/renders/{id}`                                     | render status and per-state results      |
| GET    | `/api/renders/{id}/{base\|head}/{index}.png`            | screenshot (only for whoever started it) |
| POST   | `/api/repos/{owner}/{repo}/pulls/{number}/stress` `{path, tier}` | start stress tests (signed in) |
| GET    | `/api/stress/{id}`                                      | verdict, test output, generated tests    |

Interactive docs at http://localhost:8000/docs. The browser only talks to `/api/*` on the
Next.js origin, which proxies to FastAPI (`BACKEND_URL`).

## Running locally

```bash
./dev.sh demo   # sample PRs against a built-in fake GitHub + LLM, no setup needed
./dev.sh        # real GitHub, configured in backend/.env
```

Full setup (GitHub App, API keys, renders) and how to give UI feedback: [AGENTS.md](AGENTS.md).
Self-hosting for a team: [docs/self-hosting.md](docs/self-hosting.md).

## Self-hosting

`docker compose up -d --build` runs everything in your own infrastructure. No vendor servers,
no database, no telemetry. See [docs/self-hosting.md](docs/self-hosting.md), which also covers
compliance (why self-hosting keeps this inside your own SOC 2 scope).

## Checks

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm build
```
