from pathlib import Path
from typing import Protocol

from .types import SandboxResult, SandboxUnavailableError

__all__ = ["SandboxResult", "SandboxService", "SandboxUnavailableError", "create_sandbox_service"]


class SandboxService(Protocol):
    """Runs untrusted code (a PR's dependencies, components, tests) in a locked-down
    container: no secrets, no capabilities, non-root, CPU/memory/process/time limits, and
    no network unless `network=True`. The only thing shared with it is `workdir`."""

    def is_available(self) -> bool: ...

    async def run(
        self,
        *,
        image: str,
        command: list[str],
        workdir: Path,
        network: bool,
        timeout_seconds: int,
    ) -> SandboxResult:
        """Runs `command` with `workdir` mounted at /work. Raises `SandboxUnavailableError`."""
        ...


def create_sandbox_service(
    *,
    enabled: bool,
    network_mode: str = "bridge",
    proxy: str | None = None,
    ca_file: str | None = None,
    memory: str = "2g",
    cpus: str = "2",
) -> SandboxService:
    """`network_mode`, `proxy` and `ca_file` apply only to networked runs (dependency
    installs), e.g. for a corporate proxy that inspects TLS."""
    from .impl import SandboxServiceImpl

    return SandboxServiceImpl(
        enabled=enabled,
        network_mode=network_mode,
        proxy=proxy,
        ca_file=ca_file,
        memory=memory,
        cpus=cpus,
    )
