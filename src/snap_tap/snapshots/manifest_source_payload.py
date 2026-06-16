from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from snap_tap.device.identity import normalize_serial
from snap_tap.snapshots.identity import build_snapshot_identity
from snap_tap.snapshots.manifest import SNAPSHOT_MANIFEST_SCHEMA_VERSION
from snap_tap.snapshots.manifest_source_artifacts import (
    artifact_payload,
    artifact_ref,
    manifest_ref,
)
from snap_tap.snapshots.manifest_source_common import (
    mapping,
    number,
    reject_json_constant,
    required_text,
)
from snap_tap.snapshots.manifest_source_elements import verified_manifest_elements
from snap_tap.snapshots.manifest_source_types import (
    SnapshotManifestSourceError,
    invalid_manifest_source,
)
from snap_tap.snapshots.models import RawSnapshotCapture, SnapshotIdentity


def read_snapshot_manifest_raw(
    source: Path,
    *,
    expected_device_id: str | None = None,
) -> tuple[Path, Path, RawSnapshotCapture]:
    manifest_path = _manifest_path(source)
    capture_dir = manifest_path.parent
    payload = _read_manifest_json(manifest_path)
    _validate_manifest_envelope(payload)

    device = mapping(payload["device"], "device")
    device_id = _device_id(device.get("device_id"))
    if expected_device_id is not None:
        expected = normalize_serial(expected_device_id)
        if expected is None or device_id != expected:
            raise SnapshotManifestSourceError(
                code="explicit_snapshot_source_device_mismatch",
                detail="Snapshot manifest device does not match --device.",
            )

    artifacts = mapping(payload["artifacts"], "artifacts")
    xml_ref = artifact_ref(
        artifact_payload(artifacts, "xml"),
        capture_dir=capture_dir,
        name="xml",
    )
    screenshot_ref = artifact_ref(
        artifact_payload(artifacts, "screenshot"),
        capture_dir=capture_dir,
        name="screenshot",
    )
    elements, normalization = verified_manifest_elements(
        normalization_payload=payload["normalization"],
        elements_payload=payload["elements"],
        xml_ref=xml_ref,
        screenshot_ref=screenshot_ref,
    )
    raw = RawSnapshotCapture(
        ok=True,
        status="completed",
        device_id=device_id,
        backend=required_text(device.get("backend"), "device.backend"),
        operation=_operation_name(payload["operation"]),
        checked_at=_operation_checked_at(payload["operation"]),
        elapsed_ms=_operation_elapsed_ms(payload["operation"]),
        refs={
            "xml": xml_ref,
            "screenshot": screenshot_ref,
            "manifest": manifest_ref(manifest_path),
        },
        identity=_identity(payload["snapshot"]),
        elements=elements,
        normalization=normalization,
        xml=None,
        image_bytes=None,
        metadata={},
        error=None,
    )
    _verify_snapshot_identity(raw)
    return manifest_path, capture_dir, raw


def _manifest_path(source: Path) -> Path:
    path = source.expanduser()
    if path.is_dir():
        path = path / "manifest.json"
    if not path.exists():
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_missing",
            detail="Snapshot source path does not exist.",
        )
    if not path.is_file():
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_invalid",
            detail="Snapshot source must be a manifest.json file or capture directory.",
        )
    if path.name != "manifest.json":
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_invalid",
            detail="Snapshot source file must be named manifest.json.",
        )
    return path.resolve(strict=True)


def _read_manifest_json(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_json_constant,
        )
    except ValueError as exc:
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_invalid",
            detail="Snapshot manifest is not valid JSON.",
        ) from exc
    except OSError as exc:
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_missing",
            detail="Snapshot manifest could not be read.",
        ) from exc
    return cast(Mapping[str, object], mapping(payload, "manifest"))


def _validate_manifest_envelope(payload: Mapping[str, object]) -> None:
    allowed = {
        "schema_version",
        "ok",
        "status",
        "snapshot",
        "device",
        "operation",
        "artifacts",
        "normalization",
        "elements",
        "metadata",
        "recovery",
    }
    if set(payload) - allowed:
        raise invalid_manifest_source("Snapshot manifest contains invalid fields.")
    if payload.get("schema_version") != SNAPSHOT_MANIFEST_SCHEMA_VERSION:
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_unsupported_version",
            detail="Snapshot source must use snapshot_manifest.v1.",
        )
    if payload.get("ok") is not True or payload.get("status") != "completed":
        raise invalid_manifest_source(
            "Snapshot manifest is not a completed successful capture."
        )
    for field in ("snapshot", "device", "operation", "artifacts", "normalization"):
        mapping(payload.get(field), field)
    elements = payload.get("elements")
    if not isinstance(elements, Sequence) or isinstance(elements, (str, bytes)):
        raise invalid_manifest_source("Snapshot manifest elements must be a list.")


def _identity(value: object) -> SnapshotIdentity:
    payload = mapping(value, "snapshot")
    return SnapshotIdentity(
        snapshot_id=required_text(payload.get("snapshot_id"), "snapshot.snapshot_id"),
        snapshot_hash=required_text(
            payload.get("snapshot_hash"),
            "snapshot.snapshot_hash",
        ),
        hash_version=required_text(payload.get("hash_version"), "snapshot.hash_version"),
    )


def _verify_snapshot_identity(raw: RawSnapshotCapture) -> None:
    expected = build_snapshot_identity(raw)
    if expected is None or raw.identity is None:
        raise invalid_manifest_source("Snapshot manifest identity could not be verified.")
    if (
        raw.identity.snapshot_id != expected.snapshot_id
        or raw.identity.snapshot_hash != expected.snapshot_hash
        or raw.identity.hash_version != expected.hash_version
    ):
        raise invalid_manifest_source(
            "Snapshot manifest identity does not match artifact refs."
        )


def _operation_name(value: object) -> str:
    return required_text(mapping(value, "operation").get("name"), "operation.name")


def _operation_checked_at(value: object) -> str:
    return required_text(
        mapping(value, "operation").get("checked_at"),
        "operation.checked_at",
    )


def _operation_elapsed_ms(value: object) -> float:
    return number(mapping(value, "operation").get("elapsed_ms"), "operation.elapsed_ms")


def _device_id(value: object) -> str:
    normalized = normalize_serial(value)
    if normalized is None:
        raise invalid_manifest_source("Snapshot manifest requires a valid device id.")
    return normalized


__all__ = ["read_snapshot_manifest_raw"]
