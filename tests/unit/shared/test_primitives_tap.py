from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from primitives_tap_helpers import (
    FakeSnapshotProvider,
    FakeTapper,
    RaisingSnapshotProvider,
    RaisingTapper,
    fake_driver_tap_result,
    fake_tap_request,
    fake_tap_snapshot_result,
)

from snap_tap.backends.contracts import DriverError, DriverTapXmlDump, DriverXmlDump
from snap_tap.primitives import (
    PrimitiveLeaseManager,
    PrimitiveRequestError,
    PrimitiveSnapshotResult,
    primitive_receipt_to_dict,
    resolved_tap,
    target_signature_from_dict,
)
from snap_tap.primitives.receipt import utc_now
from snap_tap.semantics import SemanticRole
from snap_tap.snapshots import SnapshotBounds


def test_lease_conflict_blocks_before_snapshot_or_driver() -> None:
    manager = PrimitiveLeaseManager(in_memory_only=True)
    held = manager.acquire(device_id="RFCN4010FCK")
    provider = FakeSnapshotProvider([])
    tapper = FakeTapper(None)
    try:
        receipt = resolved_tap(
            fake_tap_request(),
            snapshot_provider=provider,
            tapper=tapper,
            lease_manager=manager,
        )
    finally:
        manager.release(held)

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert payload["ok"] is False
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_lease_conflict"
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert provider.calls == []
    assert tapper.calls == []


def test_lease_releases_after_success() -> None:
    manager = PrimitiveLeaseManager(in_memory_only=True)
    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=FakeSnapshotProvider([fake_tap_snapshot_result("fresh"), fake_tap_snapshot_result("after")]),
        tapper=FakeTapper(fake_driver_tap_result()),
        lease_manager=manager,
    )

    assert receipt.ok is True
    acquired = manager.acquire(device_id="RFCN4010FCK")
    manager.release(acquired)


def test_resolution_blocked_returns_receipt_without_driver_touch() -> None:
    provider = FakeSnapshotProvider([fake_tap_snapshot_result("source")])
    tapper = FakeTapper(None)

    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=provider,
        tapper=tapper,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_resolution_blocked"
    assert tapper.calls == []


def test_stale_center_drift_blocks_before_driver_and_preserves_resolution() -> None:
    provider = FakeSnapshotProvider(
        [
            fake_tap_snapshot_result(
                "fresh",
                bounds=SnapshotBounds(250, 20, 350, 220, 100, 200, 300.0, 120.0),
            )
        ]
    )
    tapper = FakeTapper(None)

    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=provider,
        tapper=tapper,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_target_stale"
    assert cast(dict[str, object], payload["blocking_reason"])["code"] == "primitive_target_stale"
    assert payload["target_resolution"] is not None
    assert payload["driver_result"] is None
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert payload["after_snapshot_status"] == "not_attempted"
    assert tapper.calls == []


def test_stale_size_drift_blocks_before_driver() -> None:
    provider = FakeSnapshotProvider(
        [
            fake_tap_snapshot_result(
                "fresh",
                bounds=SnapshotBounds(10, 20, 180, 220, 170, 200, 95.0, 120.0),
            )
        ]
    )
    tapper = FakeTapper(None)

    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=provider,
        tapper=tapper,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_target_stale"
    assert payload["driver_result"] is None
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert tapper.calls == []


