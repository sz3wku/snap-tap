from __future__ import annotations

from dataclasses import replace
from typing import cast

from snap_tap.backends.contracts import DriverError
from snap_tap.backends.contracts import DriverNavigation
from snap_tap.backends.android.uiautomator2.navigation import NAVIGATION_BACK, NAVIGATION_SWIPE
from snap_tap.primitives import (
    PrimitiveLeaseManager,
    PrimitiveNavigationRequest,
    PrimitiveSnapshotResult,
    navigation_primitive,
    primitive_receipt_to_dict,
)
from snap_tap.primitives.receipt import utc_now
from snap_tap.semantics import SemanticViewport, ViewportOrientation
from primitives_text_helpers import fake_snapshot, fake_snapshot_result


class FakeProvider:
    def __init__(self, results: list[PrimitiveSnapshotResult]) -> None:
        self.results = results
        self.calls: list[str] = []

    def capture(self, device_id: str, timeout_s: float = 10.0) -> PrimitiveSnapshotResult:
        self.calls.append(device_id)
        return self.results.pop(0)


class FakeNavigator:
    backend_name = "fake"

    def __init__(self, result: DriverNavigation) -> None:
        self.result = result
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def back(self, *, device_id: str, timeout_s: float = 10.0) -> DriverNavigation:
        self.calls.append(("back", (device_id,)))
        return self.result

    def home(self, *, device_id: str, timeout_s: float = 10.0) -> DriverNavigation:
        self.calls.append(("home", (device_id,)))
        return self.result

    def swipe(
        self,
        *,
        device_id: str,
        direction: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration_ms: int,
        distance_ratio: float,
        timeout_s: float = 10.0,
    ) -> DriverNavigation:
        self.calls.append(("swipe", (device_id, direction, x1, y1, x2, y2)))
        return self.result


