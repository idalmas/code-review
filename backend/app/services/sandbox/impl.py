import asyncio
import os
import shutil
import uuid
from pathlib import Path

from .types import SandboxResult, SandboxUnavailableError

_OUTPUT_TAIL = 20_000
# Containers never run as root. If the backend itself runs as root, jobs run as this
# unprivileged user instead (the sandbox image's own user), which then owns the job folder.
_FALLBACK_UID = 1000


class SandboxServiceImpl:
    def __init__(
        self,
        *,
        enabled: bool,
        network_mode: str,
        proxy: str | None,
        ca_file: str | None,
        memory: str,
        cpus: str,
    ) -> None:
        self._enabled = enabled
        self._network_mode = network_mode
        self._proxy = proxy
        self._ca_file = ca_file
        self._memory = memory
        self._cpus = cpus

    def is_available(self) -> bool:
        return self._enabled and shutil.which("docker") is not None

    async def run(
        self,
        *,
        image: str,
        command: list[str],
        workdir: Path,
        network: bool,
        timeout_seconds: int,
    ) -> SandboxResult:
        if not self.is_available():
            raise SandboxUnavailableError("Sandbox is disabled or Docker isn't installed.")

        name = f"cr-sandbox-{uuid.uuid4().hex[:12]}"
        user = f"{os.getuid()}:{os.getgid()}"
        if os.getuid() == 0:
            await asyncio.to_thread(_chown_tree, workdir, _FALLBACK_UID)
            user = f"{_FALLBACK_UID}:{_FALLBACK_UID}"
        args = [
            "docker", "run", "--rm", "--name", name,
            "--user", user,
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--memory", self._memory, "--memory-swap", self._memory,
            "--cpus", self._cpus,
            "--pids-limit", "512",
            "--tmpfs", "/tmp:rw,size=512m",
            "-v", f"{workdir.resolve()}:/work",
            "-w", "/work",
        ]  # fmt: skip
        if network:
            args += ["--network", self._network_mode]
            if self._proxy:
                args += ["-e", f"HTTPS_PROXY={self._proxy}", "-e", f"HTTP_PROXY={self._proxy}"]
            if self._ca_file:
                args += ["-v", f"{self._ca_file}:/etc/cr-extra-ca.crt:ro"]
                args += ["-e", "NODE_EXTRA_CA_CERTS=/etc/cr-extra-ca.crt"]
                args += ["-e", "npm_config_cafile=/etc/cr-extra-ca.crt"]
                # uv/pip read SSL_CERT_FILE, which replaces the trust store: use a full bundle.
                args += ["-e", "SSL_CERT_FILE=/etc/cr-extra-ca.crt"]
        else:
            args += ["--network", "none"]
        # Arguments go straight to exec (no shell), so paths and names can't inject commands.
        args += [image, *command]

        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        timed_out = False
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout_seconds)
        except TimeoutError:
            timed_out = True
            kill = await asyncio.create_subprocess_exec(
                "docker", "kill", name,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )  # fmt: skip
            await kill.wait()
            stdout, _ = await proc.communicate()
        return SandboxResult(
            exit_code=proc.returncode if proc.returncode is not None else -1,
            timed_out=timed_out,
            output=stdout.decode(errors="replace")[-_OUTPUT_TAIL:],
        )


def _chown_tree(root: Path, uid: int) -> None:
    os.chown(root, uid, uid)
    for directory, dirs, files in os.walk(root):
        for name in dirs + files:
            os.chown(os.path.join(directory, name), uid, uid, follow_symlinks=False)
