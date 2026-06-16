from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from snap_tap.snapshots.latest_types import (
    ALLOWED_LATEST_REF_NAMES,
    LATEST_SNAPSHOT_REF_SCHEMA_VERSION,
    LatestSnapshotRef,
    LatestSnapshotRefError,
    LatestSnapshotSource,
    invalid_latest_ref,
    latest_snapshot_cache_key,
    normalize_latest_snapshot_device_id,
    normalize_latest_snapshot_session_id,
)
from snap_tap.snapshots.models import SnapshotArtifactRef


def latest_snapshot_ref_to_dict(ref: LatestSnapshotRef) -> dict[str, object]:
    if ref.schema_version != LATEST_SNAPSHOT_REF_SCHEMA_VERSION:
        raise LatestSnapshotRefError(
            code="latest_snapshot_unsupported_version",
            detail="Latest snapshot ref version is unsupported.",
        )
    device_id = normalize_latest_snapshot_device_id(ref.device_id)
    session_id = normalize_latest_snapshot_session_id(ref.session_id)
    refs = validated_latest_refs(ref.refs)
    cache = validated_cache(
        ref.cache,
        device_id=device_id,
        session_id=session_id,
    )
    return {
        "schema_version": ref.schema_version,
        "device_id": device_id,
        "session_id": session_id,
        "updated_at": required_text(ref.updated_at, "updated_at"),
        "snapshot": {
            "snapshot_id": required_text(
                ref.snapshot.snapshot_id,
                "snapshot.snapshot_id",
            ),
            "snapshot_hash": required_text(
                ref.snapshot.snapshot_hash,
                "snapshot.snapshot_hash",
            ),
            "hash_version": required_text(
                ref.snapshot.hash_version,
                "snapshot.hash_version",
            ),
            "checked_at": required_text(
                ref.snapshot.checked_at,
                "snapshot.checked_at",
            ),
            "backend": required_text(ref.snapshot.backend, "snapshot.backend"),
            "operation": required_text(
                ref.snapshot.operation,
                "snapshot.operation",
            ),
        },
        "refs": {
            name: _snapshot_artifact_ref_to_dict(name, refs[name])
            for name in sorted(ALLOWED_LATEST_REF_NAMES)
        },
        "cache": cache,
    }


def latest_snapshot_ref_from_dict(payload: object) -> LatestSnapshotRef:
    if not isinstance(payload, Mapping):
        raise invalid_latest_ref("Latest snapshot ref must be a JSON object.")
    allowed_keys = {
        "schema_version",
        "device_id",
        "session_id",
        "updated_at",
        "snapshot",
        "refs",
        "cache",
    }
    if set(payload) != allowed_keys:
        raise invalid_latest_ref("Latest snapshot ref contains invalid fields.")
    version = payload.get("schema_version")
    if not isinstance(version, str):
        raise invalid_latest_ref("Latest snapshot ref schema version must be text.")
    if version != LATEST_SNAPSHOT_REF_SCHEMA_VERSION:
        raise LatestSnapshotRefError(
            code="latest_snapshot_unsupported_version",
            detail="Latest snapshot ref version is unsupported.",
        )

    snapshot = required_mapping(payload.get("snapshot"), "snapshot")
    device_id = normalize_latest_snapshot_device_id(payload.get("device_id"))
    session_id = normalize_latest_snapshot_session_id(payload.get("session_id"))
    return LatestSnapshotRef(
        schema_version=version,
        device_id=device_id,
        session_id=session_id,
        updated_at=required_text(payload.get("updated_at"), "updated_at"),
        snapshot=LatestSnapshotSource(
            snapshot_id=required_text(
                snapshot.get("snapshot_id"),
                "snapshot.snapshot_id",
            ),
            snapshot_hash=required_text(
                snapshot.get("snapshot_hash"),
                "snapshot.snapshot_hash",
            ),
            hash_version=required_text(
                snapshot.get("hash_version"),
                "snapshot.hash_version",
            ),
            checked_at=required_text(
                snapshot.get("checked_at"),
                "snapshot.checked_at",
            ),
            backend=required_text(snapshot.get("backend"), "snapshot.backend"),
            operation=required_text(
                snapshot.get("operation"),
                "snapshot.operation",
            ),
        ),
        refs=refs_from_payload(payload.get("refs")),
        cache=validated_cache(
            required_mapping(payload.get("cache"), "cache"),
            device_id=device_id,
            session_id=session_id,
        ),
    )


def validated_latest_refs(
    refs: Mapping[str, SnapshotArtifactRef],
) -> dict[str, SnapshotArtifactRef]:
    if set(refs) != ALLOWED_LATEST_REF_NAMES:
        raise invalid_latest_ref(
            "Latest snapshot ref requires xml, screenshot, and manifest refs."
        )
    return {
        name: _validated_artifact_ref(name, refs[name])
        for name in sorted(ALLOWED_LATEST_REF_NAMES)
    }


def refs_from_payload(payload: object) -> dict[str, SnapshotArtifactRef]:
    refs = required_mapping(payload, "refs")
    if set(refs) != ALLOWED_LATEST_REF_NAMES:
        raise invalid_latest_ref(
            "Latest snapshot ref requires xml, screenshot, and manifest refs."
        )
    return {
        name: _ref_from_payload(name, required_mapping(refs.get(name), f"refs.{name}"))
        for name in sorted(ALLOWED_LATEST_REF_NAMES)
    }


