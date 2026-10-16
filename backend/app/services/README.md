# Services

All business logic lives here. Each service is its own folder with three files:

| File           | Purpose                                                                 |
| -------------- | ----------------------------------------------------------------------- |
| `types.py`     | Data models and errors the service accepts or returns.                  |
| `interface.py` | Everything a caller needs: the `Protocol`, re-exported types, and a `create_*` factory. |
| `impl.py`      | The implementation. Private to the folder.                              |

Rules:

- Callers import from the service package (`from app.services.github import GitHubService`),
  which re-exports `interface.py`. Never import another service's `impl.py` or `types.py`
  directly — `tests/test_service_boundaries.py` enforces this.
- Services depend on other services only through their interfaces, passed in via the factory.
- The API layer (`app/api`) is thin: parse the request, call a service, return its result.

| Service   | Responsibility                                                      |
| --------- | ------------------------------------------------------------------- |
| `links`   | Turn a pasted GitHub URL (or `owner/repo#123`) into a PR reference. |
| `github`  | Fetch PR metadata and changed files from the GitHub REST API.       |
| `diff`    | Parse unified patches into hunks/lines and classify files.          |
| `review`  | Build the review model (file tree, noise detection, per-file diffs). |
- Services expose only public methods declared on their `Protocol`. In `impl.py`, the
  implementation class is the only public name, and its public methods must exactly match
  the interface; helpers, constants and extra methods are `_private`. Also enforced by
  `tests/test_service_boundaries.py`.