def test_back_success_emits_completed_receipt_with_after_snapshot() -> None:
    navigator = FakeNavigator(_driver_result(operation=NAVIGATION_BACK))
    provider = FakeProvider([fake_snapshot_result("after")])

    receipt = navigation_primitive(
        PrimitiveNavigationRequest(device_id="RFCN4010FCK", operation=NAVIGATION_BACK),
        snapshot_provider=provider,
        navigator=navigator,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert payload["target_resolution"] is None
    assert payload["before_snapshot"] is None
    assert payload["after_snapshot_status"] == "completed"
    assert payload["execution_status"] == "completed"
    assert payload["proof_status"] == "completed"
    assert provider.calls == ["RFCN4010FCK"]


def test_wait_uses_snapshots_and_never_reports_phone_touch() -> None:
    receipt = navigation_primitive(
        PrimitiveNavigationRequest(
            device_id="RFCN4010FCK",
            operation="wait",
            seconds=0,
        ),
        snapshot_provider=FakeProvider(
            [fake_snapshot_result("before"), fake_snapshot_result("after")]
        ),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["ok"] is True
    assert payload["operation"] == "wait"
    assert payload["driver_result"] is None
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert payload["after_snapshot_status"] == "completed"
    assert payload["after_snapshot_required"] is True
    assert payload["proof_status"] == "completed"


def test_swipe_derives_coordinates_from_viewport_without_public_coordinate_api() -> None:
    navigator = FakeNavigator(_driver_result(operation=NAVIGATION_SWIPE))
    receipt = navigation_primitive(
        PrimitiveNavigationRequest(
            device_id="RFCN4010FCK",
            operation=NAVIGATION_SWIPE,
            direction="left",
            distance_ratio=0.5,
            duration_ms=300,
        ),
        snapshot_provider=FakeProvider(
            [fake_snapshot_result("before"), fake_snapshot_result("after")]
        ),
        navigator=navigator,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["ok"] is True
    request = cast(dict[str, object], payload["request"])
    assert request["direction"] == "left"
    assert "x1" not in str(payload)
    assert navigator.calls[0][0] == "swipe"
    assert navigator.calls[0][1][2:] == (810.0, 1200.0, 270.0, 1200.0)


def test_swipe_blocks_missing_viewport_before_driver() -> None:
    snapshot = fake_snapshot("before")
    metadata = replace(
        snapshot.screen_metadata,
        viewport=SemanticViewport(orientation=ViewportOrientation.UNKNOWN),
    )
    provider = FakeProvider(
        [
            PrimitiveSnapshotResult(
                ok=True,
                status="completed",
                device_id=snapshot.device_id,
                checked_at=snapshot.captured_at,
                elapsed_ms=1.0,
                snapshot=replace(snapshot, screen_metadata=metadata),
            )
        ]
    )
    navigator = FakeNavigator(_driver_result(operation=NAVIGATION_SWIPE))

    receipt = navigation_primitive(
        PrimitiveNavigationRequest(
            device_id="RFCN4010FCK",
            operation=NAVIGATION_SWIPE,
            direction="up",
        ),
        snapshot_provider=provider,
        navigator=navigator,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    error = cast(dict[str, object], payload["error"])
    assert error["code"] == "primitive_viewport_blocked"
    assert payload["attempted_touch"] is False
    assert navigator.calls == []


def test_invalid_request_and_lease_conflict_block_before_snapshot_or_driver() -> None:
    bad = navigation_primitive(
        PrimitiveNavigationRequest(device_id="bad serial", operation=NAVIGATION_BACK),
        snapshot_provider=FakeProvider([]),
        navigator=FakeNavigator(_driver_result()),
    )
    assert bad.error is not None
    assert bad.error.code == "primitive_invalid_request"

    manager = PrimitiveLeaseManager(in_memory_only=True)
    lease = manager.acquire(device_id="RFCN4010FCK", timeout_s=30.0)
    try:
        conflict = navigation_primitive(
            PrimitiveNavigationRequest(
                device_id="RFCN4010FCK",
                operation=NAVIGATION_BACK,
            ),
            snapshot_provider=FakeProvider([]),
            navigator=FakeNavigator(_driver_result()),
            lease_manager=manager,
        )
    finally:
        manager.release(lease)

    assert conflict.error is not None
    assert conflict.error.code == "primitive_lease_conflict"
    assert conflict.before_snapshot is None
    assert conflict.attempted_touch is False


def test_driver_timeout_and_after_snapshot_failure_preserve_receipts() -> None:
    timeout_receipt = navigation_primitive(
        PrimitiveNavigationRequest(device_id="RFCN4010FCK", operation=NAVIGATION_BACK),
        snapshot_provider=FakeProvider([fake_snapshot_result("before")]),
        navigator=FakeNavigator(
            _driver_result(
                ok=False,
                confirmed=False,
                error=DriverError(code="driver_timeout", detail="timeout"),
                metadata={"touch_may_have_occurred": True},
            )
        ),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )
    assert timeout_receipt.error is not None
    assert timeout_receipt.error.code == "primitive_driver_timeout"
    assert timeout_receipt.touched_phone is True

    after_failure = PrimitiveSnapshotResult(
        ok=False,
        status="failed",
        device_id="RFCN4010FCK",
        checked_at=utc_now(),
        elapsed_ms=1.0,
        error=DriverError(code="driver_timeout", detail="after failed"),
    )
    completed_with_missing_proof = navigation_primitive(
        PrimitiveNavigationRequest(device_id="RFCN4010FCK", operation=NAVIGATION_BACK),
        snapshot_provider=FakeProvider([after_failure]),
        navigator=FakeNavigator(_driver_result(operation=NAVIGATION_BACK)),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )
    payload = primitive_receipt_to_dict(completed_with_missing_proof)
    assert payload["status"] == "completed"
    assert payload["ok"] is True
    assert payload["execution_status"] == "completed"
    assert payload["proof_status"] == "unavailable"
    assert payload["after_snapshot_status"] == "failed"
    assert payload["error"] is None


def test_false_success_is_failed_receipt() -> None:
    receipt = navigation_primitive(
        PrimitiveNavigationRequest(device_id="RFCN4010FCK", operation=NAVIGATION_BACK),
        snapshot_provider=FakeProvider(
            [fake_snapshot_result("before"), fake_snapshot_result("after")]
        ),
        navigator=FakeNavigator(_driver_result(operation=NAVIGATION_BACK, confirmed=False)),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    assert receipt.status == "failed"
    assert receipt.error is not None
    assert receipt.error.code == "primitive_false_success"


def _driver_result(
    *,
    operation: str = NAVIGATION_BACK,
    ok: bool = True,
    confirmed: bool = True,
    error: DriverError | None = None,
    metadata: dict[str, object] | None = None,
) -> DriverNavigation:
    return DriverNavigation(
        ok=ok,
        status="completed" if ok else "failed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation=operation,
        elapsed_ms=1.0,
        attempted=True,
        confirmed=confirmed,
        checked_at=utc_now(),
        metadata=metadata or {},
        error=error,
    )
