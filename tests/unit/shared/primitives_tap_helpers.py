from __future__ import annotations

from snap_tap.backends.contracts import DriverError, DriverTap
from snap_tap.primitives import PrimitiveSnapshotResult, PrimitiveTapRequest
from snap_tap.primitives.receipt import utc_now
from snap_tap.semantics import (
    SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
    SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
    SemanticElement,
    SemanticRole,
    SemanticScreenCounts,
    SemanticScreenMetadata,
    SemanticSnapshot,
    SemanticViewport,
    ViewportOrientation,
)
from snap_tap.snapshots import SnapshotArtifactRef, SnapshotBounds
from snap_tap.targets import build_snapshot_targets, build_target_signature


class FakeSnapshotProvider:
    def __init__(self, results: list[PrimitiveSnapshotResult]) -> None:
        self.results = results
        self.calls: list[str] = []

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        self.calls.append(device_id)
        return self.results.pop(0)


class FakeTapper:
    backend_name = "fake"

    def __init__(self, result: DriverTap | None) -> None:
        self.result = result
        self.calls: list[tuple[str, float, float]] = []

    def tap(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        timeout_s: float = 10.0,
    ) -> DriverTap:
        self.calls.append((device_id, x, y))
        assert self.result is not None
        return self.result


class RaisingSnapshotProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        self.calls.append(device_id)
        raise RuntimeError("snapshot exploded")


class RaisingTapper:
    backend_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, float, float]] = []

    def tap(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        timeout_s: float = 10.0,
    ) -> DriverTap:
        self.calls.append((device_id, x, y))
        raise RuntimeError("tap exploded")


def fake_tap_request(
    *,
    role: SemanticRole = SemanticRole.BUTTON,
    clickable: bool = True,
) -> PrimitiveTapRequest:
    source = build_snapshot_targets(
        fake_tap_snapshot("source", role=role, clickable=clickable)
    )
    signature = build_target_signature(source, "e001")
    return PrimitiveTapRequest(device_id="RFCN4010FCK", signature=signature)


def fake_tap_snapshot_result(
    snapshot_id: str,
    *,
    role: SemanticRole = SemanticRole.BUTTON,
    clickable: bool = True,
    bounds: SnapshotBounds | None = None,
) -> PrimitiveSnapshotResult:
    snapshot = fake_tap_snapshot(
        snapshot_id,
        role=role,
        clickable=clickable,
        bounds=bounds,
    )
    return PrimitiveSnapshotResult(
        ok=True,
        status="completed",
        device_id=snapshot.device_id,
        checked_at=snapshot.captured_at,
        elapsed_ms=1.0,
        snapshot=snapshot,
    )


def fake_tap_snapshot(
    snapshot_id: str,
    *,
    role: SemanticRole = SemanticRole.BUTTON,
    clickable: bool = True,
    bounds: SnapshotBounds | None = None,
) -> SemanticSnapshot:
    is_input = role is SemanticRole.INPUT
    element = SemanticElement(
        source_index=7,
        role=role,
        bounds=bounds or SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        enabled=True,
        clickable=clickable,
        scrollable=False,
        label="Message" if is_input else "Save",
        label_source="hint" if is_input else "content_desc",
        class_name="android.widget.EditText" if is_input else "android.widget.Button",
        resource_id="com.example:id/message" if is_input else "com.example:id/save",
        package="com.example",
    )
    return SemanticSnapshot(
        schema_version=SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        device_id="RFCN4010FCK",
        captured_at="2026-06-14T10:00:00+00:00",
        refs={
            "xml": SnapshotArtifactRef(
                path="screen.xml",
                sha256="xml-sha",
                byte_length=123,
                metadata={"node_count": 1},
            )
        },
        elements=(element,),
        screen_metadata=SemanticScreenMetadata(
            schema_version=SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
            viewport=SemanticViewport(
                orientation=ViewportOrientation.PORTRAIT,
                width=1080,
                height=2400,
            ),
            counts=SemanticScreenCounts(
                source_element_count=1,
                visible_element_count=1,
                semantic_element_count=1,
                enabled_count=1,
                clickable_count=1 if clickable else 0,
                actionable_count=1 if clickable else 0,
                labeled_count=1,
                unknown_count=0,
            ),
        ),
    )


def fake_driver_tap_result(
    *,
    ok: bool = True,
    attempted: bool = True,
    confirmed: bool = True,
    error: DriverError | None = None,
) -> DriverTap:
    metadata = (
        {"touch_may_have_occurred": True}
        if error is not None and error.code == "driver_timeout"
        else {}
    )
    return DriverTap(
        ok=ok,
        status="completed" if ok else "failed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation="tap",
        elapsed_ms=1.0,
        attempted=attempted,
        confirmed=confirmed,
        checked_at=utc_now(),
        metadata=metadata,
        error=error,
    )
