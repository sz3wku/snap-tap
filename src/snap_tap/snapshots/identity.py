from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import hashlib
import json

from snap_tap.snapshots.models import (
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotIdentity,
)


SNAPSHOT_HASH_VERSION = "raw_snapshot_hash.v1"


def build_snapshot_identity(
    result: RawSnapshotCapture,
) -> SnapshotIdentity | None:
    if result.device_id is None:
        return None
    try:
        payload = canonical_snapshot_payload(
            device_id=result.device_id,
            refs=result.refs,
        )
        snapshot_hash = snapshot_hash_from_payload(payload)
        snapshot_id = snapshot_id_from_parts(result.checked_at, snapshot_hash)
    except (KeyError, TypeError, ValueError):
        return None
    return SnapshotIdentity(
        snapshot_id=snapshot_id,
        snapshot_hash=snapshot_hash,
        hash_version=SNAPSHOT_HASH_VERSION,
    )


def canonical_snapshot_payload(
    *,
    device_id: str,
    refs: Mapping[str, SnapshotArtifactRef],
) -> dict[str, object]:
    xml = refs["xml"]
    screenshot = refs["screenshot"]
    xml_metadata = dict(xml.metadata)
    screenshot_metadata = dict(screenshot.metadata)
    return {
        "hash_version": SNAPSHOT_HASH_VERSION,
        "device_id": device_id,
        "artifacts": {
            "xml": {
                "sha256": _required_sha256(xml.sha256),
                "byte_length": _required_positive_int(xml.byte_length),
                "node_count": _required_nonnegative_int(
                    xml_metadata.get("node_count"),
                ),
            },
            "screenshot": {
                "sha256": _required_sha256(screenshot.sha256),
                "byte_length": _required_positive_int(screenshot.byte_length),
                "format": _required_format(screenshot_metadata.get("format")),
                "width": _required_positive_int(screenshot_metadata.get("width")),
                "height": _required_positive_int(screenshot_metadata.get("height")),
            },
        },
    }


def snapshot_hash_from_payload(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def snapshot_id_from_parts(checked_at: str, snapshot_hash: str) -> str:
    timestamp = _compact_timestamp(checked_at)
    digest = snapshot_hash.removeprefix("sha256:")
    return f"snap_{timestamp}_{digest[:12]}"


def _compact_timestamp(checked_at: str) -> str:
    parsed = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _required_sha256(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Artifact sha256 is required.")
    normalized = value.strip().lower()
    if len(normalized) != 64:
        raise ValueError("Artifact sha256 must be a 64-character hex digest.")
    int(normalized, 16)
    return normalized


def _required_positive_int(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("Expected positive int.")
    if not isinstance(value, int):
        raise TypeError("Expected positive int.")
    if value <= 0:
        raise ValueError("Expected positive int.")
    return value


def _required_nonnegative_int(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("Expected nonnegative int.")
    if not isinstance(value, int):
        raise TypeError("Expected nonnegative int.")
    if value < 0:
        raise ValueError("Expected nonnegative int.")
    return value


def _required_format(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Screenshot format is required.")
    normalized = value.strip().lower()
    if normalized != "png":
        raise ValueError("Screenshot format must be png.")
    return normalized
