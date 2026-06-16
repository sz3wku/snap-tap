from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from uuid import uuid4

from snap_tap.snapshots._latest_payload import (
    latest_snapshot_ref_from_dict,
    latest_snapshot_ref_to_dict,
    required_text,
    validated_latest_refs,
)
from snap_tap.snapshots.latest_types import (
    DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT,
    DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    LATEST_SNAPSHOT_REF_SCHEMA_VERSION,
    LatestSnapshotRef,
    LatestSnapshotRefError,
    LatestSnapshotSource,
    cache_metadata,
    latest_snapshot_cache_key,
    latest_snapshot_error_to_dict,
    latest_snapshot_ref_path,
    normalize_latest_snapshot_device_id,
    normalize_latest_snapshot_session_id,
)
from snap_tap.snapshots.models import RawSnapshotCapture


def build_latest_snapshot_ref(
    result: RawSnapshotCapture,
    *,
    session_id: object | None = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    cache_root: Path = DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT,
) -> LatestSnapshotRef:
    if not result.ok:
        raise LatestSnapshotRefError(
            code="latest_snapshot_ref_invalid",
            detail="Latest snapshot ref requires a successful snapshot capture.",
        )
    device_id = normalize_latest_snapshot_device_id(result.device_id)
    session = normalize_latest_snapshot_session_id(session_id)
    if result.identity is None:
        raise LatestSnapshotRefError(
            code="latest_snapshot_ref_invalid",
            detail="Latest snapshot ref requires snapshot identity.",
        )
    return LatestSnapshotRef(
        schema_version=LATEST_SNAPSHOT_REF_SCHEMA_VERSION,
        device_id=device_id,
        session_id=session,
        updated_at=_utc_now(),
        snapshot=LatestSnapshotSource(
            snapshot_id=required_text(
                result.identity.snapshot_id,
                "snapshot.snapshot_id",
            ),
            snapshot_hash=required_text(
                result.identity.snapshot_hash,
                "snapshot.snapshot_hash",
            ),
            hash_version=required_text(
                result.identity.hash_version,
                "snapshot.hash_version",
            ),
            checked_at=required_text(result.checked_at, "snapshot.checked_at"),
            backend=required_text(result.backend, "snapshot.backend"),
            operation=required_text(result.operation, "snapshot.operation"),
        ),
        refs=validated_latest_refs(result.refs),
        cache=cache_metadata(
            device_id=device_id,
            session_id=session,
            cache_root=cache_root,
        ),
    )


def write_latest_snapshot_ref(
    ref: LatestSnapshotRef,
    *,
    cache_root: Path = DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT,
) -> LatestSnapshotRef:
    validated = latest_snapshot_ref_from_dict(latest_snapshot_ref_to_dict(ref))
    with_cache = replace(
        validated,
        cache=cache_metadata(
            device_id=validated.device_id,
            session_id=validated.session_id,
            cache_root=cache_root,
        ),
    )
    path = latest_snapshot_ref_path(
        device_id=with_cache.device_id,
        session_id=with_cache.session_id,
        cache_root=cache_root,
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_bytes_atomically(path, encode_latest_snapshot_ref(with_cache))
    except OSError as exc:
        raise LatestSnapshotRefError(
            code="latest_snapshot_write_failed",
            detail="Failed to write latest snapshot ref.",
        ) from exc
    return with_cache


def read_latest_snapshot_ref(
    *,
    device_id: object,
    session_id: object | None = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    cache_root: Path = DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT,
) -> LatestSnapshotRef:
    expected_device = normalize_latest_snapshot_device_id(device_id)
    expected_session = normalize_latest_snapshot_session_id(session_id)
    path = latest_snapshot_ref_path(
        device_id=expected_device,
        session_id=expected_session,
        cache_root=cache_root,
    )
    if not path.exists():
        raise LatestSnapshotRefError(
            code="latest_snapshot_missing",
            detail="Latest snapshot ref is missing for device/session.",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LatestSnapshotRefError(
            code="latest_snapshot_invalid",
            detail="Latest snapshot ref JSON is missing or corrupt.",
        ) from exc
    ref = latest_snapshot_ref_from_dict(payload)
    if ref.device_id != expected_device:
        raise LatestSnapshotRefError(
            code="latest_snapshot_device_mismatch",
            detail="Latest snapshot ref device does not match requested device.",
        )
    if ref.session_id != expected_session:
        raise LatestSnapshotRefError(
            code="latest_snapshot_session_mismatch",
            detail="Latest snapshot ref session does not match requested session.",
        )
    expected_cache = cache_metadata(
        device_id=expected_device,
        session_id=expected_session,
        cache_root=cache_root,
    )
    if dict(ref.cache) != expected_cache:
        raise LatestSnapshotRefError(
            code="latest_snapshot_invalid",
            detail="Latest snapshot ref cache metadata is invalid.",
        )
    return ref


def encode_latest_snapshot_ref(ref: LatestSnapshotRef) -> bytes:
    return (
        json.dumps(
            latest_snapshot_ref_to_dict(ref),
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def _write_bytes_atomically(path: Path, payload: bytes) -> None:
    temp_path = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        temp_path.write_bytes(payload)
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT",
    "DEFAULT_LATEST_SNAPSHOT_SESSION_ID",
    "LATEST_SNAPSHOT_REF_SCHEMA_VERSION",
    "LatestSnapshotRef",
    "LatestSnapshotRefError",
    "LatestSnapshotSource",
    "build_latest_snapshot_ref",
    "encode_latest_snapshot_ref",
    "latest_snapshot_cache_key",
    "latest_snapshot_error_to_dict",
    "latest_snapshot_ref_from_dict",
    "latest_snapshot_ref_path",
    "latest_snapshot_ref_to_dict",
    "normalize_latest_snapshot_device_id",
    "normalize_latest_snapshot_session_id",
    "read_latest_snapshot_ref",
    "write_latest_snapshot_ref",
]
