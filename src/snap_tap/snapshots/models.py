from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from snap_tap.backends.contracts import DriverError


@dataclass(frozen=True)
class SnapshotArtifactRef:
    path: str
    sha256: str
    byte_length: int
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SnapshotIdentity:
    snapshot_id: str
    snapshot_hash: str
    hash_version: str


@dataclass(frozen=True)
class SnapshotBounds:
    left: int
    top: int
    right: int
    bottom: int
    width: int
    height: int
    center_x: float
    center_y: float


@dataclass(frozen=True)
class SnapshotElement:
    source_index: int
    depth: int
    bounds: SnapshotBounds
    visible: bool
    enabled: bool
    clickable: bool
    scrollable: bool = False
    class_name: str | None = None
    resource_id: str | None = None
    package: str | None = None
    text: str | None = None
    content_desc: str | None = None
    hint: str | None = None


@dataclass(frozen=True)
class SnapshotNormalization:
    schema_version: str
    status: str
    source_node_count: int
    element_count: int
    visible_count: int
    enabled_count: int
    clickable_count: int
    discarded_count: int
    invalid_bounds_count: int
    viewport_width: int | None = None
    viewport_height: int | None = None
    scrollable_count: int = 0


@dataclass(frozen=True)
class RawSnapshotCapture:
    ok: bool
    status: str
    device_id: str | None
    backend: str
    operation: str
    checked_at: str
    elapsed_ms: float
    refs: Mapping[str, SnapshotArtifactRef] = field(default_factory=dict)
    identity: SnapshotIdentity | None = None
    elements: Sequence[SnapshotElement] = field(default_factory=tuple)
    normalization: SnapshotNormalization | None = None
    xml: str | None = None
    image_bytes: bytes | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: DriverError | None = None

    @classmethod
    def success(
        cls,
        *,
        device_id: str,
        backend: str,
        elapsed_ms: float,
        xml: str,
        image_bytes: bytes,
        metadata: Mapping[str, object] | None = None,
    ) -> RawSnapshotCapture:
        return cls(
            ok=True,
            status="completed",
            device_id=device_id,
            backend=backend,
            operation="snapshot_capture",
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            xml=xml,
            image_bytes=image_bytes,
            metadata=metadata or {},
        )

    @classmethod
    def failure(
        cls,
        *,
        backend: str,
        code: str,
        detail: str,
        elapsed_ms: float,
        device_id: str | None = None,
        status: str = "unhealthy",
        metadata: Mapping[str, object] | None = None,
        elements: Sequence[SnapshotElement] = (),
        normalization: SnapshotNormalization | None = None,
    ) -> RawSnapshotCapture:
        return cls(
            ok=False,
            status=status,
            device_id=device_id,
            backend=backend,
            operation="snapshot_capture",
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            metadata=metadata or {},
            error=DriverError(code=code, detail=detail),
            elements=tuple(elements),
            normalization=normalization,
        )

    def with_refs(
        self,
        refs: Mapping[str, SnapshotArtifactRef],
    ) -> RawSnapshotCapture:
        return replace(self, refs=dict(refs), identity=None, xml=None, image_bytes=None)

    def with_ref(
        self,
        name: str,
        ref: SnapshotArtifactRef,
    ) -> RawSnapshotCapture:
        return replace(
            self,
            refs={**self.refs, name: ref},
            xml=None,
            image_bytes=None,
        )

    def with_identity(self, identity: SnapshotIdentity) -> RawSnapshotCapture:
        return replace(self, identity=identity)

    def with_elements(
        self,
        *,
        elements: Sequence[SnapshotElement],
        normalization: SnapshotNormalization,
    ) -> RawSnapshotCapture:
        return replace(
            self,
            elements=tuple(elements),
            normalization=normalization,
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
