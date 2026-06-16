from __future__ import annotations

from pathlib import Path

from snap_tap.backends.contracts import DriverError
from snap_tap.semantics import SemanticSnapshotError, build_semantic_snapshot
from snap_tap.snapshots.manifest_source_payload import read_snapshot_manifest_raw
from snap_tap.snapshots.manifest_source_types import (
    SnapshotManifestSource,
    SnapshotManifestSourceError,
)
from snap_tap.targets.mobile_snap import build_mobile_snap
from snap_tap.targets.models import SnapshotTargetsError
from snap_tap.targets.snapshot import build_snapshot_targets


def read_snapshot_manifest_source(
    source: Path,
    *,
    expected_device_id: str | None = None,
    session_id: str = "default",
) -> SnapshotManifestSource:
    manifest_path, capture_dir, raw = read_snapshot_manifest_raw(
        source,
        expected_device_id=expected_device_id,
    )
    try:
        semantic = build_semantic_snapshot(raw)
        targets = build_snapshot_targets(semantic)
        snap = build_mobile_snap(raw, app_current=None, session_id=session_id)
    except (SemanticSnapshotError, SnapshotTargetsError) as exc:
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_invalid",
            detail="Snapshot manifest could not reconstruct snap-tap targets.",
        ) from exc

    if not snap.ok:
        error = snap.error or DriverError(
            code="explicit_snapshot_source_invalid",
            detail="Snapshot manifest source could not produce mobile_snap.v1.",
        )
        raise SnapshotManifestSourceError(code=error.code, detail=error.detail)

    return SnapshotManifestSource(
        manifest_path=manifest_path,
        capture_dir=capture_dir,
        raw=raw,
        snap=snap,
        targets=targets,
    )


__all__ = [
    "SnapshotManifestSource",
    "SnapshotManifestSourceError",
    "read_snapshot_manifest_source",
]
