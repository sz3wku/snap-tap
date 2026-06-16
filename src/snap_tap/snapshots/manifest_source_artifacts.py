from __future__ import annotations

from collections.abc import Mapping
import hashlib
from pathlib import Path

from snap_tap.snapshots.manifest import SNAPSHOT_MANIFEST_SCHEMA_VERSION
from snap_tap.snapshots.manifest_source_common import (
    mapping,
    non_negative_int,
    required_text,
    sha256_text,
)
from snap_tap.snapshots.manifest_source_types import (
    SnapshotManifestSourceError,
    invalid_manifest_source,
)
from snap_tap.snapshots.models import SnapshotArtifactRef


def artifact_ref(
    payload: Mapping[object, object],
    *,
    capture_dir: Path,
    name: str,
) -> SnapshotArtifactRef:
    path = _artifact_path(payload.get("path"), capture_dir=capture_dir)
    data = _read_artifact_bytes(path)
    expected_length = non_negative_int(payload.get("byte_length"), f"{name}.byte_length")
    expected_sha = sha256_text(payload.get("sha256"), f"{name}.sha256")
    if len(data) != expected_length:
        raise invalid_manifest_source(f"Snapshot {name} artifact byte length mismatch.")
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != expected_sha:
        raise invalid_manifest_source(f"Snapshot {name} artifact sha256 mismatch.")
    return SnapshotArtifactRef(
        path=str(path),
        sha256=actual_sha,
        byte_length=len(data),
        metadata=_artifact_metadata(payload, name=name),
    )


def artifact_payload(
    artifacts: Mapping[object, object],
    name: str,
) -> Mapping[object, object]:
    if name not in artifacts:
        raise invalid_manifest_source(f"Snapshot manifest requires {name} artifact ref.")
    return mapping(artifacts[name], f"artifacts.{name}")


def manifest_ref(path: Path) -> SnapshotArtifactRef:
    data = _read_artifact_bytes(path)
    return SnapshotArtifactRef(
        path=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        byte_length=len(data),
        metadata={"schema_version": SNAPSHOT_MANIFEST_SCHEMA_VERSION},
    )


def _artifact_path(value: object, *, capture_dir: Path) -> Path:
    ref = required_text(value, "artifact.path")
    candidate = Path(ref)
    if candidate.is_absolute():
        raise invalid_manifest_source("Snapshot artifact path must be relative.")
    resolved = (capture_dir / candidate).resolve(strict=False)
    try:
        resolved.relative_to(capture_dir.resolve(strict=True))
    except ValueError as exc:
        raise invalid_manifest_source(
            "Snapshot artifact path escaped capture directory."
        ) from exc
    if not resolved.exists() or not resolved.is_file():
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_missing",
            detail="Snapshot artifact referenced by manifest is missing.",
        )
    return resolved


def _read_artifact_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_missing",
            detail="Snapshot artifact referenced by manifest could not be read.",
        ) from exc


def _artifact_metadata(
    payload: Mapping[object, object],
    *,
    name: str,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if name == "xml":
        node_count = payload.get("node_count")
        if isinstance(node_count, int) and not isinstance(node_count, bool):
            metadata["node_count"] = node_count
    if name == "screenshot":
        image_format = payload.get("format")
        if isinstance(image_format, str):
            metadata["format"] = image_format
        for key in ("width", "height"):
            value = payload.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                metadata[key] = value
    return metadata