def test_non_clickable_resolved_input_blocks_tap_before_driver() -> None:
    provider = FakeSnapshotProvider(
        [fake_tap_snapshot_result("fresh", role=SemanticRole.INPUT, clickable=False)]
    )
    tapper = FakeTapper(None)

    receipt = resolved_tap(
        fake_tap_request(role=SemanticRole.INPUT, clickable=False),
        snapshot_provider=provider,
        tapper=tapper,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == (
        "primitive_target_not_tappable"
    )
    assert payload["target_resolution"] is not None
    assert payload["driver_result"] is None
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert tapper.calls == []


def test_non_finite_fresh_bounds_block_before_driver() -> None:
    provider = FakeSnapshotProvider(
        [
            fake_tap_snapshot_result(
                "fresh",
                bounds=SnapshotBounds(
                    10,
                    20,
                    110,
                    220,
                    100,
                    200,
                    float("nan"),
                    120.0,
                ),
            ),
            fake_tap_snapshot_result("after"),
        ]
    )
    tapper = FakeTapper(fake_driver_tap_result())

    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=provider,
        tapper=tapper,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_target_stale"
    assert payload["driver_result"] is None
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert tapper.calls == []


def test_small_bounds_drift_still_uses_resolved_fresh_target_center() -> None:
    provider = FakeSnapshotProvider(
        [
            fake_tap_snapshot_result(
                "fresh",
                bounds=SnapshotBounds(50, 20, 150, 220, 100, 200, 100.0, 120.0),
            ),
            fake_tap_snapshot_result("after"),
        ]
    )
    tapper = FakeTapper(fake_driver_tap_result())

    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=provider,
        tapper=tapper,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    assert receipt.status == "completed"
    assert tapper.calls == [("RFCN4010FCK", 100.0, 120.0)]


def test_combined_tap_uses_backend_after_xml_without_second_capture() -> None:
    provider = _FakeCombinedSnapshotProvider(
        [fake_tap_snapshot_result("fresh"), fake_tap_snapshot_result("after")]
    )
    tapper = _FakeCombinedTapper(
        DriverTapXmlDump(
            tap=fake_driver_tap_result(),
            xml_dump=DriverXmlDump.success(
                device_id="RFCN4010FCK",
                backend="fake",
                elapsed_ms=3.0,
                xml="<hierarchy><node /></hierarchy>",
            ),
        )
    )

    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=provider,
        tapper=tapper,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    assert receipt.status == "completed"
    assert provider.calls == ["RFCN4010FCK"]
    assert provider.completed_xml == [("fake", 10.0)]
    assert tapper.calls == []
    assert tapper.combined_calls == [("RFCN4010FCK", 60.0, 120.0, 500)]


def test_lease_releases_after_blocked_resolution() -> None:
    manager = PrimitiveLeaseManager(in_memory_only=True)

    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=FakeSnapshotProvider([fake_tap_snapshot_result("source")]),
        tapper=FakeTapper(None),
        lease_manager=manager,
    )

    assert receipt.status == "blocked"
    acquired = manager.acquire(device_id="RFCN4010FCK")
    manager.release(acquired)


def test_snapshot_exception_returns_receipt_without_driver_touch() -> None:
    manager = PrimitiveLeaseManager(in_memory_only=True)
    provider = RaisingSnapshotProvider()
    tapper = FakeTapper(None)

    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=provider,
        tapper=tapper,
        lease_manager=manager,
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_resolution_blocked"
    assert provider.calls == ["RFCN4010FCK"]
    assert tapper.calls == []
    acquired = manager.acquire(device_id="RFCN4010FCK")
    manager.release(acquired)


