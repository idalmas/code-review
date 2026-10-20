"""Fake GitHub + fake LLM for trying Cypher locally without accounts or API keys.

Run through `./dev.sh demo`. Serves two pull requests:
  acme/web#43   a small React change: bot review comments, renders, click-to-comment
  acme/shop#42  a synthetic 300-file PR for the large-diff experience
Sign-in is automatic (you are "demo-user"). Comments you post live in memory until restart.
Standard library only.
"""

import difflib
import io
import json
import os
import random
import tarfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / "sample"
PORT = int(os.environ.get("DEMO_PORT", "9999"))
TOKEN = "demo-token"
USER = {"login": "demo-user", "avatar_url": None, "type": "User"}
BOT = {"login": "claude[bot]", "avatar_url": None, "type": "Bot"}
BASE_SHA, HEAD_SHA = "c" * 40, "d" * 40


def _pull(number: int, repo: str, title: str, files: list[dict], base: str, head: str) -> dict:
    return {
        "number": number,
        "title": title,
        "body": "",
        "state": "open",
        "draft": False,
        "merged": False,
        "user": {"login": "octocat", "avatar_url": None, "type": "User"},
        "base": {"ref": "main", "sha": base},
        "head": {"ref": head[:7], "sha": head},
        "html_url": f"https://github.com/acme/{repo}/pull/{number}",
        "additions": sum(f["additions"] for f in files),
        "deletions": sum(f["deletions"] for f in files),
        "changed_files": len(files),
        "commits": 3,
        "created_at": "2026-10-15T09:00:00Z",
        "updated_at": "2026-10-17T18:00:00Z",
    }


def _sample_file(path: str) -> dict:
    old = (SAMPLE / "base" / path).read_text().splitlines()
    new = (SAMPLE / "head" / path).read_text().splitlines()
    patch = list(difflib.unified_diff(old, new, lineterm="", n=3))[2:]
    return {
        "filename": path,
        "status": "modified",
        "additions": sum(1 for line in patch if line.startswith("+")),
        "deletions": sum(1 for line in patch if line.startswith("-")),
        "changes": len(patch),
        "patch": "\n".join(patch),
    }


# --- acme/web#43: the profile card change --------------------------------------------------
CARD = "web/src/components/ProfileCard.tsx"
WEB_FILES = [_sample_file(CARD)]
WEB_PR = _pull(43, "web", "Refresh profile card", WEB_FILES, BASE_SHA, HEAD_SHA)
COMMENTS: list[dict] = [
    {
        "id": 1,
        "path": CARD,
        "line": 18,
        "side": "RIGHT",
        "in_reply_to_id": None,
        "user": BOT,
        "body": (
            "**Long names overflow the card.** `whitespace-nowrap` replaced `truncate`, so "
            "names wider than the card spill out.\n\n<details><summary>Suggested fix</summary>"
            '\n\n```tsx\n<h3 className="truncate font-semibold text-gray-900">{name}</h3>\n```'
            "\n</details>"
        ),
        "created_at": "2026-10-17T16:00:00Z",
    },
    {
        "id": 2,
        "path": CARD,
        "line": 18,
        "side": "RIGHT",
        "in_reply_to_id": 1,
        "user": {"login": "octocat", "avatar_url": None, "type": "User"},
        "body": "Good catch, will fix.",
        "created_at": "2026-10-17T17:00:00Z",
    },
    {
        "id": 3,
        "path": CARD,
        "line": 20,
        "side": "RIGHT",
        "in_reply_to_id": None,
        "user": {"login": "greptile-apps[bot]", "avatar_url": None, "type": "Bot"},
        "body": "Dropping `flex-wrap` means many tags overflow horizontally. Intentional?",
        "created_at": "2026-10-17T16:05:00Z",
    },
]
for c in COMMENTS:
    c["html_url"] = f"https://github.com/acme/web/pull/43#discussion_r{c['id']}"

# --- acme/shop#42: a big synthetic PR -------------------------------------------------------
random.seed(1)
SHOP_FILES: list[dict] = []
for folder in ["backend/app/services/auth", "backend/app/services/billing",
               "frontend/src/components", "frontend/src/lib", "tests"]:  # fmt: skip
    for i in range(60):
        n = random.randint(3, 40)
        ext = "py" if "backend" in folder or folder == "tests" else "tsx"
        name = f"{folder}/{'test_' if folder == 'tests' else ''}module_{i}.{ext}"
        body = "\n".join(
            f"+    value_{j} = compute({j})" if j % 3 == 0 else f"     line {j}" for j in range(n)
        )
        SHOP_FILES.append({
            "filename": name, "status": random.choice(["modified", "added", "modified"]),
            "additions": n // 3 + 1, "deletions": 0, "changes": n // 3 + 1,
            "patch": f"@@ -10,{n - n // 3 - 1} +10,{n} @@ def handler(request):\n{body}",
        })  # fmt: skip
