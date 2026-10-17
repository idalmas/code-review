from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.services.llm import Tier

StressStatus = Literal["queued", "downloading", "installing", "writing_tests", "running",
                       "done", "skipped", "failed"]  # fmt: skip
Language = Literal["python", "javascript"]
# passed: no failures after the PR. new_failure: fails after but passed before.
# existing_failure: failed before too. failure: fails, and there was no before (new file).
Verdict = Literal["passed", "new_failure", "existing_failure", "failure"]


class StressUnavailableError(Exception):
    """Stress tests need both the sandbox (Docker) and an LLM to be configured."""


class NotStressableError(ValueError):
    """Not a backend source file (Python, JS or TS) this PR changed."""


class StressJobNotFoundError(LookupError):
    """No such job for this viewer (unknown, expired, or someone else's)."""


class TestRun(BaseModel):
    passed: bool
    timed_out: bool
    # Test runner output, tail only. Failing runs include the input that broke the code.
    output: str


class StressJob(BaseModel):
    id: str
    path: str
    tier: Tier
    language: Language
    status: StressStatus
    message: str | None = None
    created_at: datetime
    # The generated tests, so reviewers can see exactly what was tried.
    test_code: str | None = None
    base: TestRun | None = None
    head: TestRun | None = None
    verdict: Verdict | None = None
