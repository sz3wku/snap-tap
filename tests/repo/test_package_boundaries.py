from __future__ import annotations

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


def test_core_does_not_import_cli_layer() -> None:
    core_root = SOURCE_ROOT / "core"
    offenders: list[str] = []

    for path in sorted(core_root.rglob("*.py")):
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
