# Cypher: working on it locally

Instructions for people and coding agents. Project conventions are in `CLAUDE.md`.

## Set up locally

You need macOS or Linux with:

- [uv](https://docs.astral.sh/uv/) (Python): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node 22+ and [pnpm](https://pnpm.io/): `npm install -g pnpm`
- Docker (Docker Desktop on macOS), only for component renders

```bash
git clone https://github.com/idalmas/cypher.git
cd cypher
git checkout claude/amazing-wright-26dj6x   # until it's merged
```

### 1. Try it in demo mode (no accounts, no keys)

```bash
docker build -t cypher-sandbox sandbox-image   # once, ~5 min; skip if you don't need renders
./dev.sh demo
```

Then open:

- http://localhost:3000/acme/web/pull/43: a React change with bot review comments, renders,
  and click-to-comment
- http://localhost:3000/acme/shop/pull/42: a 300-file PR for the large-diff experience

"Sign in with GitHub" signs you in instantly as `demo-user`. GitHub and the LLM are faked by
`demo/server.py`, so everything behaves the same every run; comments you post disappear when
you stop it (Ctrl+C). The first page load takes a few seconds while Next.js compiles.

### 2. Use it on real pull requests

1. Create a GitHub App: checklist in [docs/self-hosting.md](docs/self-hosting.md#github-app),
   with callback URL `http://localhost:3000/api/auth/callback`. Install it on a repo.
2. `cp backend/.env.example backend/.env` and fill in:
   - `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_APP_SLUG`
   - `SESSION_SECRET` (`openssl rand -base64 32`)
   - optionally `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (Summarize, Render)
   - optionally `SANDBOX_ENABLED=true` (Render; needs the Docker image above)
3. `./dev.sh`, open http://localhost:3000, and paste a PR link (or replace `github.com` with
   `localhost:3000` in any PR URL).

Comments you post here go to the real PR on GitHub.

### Checks

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm lint && pnpm build
```

## Giving UI/UX feedback

Feedback is easiest to act on precisely when it says **where** (using the names below),
**what you see**, and **what you want instead**. A good note:

> **AI bar** on `acme/web#43` › `ProfileCard.tsx`: Summarize and Render look like two unrelated
> buttons. Want them in one row, Render first. (screenshot)

Helpful to include:

- The URL. It encodes the PR and the open file (`…/pull/43#web%2Fsrc%2F…`), so the exact
  screen can be reopened. In demo mode everything else is reproducible too.
- A screenshot, with the spot circled if it's small.
- Window width and light/dark mode if it's about layout or color (Cypher follows the OS theme).
- What you did just before, for anything about behavior.

Quick tags at the start help sort a batch: `[bug]`, `[layout]`, `[copy]`, `[flow]`, `[idea]`.

### Names for parts of the UI

| Name               | What it is                                                  | Code (`frontend/src/…`)                                    |
| ------------------ | ----------------------------------------------------------- | ---------------------------------------------------------- |
| Top bar            | "Cypher", your avatar, Sign in / out                       | `app/layout.tsx`, `components/AuthMenu.tsx`                |
| Home               | "Open a pull request" and the link box                      | `app/page.tsx`, `components/LinkForm.tsx`                  |
| PR header          | Title, branch, file count, viewed progress                  | `components/review/ReviewHeader.tsx`                       |
| File tree          | Left sidebar: filter, toggles, files, comment counts        | `components/review/FileTree.tsx`, `ReviewApp.tsx`          |
| File header        | Sticky bar with the file path, GitHub link, Viewed          | `components/review/FileDiffView.tsx`                       |
| AI bar             | Cheap / Balanced / Best, Summarize, Render                  | `TierPicker.tsx`, `FileSummaryPanel.tsx`, `RenderPanel.tsx` |
| Summary            | The text Summarize produces                                 | `components/review/FileSummaryPanel.tsx`                   |
| Render panel       | States with Before / After screenshots and problem badges   | `components/review/RenderPanel.tsx`                        |
| Live view          | "Comment on render": the clickable render and its comment box | `components/review/LiveInspector.tsx`, `sandbox-image/inspector.ts` |
| Diff               | Hunks, line numbers, the + button on hover                  | `components/review/FileDiffView.tsx`                       |
| Thread             | A comment and its replies, bot badge, Reply                 | `components/review/CommentThreadView.tsx`, `components/Markdown.tsx` |
| Composer           | The text box for a new comment or reply                     | `components/review/CommentComposer.tsx`                    |
| Outdated comments  | Collapsed list above the diff                               | `components/review/FileDiffView.tsx`                       |
| Colors and type    | Theme tokens, light/dark                                    | `app/globals.css`                                          |

Keyboard: `j` / `k` next / previous file, `v` toggle viewed, `/` filter files.

## Notes for agents working from feedback

- Reproduce on the demo first (`./dev.sh demo`); the URLs above are stable.
- Keep copy short; prefer tooltips over helper sentences.
- After UI changes, run the checks and look at the screen (Playwright screenshots work well).
