from __future__ import annotations

from typing import cast

from snap_tap.backends.contracts import DriverAppOpen, DriverError
from snap_tap.primitives import (
    PrimitiveAppOpenRequest,
    PrimitiveLeaseManager,
    PrimitiveSnapshotResult,
    app_open_primitive,
    primitive_receipt_to_dict,
)
from snap_tap.primitives.receipt import utc_now
from snap_tap.semantics import (
    SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
    SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
    SemanticElement,
    SemanticPackageSummary,
    SemanticRole,
    SemanticScreenCounts,
    SemanticScreenMetadata,
    SemanticSnapshot,
    SemanticViewport,
    ViewportOrientation,
)
from snap_tap.snapshots import SnapshotBounds


class FakeAppOpener:
    backend_name = "fake"

    def __init__(self, result: DriverAppOpen) -> None:
        self.result = result
        self.calls: list[tuple[str, str, str | None, float]] = []

    def open_app(
        self,
        *,
        device_id: str,
        package: str,
        activity: str | None = None,
        timeout_s: float = 10.0,
    ) -> DriverAppOpen:
        self.calls.append((device_id, package, activity, timeout_s))
        return self.result


class FakeSnapshotProvider:
    def __init__(self, result: PrimitiveSnapshotResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        self.calls.append(device_id)
        return self.result


def test_app_open_requires_matching_foreground_package() -> None:
    request = _request(package="com.example.target")
    provider = FakeSnapshotProvider(
        _snapshot_result("after", dominant_package="com.example.target")
    )
    opener = FakeAppOpener(_driver_app_open_result())

    receipt = app_open_primitive(
        request,
        snapshot_provider=provider,
        opener=opener,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert payload["after_snapshot_required"] is True
    assert payload["proof_status"] == "completed"
    assert payload["error"] is None
    assert opener.calls == [("RFCN4010FCK", "com.example.target", None, 10.0)]
    assert provider.calls == ["RFCN4010FCK"]


def test_app_open_uses_normalized_package_for_foreground_proof() -> None:
    receipt = app_open_primitive(
        _request(package=" com.example.target "),
        snapshot_provider=FakeSnapshotProvider(
            _snapshot_result("after", dominant_package="com.example.target")
        ),
        opener=FakeAppOpener(_driver_app_open_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["ok"] is True
    assert payload["status"] == "completed"


def test_app_open_foreground_mismatch_is_partial_not_completed() -> None:
    receipt = app_open_primitive(
        _request(package="com.example.target"),
        snapshot_provider=FakeSnapshotProvider(
            _snapshot_result("after", dominant_package="com.other.app")
        ),
        opener=FakeAppOpener(_driver_app_open_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["ok"] is False
    assert payload["status"] == "partial"
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert payload["after_snapshot_status"] == "completed"
    assert payload["proof_status"] == "completed"
    error = cast(dict[str, object], payload["error"])
    assert error["code"] == "primitive_app_open_foreground_mismatch"
    driver = cast(dict[str, object], payload["driver_result"])
    metadata = cast(dict[str, object], driver["metadata"])
    assert metadata["requested_package"] == "com.example.target"
    assert metadata["foreground_package"] == "com.other.app"


def test_app_open_unknown_foreground_is_partial_not_completed() -> None:
    receipt = app_open_primitive(
        _request(package="com.example.target"),
        snapshot_provider=FakeSnapshotProvider(
            _snapshot_result("after", dominant_package=None)
        ),
        opener=FakeAppOpener(_driver_app_open_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["ok"] is False
    assert payload["status"] == "partial"
    assert payload["after_snapshot_status"] == "completed"
    error = cast(dict[str, object], payload["error"])
    assert error["code"] == "primitive_app_open_foreground_unknown"


def test_app_open_after_snapshot_failure_is_partial_required_proof_failure() -> None:
    receipt = app_open_primitive(
        _request(package="com.example.target"),
        snapshot_provider=FakeSnapshotProvider(
            PrimitiveSnapshotResult(
                ok=False,
                status="blocked",
                device_id="RFCN4010FCK",
                checked_at=utc_now(),
                elapsed_ms=1.0,
                error=DriverError(code="snapshot_parse_failed", detail="bad xml"),
            )
        ),
        opener=FakeAppOpener(_driver_app_open_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["ok"] is False
    assert payload["status"] == "partial"
    assert payload["proof_status"] == "required_failed"
    assert payload["after_snapshot_status"] == "failed"
    error = cast(dict[str, object], payload["error"])
    assert error["code"] == "primitive_after_snapshot_failed"


def _request(*, package: str) -> PrimitiveAppOpenRequest:
    return PrimitiveAppOpenRequest(
        device_id="RFCN4010FCK",
        query=package,
        package=package,
    )


def _driver_app_open_result() -> DriverAppOpen:
    return DriverAppOpen(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation="app_open",
        checked_at=utc_now(),
        elapsed_ms=1.0,
        attempted=True,
        confirmed=True,
    )


def _snapshot_result(
    snapshot_id: str,
    *,
    dominant_package: str | None,
) -> PrimitiveSnapshotResult:
    snapshot = _snapshot(snapshot_id, dominant_package=dominant_package)
    return PrimitiveSnapshotResult(
        ok=True,
        status="completed",
        device_id=snapshot.device_id,
        checked_at=snapshot.captured_at,
        elapsed_ms=1.0,
        snapshot=snapshot,
    )


def _snapshot(
    snapshot_id: str,
    *,
    dominant_package: str | None,
) -> SemanticSnapshot:
    package = dominant_package or "com.example.unknown"
    element = SemanticElement(
        source_index=7,
        role=SemanticRole.BUTTON,
        bounds=SnapshotBounds(10, 20, 110, 220, 100, 200, 60.0, 120.0),
        enabled=True,
        clickable=True,
        scrollable=False,
        label="Home",
        label_source="content_desc",
        class_name="android.widget.Button",
        resource_id=f"{package}:id/home",
        package=package,
    )
    return SemanticSnapshot(
        schema_version=SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        device_id="RFCN4010FCK",
        captured_at="2026-06-14T10:00:00+00:00",
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
                clickable_count=1,
                actionable_count=1,
                labeled_count=1,
                unknown_count=0,
            ),
            packages=(
                SemanticPackageSummary(
                    package=package,
                    element_count=1,
                    visible_count=1,
                    semantic_count=1,
                ),
            ),
            dominant_package=dominant_package,
        ),
    )
