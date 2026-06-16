from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from snap_tap.snapshots.elements import (
    SnapshotNormalizationError,
    normalize_snapshot_elements,
)
from snap_tap.snapshots.identity import build_snapshot_identity
from snap_tap.snapshots.manifest import (
    SNAPSHOT_MANIFEST_SCHEMA_VERSION,
    SnapshotManifestError,
    build_snapshot_manifest,
    encode_snapshot_manifest,
)
from snap_tap.snapshots.models import RawSnapshotCapture, SnapshotArtifactRef


def materialize_raw_snapshot_artifacts(
    result: RawSnapshotCapture,
    out_dir: Path,
) -> RawSnapshotCapture:
    if result.xml is None or result.image_bytes is None:
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code="snapshot_evidence_missing",
            detail="Snapshot capture completed without raw artifact payloads.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
        )

    target_dir: Path | None = None
    xml_bytes = result.xml.encode("utf-8")
    screenshot_bytes = result.image_bytes

    try:
        target_dir = _reserve_artifact_dir(out_dir.expanduser())
        xml_path = target_dir / "screen.xml"
        screenshot_path = target_dir / "screen.png"
        _write_bytes_atomically(xml_path, xml_bytes)
        _write_bytes_atomically(screenshot_path, screenshot_bytes)
    except OSError:
        if target_dir is not None:
            shutil.rmtree(target_dir, ignore_errors=True)
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code="snapshot_evidence_missing",
            detail="Failed to write raw snapshot artifacts.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
        )

    materialized = result.with_refs(
        {
            "xml": SnapshotArtifactRef(
                path=str(xml_path),
                sha256=_sha256(xml_bytes),
                byte_length=len(xml_bytes),
                metadata={"node_count": result.xml.count("<node")},
            ),
            "screenshot": SnapshotArtifactRef(
                path=str(screenshot_path),
                sha256=_sha256(screenshot_bytes),
                byte_length=len(screenshot_bytes),
                metadata=_screenshot_ref_metadata(result.metadata),
            ),
        }
    )
    identity = build_snapshot_identity(materialized)
    if identity is None:
        shutil.rmtree(target_dir, ignore_errors=True)
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code="snapshot_evidence_missing",
            detail="Failed to build raw snapshot identity.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
        )
    try:
        elements, normalization = normalize_snapshot_elements(
            xml=result.xml,
            viewport_width=result.metadata.get("screenshot_width"),
            viewport_height=result.metadata.get("screenshot_height"),
        )
    except SnapshotNormalizationError as exc:
        shutil.rmtree(target_dir, ignore_errors=True)
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code=exc.code,
            detail=exc.detail,
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
            normalization=exc.normalization,
        )
    completed = materialized.with_identity(identity).with_elements(
        elements=elements,
        normalization=normalization,
    )
    try:
        manifest_path = target_dir / "manifest.json"
        manifest_bytes = encode_snapshot_manifest(
            build_snapshot_manifest(completed, capture_dir=target_dir)
        )
        manifest_sha256 = _sha256(manifest_bytes)
        _write_bytes_atomically(manifest_path, manifest_bytes)
    except (OSError, SnapshotManifestError):
        shutil.rmtree(target_dir, ignore_errors=True)
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code="snapshot_evidence_missing",
            detail="Failed to write snapshot manifest.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
        )
    return completed.with_ref(
        "manifest",
        SnapshotArtifactRef(
            path=str(manifest_path),
            sha256=manifest_sha256,
            byte_length=len(manifest_bytes),
            metadata={"schema_version": SNAPSHOT_MANIFEST_SCHEMA_VERSION},
        ),
    )


def _screenshot_ref_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    public: dict[str, object] = {}
    image_format = metadata.get("screenshot_format")
    if isinstance(image_format, str):
        public["format"] = image_format
    width = metadata.get("screenshot_width")
    if isinstance(width, int) and not isinstance(width, bool):
        public["width"] = width
    height = metadata.get("screenshot_height")
    if isinstance(height, int) and not isinstance(height, bool):
        public["height"] = height
    return public


def _reserve_artifact_dir(parent: Path) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        candidate = parent / _artifact_dir_name()
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise OSError("Failed to reserve a unique snapshot artifact directory.")


def _artifact_dir_name() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"capture-{timestamp}-{uuid4().hex[:8]}"


def _write_bytes_atomically(path: Path, payload: bytes) -> None:
    temp_path = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        temp_path.write_bytes(payload)
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