def test_success_receipt_shape_excludes_raw_payloads() -> None:
    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=FakeSnapshotProvider([fake_tap_snapshot_result("fresh"), fake_tap_snapshot_result("after")]),
        tapper=FakeTapper(fake_driver_tap_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["schema_version"] == "primitive_receipt.v1"
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert payload["after_snapshot_status"] == "completed"
    assert "lease_id" not in cast(dict[str, object], payload["lease"])
    serialized = str(payload)
    for forbidden in ("<hierarchy", "image_base64", "image_bytes", "selector", "prompt"):
        assert forbidden not in serialized


def test_false_success_is_failed_not_completed() -> None:
    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=FakeSnapshotProvider([fake_tap_snapshot_result("fresh"), fake_tap_snapshot_result("after")]),
        tapper=FakeTapper(fake_driver_tap_result(confirmed=False)),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "failed"
    assert payload["ok"] is False
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is False
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_false_success"


def test_driver_failure_mappings() -> None:
    cases = (
        ("driver_timeout", "primitive_driver_timeout", True, True),
        ("driver_unavailable", "primitive_driver_unavailable", False, False),
        ("tap_failed", "primitive_driver_failed", True, False),
    )
    for driver_code, primitive_code, attempted, touched in cases:
        provider_results = [fake_tap_snapshot_result("fresh")]
        if attempted:
            provider_results.append(fake_tap_snapshot_result("after"))
        receipt = resolved_tap(
            fake_tap_request(),
            snapshot_provider=FakeSnapshotProvider(provider_results),
            tapper=FakeTapper(
                fake_driver_tap_result(
                    ok=False,
                    attempted=attempted,
                    confirmed=False,
                    error=DriverError(code=driver_code, detail=driver_code),
                )
            ),
            lease_manager=PrimitiveLeaseManager(in_memory_only=True),
        )
        payload = primitive_receipt_to_dict(receipt)
        assert payload["status"] == "failed"
        assert cast(dict[str, object], payload["error"])["code"] == primitive_code
        assert payload["attempted_touch"] is attempted
        assert payload["touched_phone"] is touched


def test_after_snapshot_failure_preserves_completed_execution() -> None:
    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=FakeSnapshotProvider(
            [
                fake_tap_snapshot_result("fresh"),
                PrimitiveSnapshotResult(
                    ok=False,
                    status="blocked",
                    device_id="RFCN4010FCK",
                    checked_at=utc_now(),
                    elapsed_ms=1.0,
                    error=DriverError(code="snapshot_parse_failed", detail="bad xml"),
                ),
            ]
        ),
        tapper=FakeTapper(fake_driver_tap_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "completed"
    assert payload["ok"] is True
    assert payload["execution_status"] == "completed"
    assert payload["proof_status"] == "unavailable"
    assert payload["after_snapshot_status"] == "failed"
    assert payload["error"] is None


def test_tapper_exception_returns_failed_receipt_and_after_snapshot() -> None:
    tapper = RaisingTapper()

    receipt = resolved_tap(
        fake_tap_request(),
        snapshot_provider=FakeSnapshotProvider(
            [fake_tap_snapshot_result("fresh"), fake_tap_snapshot_result("after")]
        ),
        tapper=tapper,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "failed"
    assert payload["ok"] is False
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert payload["after_snapshot_status"] == "completed"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_driver_failed"
    assert tapper.calls == [("RFCN4010FCK", 60.0, 120.0)]


def test_bad_serial_blocks_before_snapshot_or_driver() -> None:
    provider = FakeSnapshotProvider([])
    tapper = FakeTapper(None)

    receipt = resolved_tap(
        replace(fake_tap_request(), device_id="bad serial"),
        snapshot_provider=provider,
        tapper=tapper,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_invalid_request"
    assert provider.calls == []
    assert tapper.calls == []


def test_malformed_signature_is_rejected_before_primitive() -> None:
    with pytest.raises(PrimitiveRequestError) as exc:
        target_signature_from_dict({"schema_version": "target_signature.v1"})

    assert exc.value.code == "primitive_invalid_request"


class _FakeCombinedTapper(FakeTapper):
    def __init__(self, result: DriverTapXmlDump) -> None:
        super().__init__(None)
        self.combined_result = result
        self.combined_calls: list[tuple[str, float, float, int]] = []

    def tap_and_dump_xml(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        settle_ms: int = 0,
        timeout_s: float = 10.0,
    ) -> DriverTapXmlDump:
        self.combined_calls.append((device_id, x, y, settle_ms))
        return self.combined_result


class _FakeCombinedSnapshotProvider(FakeSnapshotProvider):
    def __init__(self, results: list[PrimitiveSnapshotResult]) -> None:
        super().__init__(results)
        self.completed_xml: list[tuple[str, float]] = []

    def complete_xml_dump(
        self,
        xml_dump: DriverXmlDump,
        *,
        timeout_s: float = 10.0,
    ) -> PrimitiveSnapshotResult:
        self.completed_xml.append((xml_dump.backend, timeout_s))
        return self.results.pop(0)
