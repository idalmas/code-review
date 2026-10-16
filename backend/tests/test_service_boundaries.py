"""Enforces the services convention described in app/services/README.md."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
SERVICES = APP / "services"
REQUIRED = {"__init__.py", "interface.py", "impl.py", "types.py"}


def service_dirs() -> list[Path]:
    return [p for p in SERVICES.iterdir() if p.is_dir() and not p.name.startswith("__")]


def test_every_service_has_interface_impl_and_types() -> None:
    for service in service_dirs():
        missing = REQUIRED - {p.name for p in service.iterdir()}
        assert not missing, f"{service.name} is missing {sorted(missing)}"


def test_no_one_imports_another_services_internals() -> None:
    violations = []
    for file in APP.rglob("*.py"):
        own_service = file.relative_to(SERVICES).parts[0] if file.is_relative_to(SERVICES) else None
        for node in ast.walk(ast.parse(file.read_text())):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            parts = node.module.split(".")
            if parts[:2] != ["app", "services"] or len(parts) < 4:
                continue
            target_service = parts[2]
            if target_service != own_service:
                violations.append(f"{file.relative_to(APP)} imports {node.module}")
    assert not violations, "Import services via their package, not internals:\n" + "\n".join(
        violations
    )
