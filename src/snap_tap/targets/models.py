from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from snap_tap.backends.contracts import DriverError
from snap_tap.semantics import SemanticRole
from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds


SNAPSHOT_TARGETS_SCHEMA_VERSION = "snapshot_targets.v1"
TARGET_SIGNATURE_SCHEMA_VERSION = "target_signature.v1"
TARGET_RESOLUTION_SCHEMA_VERSION = "target_resolution.v1"
MOBILE_SNAP_SCHEMA_VERSION = "mobile_snap.v1"


class MobileSnapKind(Enum):
    INPUT = "input"
    TAP = "tap"
    SCROLL = "scroll"
    TEXT = "text"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SnapshotTarget:
    display_id: str
    snapshot_id: str
    semantic_index: int
    source_index: int
    role: SemanticRole
    bounds: SnapshotBounds
    enabled: bool
    clickable: bool
    actionable: bool
    label: str | None
    label_source: str
    class_name: str | None = None
    resource_id: str | None = None
    package: str | None = None
    scrollable: bool = False


@dataclass(frozen=True)
class SnapshotTargetSummary:
    target_count: int
    actionable_count: int
    disabled_count: int
    non_clickable_count: int
    labeled_count: int
    source_element_count: int
    scrollable_count: int = 0


@dataclass(frozen=True)
class SnapshotTargets:
    schema_version: str
    snapshot_id: str
    device_id: str
    captured_at: str
    source_schema_version: str
    refs: Mapping[str, SnapshotArtifactRef] = field(default_factory=dict)
    targets: Sequence[SnapshotTarget] = field(default_factory=tuple)
    summary: SnapshotTargetSummary | None = None


class SnapshotTargetsError(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class MobileSnapOperatorLabelCandidate:
    id: str
    label: str
    label_source: str
    role: SemanticRole
    source_index: int
    semantic_index: int
    bounds: SnapshotBounds


@dataclass(frozen=True)
class MobileSnapTarget:
    id: str
    kind: MobileSnapKind
    role: SemanticRole
    label: str | None
    enabled: bool
    clickable: bool
    scrollable: bool
    actionable: bool
    center_x: float
    center_y: float
    bounds: SnapshotBounds
    package: str | None
    source_index: int
    semantic_index: int
    class_name: str | None = None
    resource_id: str | None = None
    label_source: str | None = None
    snapshot_id: str | None = None
    operator_label: str | None = None
    operator_label_source: str | None = None
    operator_label_confidence: str | None = None
    operator_label_candidates: Sequence[MobileSnapOperatorLabelCandidate] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class MobileSnap:
    ok: bool
    status: str
    device_id: str | None
    session_id: str
    captured_at: str
    app: Mapping[str, object]
    viewport: Mapping[str, object]
    summary: Mapping[str, int]
    snapshot: Mapping[str, object]
    targets: Sequence[MobileSnapTarget] = field(default_factory=tuple)
    error: DriverError | None = None
    schema_version: str = MOBILE_SNAP_SCHEMA_VERSION


@dataclass(frozen=True)
class TargetSignatureRequirements:
    requires_fresh_snapshot: bool = True
    requires_resolution: bool = True
    not_executable_directly: bool = True


@dataclass(frozen=True)
class TargetSignature:
    schema_version: str
    signature_id: str
    source_snapshot_id: str
    device_id: str
    captured_at: str
    display_id: str
    semantic_index: int
    source_index: int
    role: SemanticRole
    identity: Mapping[str, str]
    source_bounds: SnapshotBounds
    requirements: TargetSignatureRequirements = field(
        default_factory=TargetSignatureRequirements
    )
    identity_strength: str = "weak"
    refs: Mapping[str, SnapshotArtifactRef] = field(default_factory=dict)


class TargetSignatureError(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class TargetResolutionMatch:
    identity_strength: str
    matched_fields: Sequence[str]
    candidate_count: int


@dataclass(frozen=True)
class TargetResolutionBlockingReason:
    code: str
    detail: str
    touched_phone: bool = False


@dataclass(frozen=True)
class TargetResolution:
    schema_version: str
    ok: bool
    status: str
    signature_id: str
    source_snapshot_id: str
    resolved_snapshot_id: str
    device_id: str
    match: TargetResolutionMatch
    refs: Mapping[str, SnapshotArtifactRef] = field(default_factory=dict)
    resolved_target: SnapshotTarget | None = None
    blocking_reason: TargetResolutionBlockingReason | None = None


class TargetResolutionError(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
