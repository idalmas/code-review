# Cypher roadmap

Cypher is the place you review a pull request: read the diff, see the UI change, and talk
about it. Finding bugs is left to review bots (Claude Code Review, Greptile, CodeRabbit, …);
Cypher makes their findings and your own comments easy to work through. It runs on your own
infrastructure against your own GitHub App.

## Shipped

- Large-diff reading: file tree, generated/lockfile files set aside, viewed tracking,
  keyboard navigation, lazy per-file diffs
- Sign in with a GitHub App (expiring tokens, refreshed automatically)
- Review threads inline in the diff, including bot comments; comment on any diff line; reply
- Before/after renders of changed React components in typical and stress states, with
  overflow and error checks
- Click a rendered element to comment on the line of code that produced it
- AI summaries per file, with Cheap / Balanced / Best tiers on Anthropic or OpenAI
- Docker sandbox for running PR code; self-hosting with Docker Compose

## Next

**Review workflow**
- PR conversation panel: PR description, issue comments, and review summaries from bots
- Resolve / unresolve threads (GraphQL), and hide resolved threads by default
- Submit a review (comment / approve / request changes) with comments batched as pending
- Multi-line comments by dragging over line numbers; ```` ```suggestion ```` blocks with
  one-click "apply" preview
- Jump between unresolved threads (`n` / `p`), filter by author (people vs. each bot)
- Comment drafts that survive reloads

**Renders**
- Render every changed component automatically when a PR opens, cached per commit
- Live view of the base version too, side by side, with synced interactions
- Viewport presets (phone / tablet / desktop) and dark mode
- Attach the clicked element's screenshot to the comment (needs image hosting)
- Use the repo's Storybook stories as render states when they exist

## Later

**Platform**
- Postgres for things worth sharing: review progress across devices and teammates,
  render/summary caches, comment drafts
- GitHub webhooks so new comments and pushes appear live
- A separate sandbox runner service, so renders work under Docker Compose without giving the
  backend the Docker socket; rootless Docker or gVisor
- Dependency install caching keyed by lockfile hash
- GitLab and Bitbucket

**AI that helps you read, not judge**
- Suggested review order for big PRs (types and interfaces first, tests last)
- Folder-level summaries and "what changed in this area" for 100+ file PRs
- Explain this hunk in context of the rest of the PR
- Fast triage of which files deserve a render or a closer look (e.g. a decision model like
  Jev), so large PRs stay cheap

**Integrations**
- Badges and filters for known review bots, and "open in Claude Code" for a thread
- Embed a PR's preview deployment (Vercel, Netlify) next to the renders

## Experiments

- **Stress tests** (`STRESS_TESTS_ENABLED`): an LLM writes property-based tests (Hypothesis,
  fast-check) for changed backend functions and runs them before and after the PR. Works,
  but it's bug-finding, which isn't Cypher's job right now, so it's off by default.
