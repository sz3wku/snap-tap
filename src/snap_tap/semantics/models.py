from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds

SEMANTIC_SNAPSHOT_SCHEMA_VERSION = "semantic_snapshot.v1"
SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION = "semantic_screen_metadata.v1"


class SemanticRole(Enum):
    BUTTON = "button"
    TAB = "tab"
    INPUT = "input"
    TEXT = "text"
    IMAGE = "image"
    LIST_ITEM = "list_item"
    UNKNOWN = "unknown"


class ViewportOrientation(Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    SQUARE = "square"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SemanticElement:
    source_index: int
    role: SemanticRole
    bounds: SnapshotBounds
    enabled: bool
    clickable: bool
    label: str | None
    label_source: str
    accessibility: Mapping[str, str] = field(default_factory=dict)
    class_name: str | None = None
    resource_id: str | None = None
    package: str | None = None
    scrollable: bool = False


@dataclass(frozen=True)
class SemanticViewport:
    orientation: ViewportOrientation
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class SemanticPackageSummary:
    package: str
    element_count: int
    visible_count: int
    semantic_count: int


@dataclass(frozen=True)
class SemanticScreenCounts:
    source_element_count: int
    visible_element_count: int
    semantic_element_count: int
    enabled_count: int
    clickable_count: int
    actionable_count: int
    labeled_count: int
    unknown_count: int
    scrollable_count: int = 0


@dataclass(frozen=True)
class SemanticScreenMetadata:
    schema_version: str
    viewport: SemanticViewport
    counts: SemanticScreenCounts
    packages: Sequence[SemanticPackageSummary] = field(default_factory=tuple)
    dominant_package: str | None = None


@dataclass(frozen=True)
class SemanticRoleNormalization:
    source_schema_version: str
    source_element_count: int
    visible_element_count: int
    semantic_element_count: int
    role_counts: Mapping[str, int]
    unknown_count: int
    labeled_count: int
    accessibility_field_counts: Mapping[str, int]


@dataclass(frozen=True)
class SemanticSnapshot:
    schema_version: str
    snapshot_id: str
    device_id: str
    captured_at: str
    screen_metadata: SemanticScreenMetadata
    refs: Mapping[str, SnapshotArtifactRef] = field(default_factory=dict)
    elements: Sequence[SemanticElement] = field(default_factory=tuple)
    role_normalization: SemanticRoleNormalization | None = None


class SemanticSnapshotError(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
