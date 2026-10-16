"""Enforces the services convention described in app/services/README.md."""

import ast
import importlib
import inspect
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


def _protocol(interface) -> type:
    protocols = [
        obj
        for obj in vars(interface).values()
        if inspect.isclass(obj)
        and obj.__module__ == interface.__name__
        and getattr(obj, "_is_protocol", False)
    ]
    assert len(protocols) == 1, f"{interface.__name__} should define exactly one Protocol"
    return protocols[0]


def _public_methods(cls: type) -> set[str]:
    return {
        name for name in dir(cls) if not name.startswith("_") and callable(getattr(cls, name, None))
    }


def test_services_expose_only_their_interface_methods() -> None:
    """An impl may define one public class, whose public methods are exactly the
    Protocol's. Everything else in impl.py must be `_private`."""
    for service in service_dirs():
        interface = importlib.import_module(f"app.services.{service.name}.interface")
        impl = importlib.import_module(f"app.services.{service.name}.impl")
        protocol = _protocol(interface)

        public = [
            name
            for name, obj in vars(impl).items()
            if not name.startswith("_") and getattr(obj, "__module__", None) == impl.__name__
        ]
        assert len(public) == 1, f"{service.name}/impl.py exposes {public}; prefix helpers with _"

        impl_cls = getattr(impl, public[0])
        assert _public_methods(impl_cls) == _public_methods(protocol), (
            f"{impl_cls.__name__} public methods {sorted(_public_methods(impl_cls))} "
            f"!= {protocol.__name__} {sorted(_public_methods(protocol))}"
        )
