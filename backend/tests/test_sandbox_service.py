import asyncio
from pathlib import Path

import pytest

from app.services.sandbox import SandboxUnavailableError, create_sandbox_service


class _Proc:
    returncode = 0

    async def communicate(self):
        return b"ok", None


@pytest.fixture
def captured(monkeypatch):
    calls: list[list[str]] = []

    async def fake_exec(*args, **kwargs):
        calls.append(list(args))
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr("os.chown", lambda *a, **k: None)
    return calls


def _flag(args: list[str], name: str) -> list[str]:
    return [args[i + 1] for i, a in enumerate(args) if a == name]


async def test_offline_run_is_locked_down(captured, tmp_path: Path) -> None:
    sandbox = create_sandbox_service(enabled=True, proxy="http://proxy", ca_file="/ca.crt")
    result = await sandbox.run(image="img", command=["node", "x; rm -rf /"], workdir=tmp_path,
                               network=False, timeout_seconds=5)  # fmt: skip
    args = captured[0]
    assert result.exit_code == 0 and result.output == "ok"
    assert _flag(args, "--network") == ["none"]
    assert _flag(args, "--cap-drop") == ["ALL"]
    assert _flag(args, "--security-opt") == ["no-new-privileges"]
    assert _flag(args, "--pids-limit") == ["512"]
    assert _flag(args, "--memory") and _flag(args, "--cpus")
    assert not _flag(args, "--user")[0].startswith("0:")
    assert _flag(args, "-v") == [f"{tmp_path.resolve()}:/work"]  # only the job folder
    assert not any("PROXY" in a for a in args)  # proxy/CA only for networked installs
    assert args[-2:] == ["node", "x; rm -rf /"]  # passed as argv, never through a shell


async def test_networked_run_gets_proxy_and_ca(captured, tmp_path: Path) -> None:
    sandbox = create_sandbox_service(enabled=True, network_mode="bridge", proxy="http://p:1",
                                     ca_file="/ca.crt")  # fmt: skip
    await sandbox.run(image="img", command=["install"], workdir=tmp_path, network=True,
                      timeout_seconds=5)  # fmt: skip
    args = captured[0]
    assert _flag(args, "--network") == ["bridge"]
    assert "HTTPS_PROXY=http://p:1" in _flag(args, "-e")
    assert "/ca.crt:/etc/cr-extra-ca.crt:ro" in _flag(args, "-v")
    assert {
        "NODE_EXTRA_CA_CERTS=/etc/cr-extra-ca.crt",
        "SSL_CERT_FILE=/etc/cr-extra-ca.crt",
    } <= set(_flag(args, "-e"))


async def test_disabled_sandbox_refuses(tmp_path: Path) -> None:
    sandbox = create_sandbox_service(enabled=False)
    assert sandbox.is_available() is False
    with pytest.raises(SandboxUnavailableError):
        await sandbox.run(image="i", command=["x"], workdir=tmp_path, network=False,
                          timeout_seconds=1)  # fmt: skip


async def test_never_runs_containers_as_root(captured, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("os.getuid", lambda: 0)
    monkeypatch.setattr("os.getgid", lambda: 0)
    await create_sandbox_service(enabled=True).run(
        image="i", command=["x"], workdir=tmp_path, network=False, timeout_seconds=1
    )
    assert _flag(captured[0], "--user") == ["1000:1000"]
