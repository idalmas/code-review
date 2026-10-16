import re
from urllib.parse import urlsplit

from .types import InvalidLinkError, PullRequestRef, ResolvedLink

# GitHub's own limits: owners are alnum + hyphen; repos also allow `.` and `_`.
_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
_REPO = r"[A-Za-z0-9._-]{1,100}"

_PATH_RE = re.compile(rf"^/(?P<owner>{_OWNER})/(?P<repo>{_REPO})/pulls?/(?P<number>\d+)(?:/.*)?$")
_SHORTHAND_RE = re.compile(rf"^(?P<owner>{_OWNER})/(?P<repo>{_REPO})#(?P<number>\d+)$")
_GITHUB_HOSTS = {"github.com", "www.github.com"}


class LinkServiceImpl:
    def parse(self, raw: str) -> PullRequestRef:
        text = raw.strip()
        if not text:
            raise InvalidLinkError("Paste a GitHub pull request link.")

        match = _SHORTHAND_RE.match(text)
        if match is None:
            match = self._match_url(text)

        number = int(match["number"])
        if number <= 0:
            raise InvalidLinkError("Pull request numbers start at 1.")
        repo = match["repo"].removesuffix(".git")
        return PullRequestRef(owner=match["owner"], repo=repo, number=number)

    def resolve(self, raw: str) -> ResolvedLink:
        ref = self.parse(raw)
        return ResolvedLink(
            owner=ref.owner,
            repo=ref.repo,
            number=ref.number,
            app_path=ref.app_path,
            github_url=ref.github_url,
        )

    @staticmethod
    def _match_url(text: str) -> re.Match[str]:
        if "://" not in text:
            text = "https://" + text
        parts = urlsplit(text)
        if parts.hostname not in _GITHUB_HOSTS:
            raise InvalidLinkError("Only github.com pull request links are supported.")
        match = _PATH_RE.match(parts.path.rstrip("/") or "/")
        if match is None:
            raise InvalidLinkError(
                "That doesn't look like a pull request. "
                "Expected https://github.com/<owner>/<repo>/pull/<number>."
            )
        return match