def validated_cache(
    cache: Mapping[Any, object],
    *,
    device_id: str,
    session_id: str,
) -> dict[str, object]:
    if set(cache) != {"key", "path"}:
        raise invalid_latest_ref("Latest snapshot cache metadata is invalid.")
    key = required_text(cache.get("key"), "cache.key")
    path = required_text(cache.get("path"), "cache.path")
    expected_key = latest_snapshot_cache_key(
        device_id=device_id,
        session_id=session_id,
    )
    if key != expected_key:
        raise invalid_latest_ref("Latest snapshot cache key is invalid.")
    return {"key": key, "path": path}


def required_mapping(value: object, field_name: str) -> Mapping[object, object]:
    if not isinstance(value, Mapping):
        raise invalid_latest_ref(f"{field_name} must be an object.")
    return value


def required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise invalid_latest_ref(f"{field_name} must be text.")
    normalized = value.strip()
    if not normalized:
        raise invalid_latest_ref(f"{field_name} must not be empty.")
    if normalized != value:
        raise invalid_latest_ref(f"{field_name} must already be normalized.")
    return normalized


def _validated_artifact_ref(
    name: str,
    ref: SnapshotArtifactRef,
) -> SnapshotArtifactRef:
    if not isinstance(ref, SnapshotArtifactRef):
        raise invalid_latest_ref(f"{name} ref is invalid.")
    return SnapshotArtifactRef(
        path=required_text(ref.path, f"refs.{name}.path"),
        sha256=required_text(ref.sha256, f"refs.{name}.sha256"),
        byte_length=_required_non_negative_int(
            ref.byte_length,
            f"refs.{name}.byte_length",
        ),
        metadata=_sanitized_ref_metadata(name, ref.metadata),
    )


def _ref_from_payload(
    name: str,
    payload: Mapping[object, object],
) -> SnapshotArtifactRef:
    allowed_keys = {"path", "sha256", "byte_length"}
    if name == "xml":
        allowed_keys.add("node_count")
    elif name == "screenshot":
        allowed_keys.update({"format", "width", "height"})
    elif name == "manifest":
        allowed_keys.add("metadata")
    if set(payload) - allowed_keys:
        raise invalid_latest_ref(f"{name} ref contains invalid fields.")

    metadata: dict[str, object] = {}
    if name == "xml":
        _add_int_metadata(metadata, payload, "node_count", "refs.xml.node_count")
    elif name == "screenshot":
        image_format = payload.get("format")
        if image_format is not None:
            metadata["format"] = required_text(
                image_format,
                "refs.screenshot.format",
            )
        _add_int_metadata(metadata, payload, "width", "refs.screenshot.width")
        _add_int_metadata(metadata, payload, "height", "refs.screenshot.height")
    elif name == "manifest" and payload.get("metadata") is not None:
        metadata = _manifest_metadata_from_payload(payload["metadata"])

    return SnapshotArtifactRef(
        path=required_text(payload.get("path"), f"refs.{name}.path"),
        sha256=required_text(payload.get("sha256"), f"refs.{name}.sha256"),
        byte_length=_required_non_negative_int(
            payload.get("byte_length"),
            f"refs.{name}.byte_length",
        ),
        metadata=metadata,
    )


def _snapshot_artifact_ref_to_dict(
    name: str,
    ref: SnapshotArtifactRef,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "path": ref.path,
        "sha256": ref.sha256,
        "byte_length": ref.byte_length,
    }
    metadata = _sanitized_ref_metadata(name, ref.metadata)
    if name == "xml":
        _copy_int_metadata(payload, metadata, "node_count")
    elif name == "screenshot":
        image_format = metadata.get("format")
        if isinstance(image_format, str):
            payload["format"] = image_format
        _copy_int_metadata(payload, metadata, "width")
        _copy_int_metadata(payload, metadata, "height")
    elif name == "manifest":
        schema_version = metadata.get("schema_version")
        if isinstance(schema_version, str):
            payload["metadata"] = {"schema_version": schema_version}
    return payload


def _sanitized_ref_metadata(
    name: str,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    public: dict[str, object] = {}
    if name == "xml":
        _copy_int_metadata(public, metadata, "node_count")
    elif name == "screenshot":
        image_format = metadata.get("format")
        if isinstance(image_format, str):
            public["format"] = image_format
        _copy_int_metadata(public, metadata, "width")
        _copy_int_metadata(public, metadata, "height")
    elif name == "manifest":
        schema_version = metadata.get("schema_version")
        if isinstance(schema_version, str):
            public["schema_version"] = schema_version
    return public


def _manifest_metadata_from_payload(value: object) -> dict[str, object]:
    metadata = required_mapping(value, "refs.manifest.metadata")
    if set(metadata) != {"schema_version"}:
        raise invalid_latest_ref("Manifest ref metadata contains invalid fields.")
    return {
        "schema_version": required_text(
            metadata.get("schema_version"),
            "refs.manifest.metadata.schema_version",
        )
    }


def _add_int_metadata(
    target: dict[str, object],
    source: Mapping[object, object],
    key: str,
    field_name: str,
) -> None:
    value = source.get(key)
    if value is not None:
        target[key] = _required_non_negative_int(value, field_name)


def _copy_int_metadata(
    target: dict[str, object],
    source: Mapping[str, object],
    key: str,
) -> None:
    value = source.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        target[key] = value


def _required_non_negative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise invalid_latest_ref(f"{field_name} must be a non-negative integer.")
    return value
