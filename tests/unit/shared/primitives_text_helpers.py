from __future__ import annotations

from collections.abc import Sequence

from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessResult,
    ProcessRunner,
)
from snap_tap.backends.android.uiautomator2.text import TEXT_INPUT_MODE
from snap_tap.backends.contracts import DriverError, DriverText
from snap_tap.primitives import PrimitiveSnapshotResult, PrimitiveTextRequest
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


class FakeTexter:
    backend_name = "fake"

    def __init__(self, result: DriverText | None) -> None:
        self.result = result
        self.calls: list[tuple[str, float, float, str, str]] = []

    def input_text(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        text: str,
        mode: str,
        timeout_s: float = 10.0,
    ) -> DriverText:
        self.calls.append((device_id, x, y, text, mode))
        assert self.result is not None
        return self.result


class FakeRunner(ProcessRunner):
    def run(self, args: Sequence[str], timeout_s: float) -> ProcessResult:
        return ProcessResult(1, "not json", "")


def fake_request(
    *,
    mode: str = TEXT_INPUT_MODE,
    role: SemanticRole = SemanticRole.INPUT,
    clickable: bool = True,
) -> PrimitiveTextRequest:
    source = build_snapshot_targets(
        fake_snapshot("source", role=role, clickable=clickable)
    )
    signature = build_target_signature(source, "e001")
    return PrimitiveTextRequest(
        device_id="RFCN4010FCK",
        signature=signature,
        text="hakar smoke",
        mode=mode,
    )


def fake_snapshot_result(
    snapshot_id: str,
    *,
    role: SemanticRole = SemanticRole.INPUT,
    clickable: bool = True,
    bounds: SnapshotBounds | None = None,
) -> PrimitiveSnapshotResult:
    snapshot = fake_snapshot(
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


def fake_snapshot(
    snapshot_id: str,
    *,
    role: SemanticRole = SemanticRole.INPUT,
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
        label="Message",
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


def fake_driver_result(
    *,
    operation: str = TEXT_INPUT_MODE,
    ok: bool = True,
    attempted: bool = True,
    confirmed: bool = True,
    error: DriverError | None = None,
    metadata: dict[str, object] | None = None,
) -> DriverText:
    driver_metadata = metadata if metadata is not None else (
        {"touch_may_have_occurred": True}
        if error is not None and error.code == "driver_timeout"
        else {}
    )
    return DriverText(
        ok=ok,
        status="completed" if ok else "failed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation=operation,
        elapsed_ms=1.0,
        attempted=attempted,
        confirmed=confirmed,
        checked_at=utc_now(),
        metadata=driver_metadata,
        error=error,
    )
