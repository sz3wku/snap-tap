from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from snap_tap.snapshots import (
    DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT,
    DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    LatestSnapshotRefError,
)
from snap_tap.snapshots.latest_types import (
    latest_snapshot_cache_key,
    normalize_latest_snapshot_device_id,
    normalize_latest_snapshot_session_id,
)
from snap_tap.targets.latest_snap_source_models import (
    LatestSnapSource,
    LatestSnapSourceError,
)
from snap_tap.targets.latest_snap_source_payload import (
    encode_latest_snap_source,
    latest_snap_source_from_dict,
    latest_snap_source_to_dict,
    latest_snapshot_error_to_snap_source_error,
)


def latest_snap_source_path(
    *,
    device_id: object,
    session_id: object | None = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    cache_root: Path = DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT,
) -> Path:
    key = latest_snapshot_cache_key(device_id=device_id, session_id=session_id)
    return cache_root / "snap-source" / f"{key}.json"


def write_latest_snap_source(
    source: LatestSnapSource,
    *,
    cache_root: Path = DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT,
) -> LatestSnapSource:
    validated = latest_snap_source_from_dict(latest_snap_source_to_dict(source))
    path = latest_snap_source_path(
        device_id=validated.device_id,
        session_id=validated.session_id,
        cache_root=cache_root,
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_bytes_atomically(path, encode_latest_snap_source(validated))
    except OSError as exc:
        raise LatestSnapSourceError(
            code="latest_snap_source_write_failed",
            detail="Failed to write latest snap source.",
        ) from exc
    return validated


def read_latest_snap_source(
    *,
    device_id: object,
    session_id: object | None = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    cache_root: Path = DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT,
) -> LatestSnapSource:
    expected_device = normalize_latest_snapshot_device_id(device_id)
    expected_session = normalize_latest_snapshot_session_id(session_id)
    path = latest_snap_source_path(
        device_id=expected_device,
        session_id=expected_session,
        cache_root=cache_root,
    )
    if not path.exists():
        raise LatestSnapSourceError(
            code="latest_snap_source_missing",
            detail="Latest snap source is missing for device/session.",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LatestSnapSourceError(
            code="latest_snap_source_invalid",
            detail="Latest snap source JSON is missing or corrupt.",
        ) from exc
    try:
        source = latest_snap_source_from_dict(payload)
    except LatestSnapshotRefError as exc:
        raise LatestSnapSourceError(
            code="latest_snap_source_invalid",
            detail=latest_snapshot_error_to_snap_source_error(exc),
        ) from exc
    if source.device_id != expected_device:
        raise LatestSnapSourceError(
            code="latest_snap_source_device_mismatch",
            detail="Latest snap source device does not match requested device.",
        )
    if source.session_id != expected_session:
        raise LatestSnapSourceError(
            code="latest_snap_source_session_mismatch",
            detail="Latest snap source session does not match requested session.",
        )
    return source


def _write_bytes_atomically(path: Path, payload: bytes) -> None:
    temp_path = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        temp_path.write_bytes(payload)
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise
