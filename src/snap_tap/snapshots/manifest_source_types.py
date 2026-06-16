from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from snap_tap.snapshots.models import RawSnapshotCapture
from snap_tap.targets.models import MobileSnap, SnapshotTargets


@dataclass(frozen=True)
class SnapshotManifestSource:
    manifest_path: Path
    capture_dir: Path
    raw: RawSnapshotCapture
    snap: MobileSnap
    targets: SnapshotTargets


class SnapshotManifestSourceError(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def invalid_manifest_source(detail: str) -> SnapshotManifestSourceError:
    return SnapshotManifestSourceError(
        code="explicit_snapshot_source_invalid",
        detail=detail,
    )


__all__ = [
    "SnapshotManifestSource",
    "SnapshotManifestSourceError",
    "invalid_manifest_source",
]
