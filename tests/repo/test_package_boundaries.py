from __future__ import annotations

import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "snap_tap"
PUBLIC_DOC_ROOTS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "ROADMAP.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "SECURITY.md",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / ".github",
    REPO_ROOT / "docs",
    SOURCE_ROOT,
)


def _files(pattern: str) -> list[Path]:
    return sorted(path for path in SOURCE_ROOT.rglob(pattern) if path.is_file())


def _public_docs() -> list[Path]:
    docs: list[Path] = []
    for root in PUBLIC_DOC_ROOTS:
        if root.is_file() and root.suffix == ".md":
            docs.append(root)
        elif root.is_dir():
            docs.extend(path for path in root.rglob("*.md") if path.is_file())
    return sorted(set(docs))


def test_source_uses_standalone_package_imports() -> None:
    forbidden = (
        "from " "core.",
        "import " "core.",
        '"core.',
        "'core.",
        "from " "cli.",
        "import " "cli.",
        '"cli.',
        "'cli.",
    )

    offenders: list[str] = []
    for path in _files("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                rel_path = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel_path}: {needle}")

    assert offenders == []


def test_runtime_packages_do_not_import_cli_layer() -> None:
    runtime_roots = (
        SOURCE_ROOT / "backends",
        SOURCE_ROOT / "device",
        SOURCE_ROOT / "evidence",
        SOURCE_ROOT / "primitives",
        SOURCE_ROOT / "semantics",
        SOURCE_ROOT / "snapshots",
        SOURCE_ROOT / "targets",
    )
    offenders: list[str] = []

    for runtime_root in runtime_roots:
        for path in sorted(runtime_root.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "snap_tap.cli" in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []


def test_public_docs_use_snap_tap_command_name() -> None:
    legacy_phrases = (
        "hakar mobile",
        ".\\scripts\\hakar.ps1",
        "mobile snap",
        "mobile tap",
        "mobile input",
        "mobile replace-text",
        "mobile snapshot",
        "mobile back",
        "mobile home",
        "mobile swipe",
        "mobile wait",
    )
    offenders: list[str] = []

    for path in _public_docs():
        text = path.read_text(encoding="utf-8").lower()
        for phrase in legacy_phrases:
            if phrase in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {phrase}")

    assert offenders == []


def test_source_user_facing_strings_use_snap_tap_command_name() -> None:
    legacy_phrases = (
        "mobile snap",
        "mobile tap",
        "mobile input",
        "mobile replace-text",
        "mobile snapshot",
    )
    offenders: list[str] = []

    for path in _files("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for phrase in legacy_phrases:
            if phrase in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {phrase}")

    assert offenders == []


def test_public_docs_do_not_use_private_device_serial_examples() -> None:
    private_serials = ("RFCN4010FCK", "R58R502HMSJ")
    offenders: list[str] = []

    for path in _public_docs():
        text = path.read_text(encoding="utf-8")
        for serial in private_serials:
            if serial in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {serial}")

    assert offenders == []


def test_public_modules_have_clean_all_exports() -> None:
    public_modules = (
        "snap_tap",
        "snap_tap.backends",
        "snap_tap.backends.capabilities",
        "snap_tap.backends.contracts",
        "snap_tap.device",
        "snap_tap.device.discovery",
        "snap_tap.device.identity",
        "snap_tap.evidence",
        "snap_tap.primitives",
        "snap_tap.semantics",
        "snap_tap.snapshots",
        "snap_tap.targets",
    )
    offenders: list[str] = []

    for module_name in public_modules:
        module = importlib.import_module(module_name)
        exports = getattr(module, "__all__", None)
        if not isinstance(exports, list):
            offenders.append(f"{module_name}: missing __all__ list")
            continue
        for name in exports:
            if not isinstance(name, str) or not name:
                offenders.append(f"{module_name}: invalid export {name!r}")
                continue
            if name.startswith("_") and name != "__version__":
                offenders.append(f"{module_name}: private export {name}")
            if not hasattr(module, name):
                offenders.append(f"{module_name}: missing exported attr {name}")

    assert offenders == []


def test_public_docs_do_not_expose_private_python_paths() -> None:
    private_paths = (
        "snap_tap.backends._shared",
        "snap_tap.snapshots._",
        "snap_tap.targets._",
        "src/snap_tap/backends/_shared",
        "src\\snap_tap\\backends\\_shared",
    )
    offenders: list[str] = []

    for path in _public_docs():
        text = path.read_text(encoding="utf-8")
        for private_path in private_paths:
            if private_path in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {private_path}")

    assert offenders == []
