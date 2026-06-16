from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from snap_tap.device.identity import normalize_serial
from snap_tap.snapshots.models import SnapshotArtifactRef

LATEST_SNAPSHOT_REF_SCHEMA_VERSION = "latest_snapshot_ref.v1"
DEFAULT_LATEST_SNAPSHOT_SESSION_ID = "default"
DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT = Path("data/cache/mobile/latest")

ALLOWED_LATEST_REF_NAMES = frozenset({"xml", "screenshot", "manifest"})
_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class LatestSnapshotSource:
    snapshot_id: str
    snapshot_hash: str
    hash_version: str
    checked_at: str
    backend: str
    operation: str


@dataclass(frozen=True)
class LatestSnapshotRef:
    schema_version: str
    device_id: str
    session_id: str
    updated_at: str
    snapshot: LatestSnapshotSource
    refs: Mapping[str, SnapshotArtifactRef]
    cache: Mapping[str, object] = field(default_factory=dict)


class LatestSnapshotRefError(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def normalize_latest_snapshot_device_id(device_id: object) -> str:
    normalized = normalize_serial(device_id)
    if normalized is None:
        raise LatestSnapshotRefError(
            code="latest_snapshot_ref_invalid",
            detail="Latest snapshot ref requires a valid device id.",
        )
    return normalized


def normalize_latest_snapshot_session_id(session_id: object | None) -> str:
    if session_id is None:
        return DEFAULT_LATEST_SNAPSHOT_SESSION_ID
    if not isinstance(session_id, str):
        raise _invalid_session()
    normalized = session_id.strip()
    if normalized != session_id or _SESSION_RE.fullmatch(normalized) is None:
        raise _invalid_session()
    if ".." in normalized:
        raise _invalid_session()
    return normalized


def latest_snapshot_cache_key(*, device_id: object, session_id: object | None) -> str:
    device = normalize_latest_snapshot_device_id(device_id)
    session = normalize_latest_snapshot_session_id(session_id)
    payload = json.dumps(
        {"device_id": device, "session_id": session},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


def latest_snapshot_ref_path(
    *,
    device_id: object,
    session_id: object | None = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    cache_root: Path = DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT,
) -> Path:
    key = latest_snapshot_cache_key(device_id=device_id, session_id=session_id)
    return cache_root / f"{key}.json"


def latest_snapshot_error_to_dict(
    error: LatestSnapshotRefError,
) -> dict[str, object]:
    return {"code": error.code, "detail": error.detail}


def cache_metadata(
    *,
    device_id: str,
    session_id: str,
    cache_root: Path,
) -> dict[str, object]:
    key = latest_snapshot_cache_key(device_id=device_id, session_id=session_id)
    return {
        "key": key,
        "path": str(cache_root / f"{key}.json"),
    }


def invalid_latest_ref(detail: str) -> LatestSnapshotRefError:
    return LatestSnapshotRefError(code="latest_snapshot_invalid", detail=detail)


def _invalid_session() -> LatestSnapshotRefError:
    return LatestSnapshotRefError(
        code="latest_snapshot_ref_invalid",
        detail="Latest snapshot session must be normalized path-safe text.",
    )