SHOP_FILES += [
    {"filename": "frontend/pnpm-lock.yaml", "status": "modified", "additions": 4210,
     "deletions": 3900, "changes": 8110},
    {"filename": "backend/app/gen/api_pb2.py", "status": "added", "additions": 900,
     "deletions": 0, "changes": 900, "patch": "@@ -0,0 +1 @@\n+# generated"},
    {"filename": "README.md", "status": "modified", "additions": 1, "deletions": 1, "changes": 2,
     "patch": "@@ -1 +1 @@\n-# Shop\n+# Shop (billing split out)"},
]  # fmt: skip
SHOP_PR = _pull(42, "shop", "Split billing into its own service", SHOP_FILES, "a" * 40, "b" * 40)

HARNESS = (HERE / "harness.tsx").read_text()


def _tarball(version: str, sha: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(SAMPLE / version, arcname=f"acme-web-{sha[:7]}")
    return buf.getvalue()


def _page(items: list, query: dict) -> list:
    page = int(query.get("page", ["1"])[0])
    per = int(query.get("per_page", ["30"])[0])
    return items[(page - 1) * per : page * per]


def _fake_llm(request: dict) -> str:
    """Canned answers: the render harness for the profile card, or a short summary."""
    if "harnesses" in request["system"]:
        return f"```tsx\n{HARNESS}```"
    prompt = request["messages"][0]["content"]
    if "ProfileCard" in prompt:
        return (
            "Adds an online indicator to the avatar and restyles the tags as pills.\n"
            "- Names no longer truncate, so long names overflow the card.\n"
            "- Tags no longer wrap, so many tags overflow horizontally."
        )
    return "Small change to this file. (Demo summary: the demo LLM returns canned text.)"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/login/oauth/authorize":  # approve instantly
            redirect = f"{query['redirect_uri'][0]}?code=demo-code&state={query['state'][0]}"
            self.send_response(302)
            self.send_header("Location", redirect)
            self.end_headers()
            return
        if url.path.startswith("/repos/acme/web/tarball/"):
            sha = url.path.rsplit("/", 1)[1]
            return self._send(_tarball("base" if sha == BASE_SHA else "head", sha), "application/gzip")

        routes = {
            "/user": {**USER, "name": "Demo User"},
            "/repos/acme/web/pulls/43": WEB_PR,
            "/repos/acme/web/pulls/43/files": _page(WEB_FILES, query),
            "/repos/acme/web/pulls/43/comments": _page(COMMENTS, query),
            "/repos/acme/shop/pulls/42": SHOP_PR,
            "/repos/acme/shop/pulls/42/files": _page(SHOP_FILES, query),
            "/repos/acme/shop/pulls/42/comments": [],
        }
        if url.path in routes:
            return self._json(routes[url.path])
        self._json({"message": "Not Found"}, 404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        if self.path == "/login/oauth/access_token":
            return self._json({"access_token": TOKEN, "token_type": "bearer"})
        if self.path.startswith("/v1/messages"):  # Anthropic Messages API
            request = json.loads(raw)
            return self._json({
                "id": "msg_demo", "type": "message", "role": "assistant", "model": request["model"],
                "content": [{"type": "text", "text": _fake_llm(request)}],
                "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 1000, "output_tokens": 100},
            })  # fmt: skip
        if self.path.startswith("/repos/acme/web/pulls/43/comments"):
            body = json.loads(raw)
            parent_id = int(self.path.split("/")[-2]) if self.path.endswith("/replies") else None
            parent = next((c for c in COMMENTS if c["id"] == parent_id), None)
            new_id = 1000 + len(COMMENTS)
            comment = {
                "id": new_id,
                "path": parent["path"] if parent else body["path"],
                "line": parent["line"] if parent else body["line"],
                "side": parent["side"] if parent else body.get("side", "RIGHT"),
                "in_reply_to_id": parent_id,
                "user": USER,
                "body": body["body"],
                "created_at": "2026-10-18T12:00:00Z",
                "html_url": f"https://github.com/acme/web/pull/43#discussion_r{new_id}",
            }
            COMMENTS.append(comment)
            return self._json(comment, 201)
        self._json({"message": "Not Found"}, 404)

    def _json(self, data, status: int = 200) -> None:
        self._send(json.dumps(data).encode(), "application/json", status)

    def _send(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


if __name__ == "__main__":
    print(f"Demo GitHub + LLM on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
