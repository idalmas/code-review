# Self-hosting

Cypher is built to run entirely inside your own infrastructure. There is no vendor
server in the loop: your browser talks to your deployment, and your deployment talks to
GitHub (and, if you turn on AI features, to the LLM provider *you* configure with *your* key).

```
browser ──► web (Next.js, :3000) ──► backend (FastAPI, internal) ──► GitHub / GitHub Enterprise
                                                                └──► your LLM provider (optional)
```

## What it stores

- **Nothing server-side.** No database, no disk writes. PR data is cached in memory for a
  couple of minutes, keyed per user.
- **Session cookie** (encrypted with your `SESSION_SECRET`, httpOnly, SameSite=Lax) holding the
  signed-in user's GitHub token. Rotating `SESSION_SECRET` signs everyone out.
- **"Viewed" checkmarks** live in each reviewer's browser (localStorage).
- **No telemetry.** Next.js telemetry is disabled in the image.

## Deploy with Docker Compose

1. **Create a GitHub App** (see [below](#github-app)).
2. **Configure** the backend:
   ```bash
   cp backend/.env.example backend/.env
   ```
   Set `APP_URL`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_APP_SLUG`, and
   `SESSION_SECRET` (`openssl rand -base64 32`).
   For GitHub Enterprise Server also set `GITHUB_WEB_URL` and `GITHUB_API_URL`.
3. **Run it:**
   ```bash
   docker compose up -d --build
   ```
4. Put it behind your usual TLS-terminating proxy or load balancer, pointing at port 3000.
   Only the web container is published; the backend is reachable only from it.

When `APP_URL` starts with `https://`, cookies are marked `Secure`.

## AI features (optional)

Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `backend/.env` (both + `LLM_PROVIDER` to choose).
Reviewers then get a per-file **Summarize** button with three tiers (Cheap / Balanced / Best);
the operator decides which model backs each tier (`LLM_MODEL_CHEAP` etc.).

- What's sent: the one file's diff, its path and the PR title, and only when someone clicks.
  Requests go directly from your backend to the provider, using your key and your account's
  data-retention terms.
- Who can use it: when GitHub sign-in is enabled, only signed-in users, and only for PRs they
  can read, so anonymous visitors can't spend your credits.
- Anthropic refusals on Sonnet/Opus are retried server-side on Anthropic's recommended
  fallback model. Disable with `ANTHROPIC_SERVER_FALLBACKS=false`.

## Component renders and stress tests (optional)

Two features run the PR's own code, in Docker containers started by the backend:

- **Renders:** a changed React component, before and after, in typical and stress states,
  screenshotted in Chromium.
- **Stress tests** (experimental, also needs `STRESS_TESTS_ENABLED=true`): property-based
  tests (Hypothesis for Python, fast-check for Node/Bun JS/TS) for the functions a PR
  changed, run before and after.

Each job:

1. Downloads both commits as tarballs (with the reviewer's GitHub token) and unpacks them
   with path-traversal, link and size checks.
2. **Install container:** network on, but no code from the packages runs: JS install
   scripts are disabled (`--ignore-scripts`) and Python is wheels-only (`--no-build`).
3. An LLM writes the harness or tests. The PR source is passed as untrusted data.
4. **Run container:** `--network none`.

Every container runs as a non-root user (never uid 0, even if the backend runs as root) with
all capabilities dropped, `no-new-privileges`, 2 GB memory, 2 CPUs, 512 processes, a private
`/tmp`, and a time limit. Only the job's own folder is mounted; no secrets or tokens are
passed in. Commands are passed as argument lists, never through a shell. Source trees and
dependencies are deleted after each job; results expire after two hours and are only shown
to the person who started them.

Setup, on a host with Docker:

```bash
docker build -t cypher-sandbox sandbox-image
# backend/.env
SANDBOX_ENABLED=true
# Behind a TLS-inspecting corporate proxy, for the install step only.
# The CA file must be a full bundle (system roots + your proxy's CA).
# SANDBOX_INSTALL_PROXY=http://proxy:3128
# SANDBOX_INSTALL_CA_FILE=/etc/ssl/certs/corp-bundle.crt
```

The backend calls the `docker` CLI, so run it directly on the Docker host (as `./dev.sh`
does). Running these from inside the Compose backend container would require mounting the
Docker socket into it, which gives that container root on the host, so the Compose setup
leaves them off.

Assumptions: a React frontend installed with npm, pnpm or yarn (Next.js `Link`, `Image` and
navigation hooks are replaced with simple stand-ins), and a Node/Bun or Python backend
(`package.json`, or `pyproject.toml`/`requirements.txt`, optionally with `uv.lock`).

## GitHub App

Cypher signs people in through a GitHub App you own (create it under your organization:
**Settings → Developer settings → GitHub Apps → New GitHub App**):

- **Homepage URL:** your `APP_URL`, e.g. `https://review.yourcompany.com`
- **Callback URL:** `<APP_URL>/api/auth/callback`
- **Expire user authorization tokens:** on (Cypher refreshes them automatically)
- **Webhook:** off. Cypher doesn't need one.
- **Repository permissions:**
  - Contents: **Read** (to render components and run checks on the PR's code)
  - Pull requests: **Read and write** (to read the diff and post review comments)
  - Metadata: Read (required by GitHub)
- **Where can this app be installed:** only this account

Then **Generate a client secret**, copy the Client ID, and note the App's URL name
(`github.com/apps/<slug>`) for `GITHUB_APP_SLUG`. Install the App on the repositories you want
to review. People can only use Cypher on repos where it's installed *and* they have access.

An OAuth app also works (same settings, no slug), but it can only ask for the broad `repo`
scope, so a GitHub App is recommended.

## Access model

- Every GitHub request uses the signed-in user's own token, so people only see repos they
  can already see on GitHub. Signed-out visitors can only open public repos.
- Review comments are posted as the person who wrote them, never as a shared bot account.
- GitHub App tokens are scoped to the permissions above and the repos the App is installed
  on, and expire after 8 hours.
- Restrict who can sign in the same way you restrict any internal tool: network policy, VPN,
  or your SSO proxy in front of the web container.

## Compliance (SOC 2 and friends)

SOC 2 is an audit of a *service provider's* controls over customer data. When you self-host,
there's no third-party provider holding your code or tokens: the software runs under your
controls, inside your existing SOC 2 / ISO 27001 scope, like any other internal tool. What
your security team will typically want instead is:

- the source (this repo) and the dependency lockfiles (`backend/uv.lock`,
  `frontend/pnpm-lock.yaml`) for review,
- the data-flow summary above,
- if AI features are enabled, confirmation that the LLM provider is one you already have a
  data-processing agreement with (you supply the key, so you choose).

This isn't legal advice. If the project is ever offered as a hosted service, *that* offering
would be in scope for a vendor audit.
