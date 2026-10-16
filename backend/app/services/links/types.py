from pydantic import BaseModel, Field


class InvalidLinkError(ValueError):
    """Raised when input can't be understood as a GitHub pull request link."""


class PullRequestRef(BaseModel):
    owner: str
    repo: str
    number: int = Field(gt=0)

    @property
    def app_path(self) -> str:
        """Path in this tool. Mirrors GitHub's, so swapping the host is enough."""
        return f"/{self.owner}/{self.repo}/pull/{self.number}"

    @property
    def github_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}/pull/{self.number}"


class ResolvedLink(BaseModel):
    owner: str
    repo: str
    number: int
    app_path: str
    github_url: str
