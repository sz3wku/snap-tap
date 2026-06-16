from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from snap_tap.semantics import SemanticRole
from snap_tap.snapshots import SnapshotBounds
from snap_tap.targets.models import MobileSnapKind


LATEST_SNAP_SOURCE_SCHEMA_VERSION = "latest_snap_source.v1"
TAPPABLE_ROLES = frozenset(
    {SemanticRole.BUTTON, SemanticRole.TAB, SemanticRole.LIST_ITEM}
)


@dataclass(frozen=True)
class LatestSnapSourceSnapshot:
    snapshot_id: str
    captured_at: str
    source_schema_version: str


@dataclass(frozen=True)
class LatestSnapSourceTarget:
    display_id: str
    snapshot_id: str
    semantic_index: int
    source_index: int
    role: SemanticRole
    kind: MobileSnapKind
    bounds: SnapshotBounds
    enabled: bool
    clickable: bool
    scrollable: bool
    actionable: bool
    label: str | None
    label_source: str
    class_name: str | None = None
    resource_id: str | None = None
    package: str | None = None


@dataclass(frozen=True)
class LatestSnapSource:
    schema_version: str
    device_id: str
    session_id: str
    updated_at: str
    snapshot: LatestSnapSourceSnapshot
    targets: Sequence[LatestSnapSourceTarget] = field(default_factory=tuple)


class LatestSnapSourceError(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def invalid_latest_snap_source(detail: str) -> LatestSnapSourceError:
    return LatestSnapSourceError(code="latest_snap_source_invalid", detail=detail)


def unsupported_latest_snap_source() -> LatestSnapSourceError:
    return LatestSnapSourceError(
        code="latest_snap_source_unsupported_version",
        detail="Latest snap source version is unsupported.",
    )


def latest_snap_source_error_to_dict(
    error: LatestSnapSourceError,
) -> Mapping[str, object]:
    return {"code": error.code, "detail": error.detail}
