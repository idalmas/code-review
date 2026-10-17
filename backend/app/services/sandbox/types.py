from pydantic import BaseModel


class SandboxUnavailableError(Exception):
    """Docker isn't configured or reachable, so untrusted code can't be run safely."""


class SandboxResult(BaseModel):
    exit_code: int
    timed_out: bool
    # Combined stdout/stderr, tail only.
    output: str
