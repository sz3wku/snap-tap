from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import cast

from primitives_text_helpers import (
    FakeRunner,
    FakeSnapshotProvider,
    FakeTexter,
    fake_driver_result,
    fake_request,
    fake_snapshot_result,
)

from snap_tap.backends.android.uiautomator2.text import (
    TEXT_INPUT_MODE,
    TEXT_REPLACE_MODE,
    text_uiautomator2,
)
from snap_tap.backends.contracts import DriverError
from snap_tap.primitives import (
    PrimitiveLeaseManager,
    PrimitiveSnapshotResult,
    primitive_receipt_to_dict,
    resolved_text,
)
from snap_tap.primitives.receipt import utc_now
from snap_tap.semantics import SemanticRole
from snap_tap.snapshots import SnapshotBounds


def test_successful_input_receipt_has_resolution_driver_and_after_refs() -> None:
    texter = FakeTexter(fake_driver_result(operation=TEXT_INPUT_MODE))

    receipt = resolved_text(
        fake_request(mode=TEXT_INPUT_MODE),
        snapshot_provider=FakeSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=texter,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["operation"] == "input"
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert payload["target_resolution"] is not None
    assert payload["driver_result"] is not None
    assert payload["after_snapshot_status"] == "completed"
    request = cast(dict[str, object], payload["request"])
    assert "text" not in request
    assert request["text_length"] == 11
    assert request["text_sha256"] == hashlib.sha256(b"hakar smoke").hexdigest()
    assert texter.calls == [
        ("RFCN4010FCK", 60.0, 120.0, "hakar smoke", TEXT_INPUT_MODE)
    ]


def test_successful_replace_text_receipt_uses_replace_mode() -> None:
    receipt = resolved_text(
        fake_request(mode=TEXT_REPLACE_MODE),
        snapshot_provider=FakeSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=FakeTexter(fake_driver_result(operation=TEXT_REPLACE_MODE)),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["operation"] == "replace_text"
    assert payload["status"] == "completed"
    assert cast(dict[str, object], payload["request"])["mode"] == "replace_text"


def test_input_accepts_non_clickable_edit_text_target() -> None:
    texter = FakeTexter(fake_driver_result(operation=TEXT_INPUT_MODE))

    receipt = resolved_text(
        fake_request(clickable=False),
        snapshot_provider=FakeSnapshotProvider(
            [
                fake_snapshot_result("fresh", clickable=False),
                fake_snapshot_result("after", clickable=False),
            ]
        ),
        texter=texter,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "completed"
    assert payload["touched_phone"] is True
    assert texter.calls == [
        ("RFCN4010FCK", 60.0, 120.0, "hakar smoke", TEXT_INPUT_MODE)
    ]


def test_invalid_text_blocks_before_lease_snapshot_or_driver() -> None:
    provider = FakeSnapshotProvider([])
    texter = FakeTexter(None)

    receipt = resolved_text(
        replace(fake_request(), text=""),
        snapshot_provider=provider,
        texter=texter,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_invalid_request"
    assert payload["lease"] is None
    assert provider.calls == []
    assert texter.calls == []


def test_lease_conflict_blocks_before_snapshot_or_driver() -> None:
    manager = PrimitiveLeaseManager(in_memory_only=True)
    held = manager.acquire(device_id="RFCN4010FCK")
    provider = FakeSnapshotProvider([])
    texter = FakeTexter(None)
    try:
        receipt = resolved_text(
            fake_request(),
            snapshot_provider=provider,
            texter=texter,
            lease_manager=manager,
        )
    finally:
        manager.release(held)

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_lease_conflict"
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert provider.calls == []
    assert texter.calls == []


def test_resolution_blocked_returns_receipt_without_driver_call() -> None:
    provider = FakeSnapshotProvider([fake_snapshot_result("source")])
    texter = FakeTexter(None)

    receipt = resolved_text(
        fake_request(),
        snapshot_provider=provider,
        texter=texter,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_resolution_blocked"
    assert texter.calls == []


def test_stale_target_guard_blocks_text_before_driver_call() -> None:
    provider = FakeSnapshotProvider(
        [
            fake_snapshot_result(
                "fresh",
                bounds=SnapshotBounds(250, 20, 350, 220, 100, 200, 300.0, 120.0),
            )
        ]
    )
    texter = FakeTexter(None)

    receipt = resolved_text(
        fake_request(),
        snapshot_provider=provider,
        texter=texter,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_target_stale"
    assert payload["target_resolution"] is not None
    assert payload["driver_result"] is None
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert payload["after_snapshot_status"] == "not_attempted"
    assert texter.calls == []


def test_stale_target_guard_blocks_replace_text_before_driver_call() -> None:
    provider = FakeSnapshotProvider(
        [
            fake_snapshot_result(
                "fresh",
                bounds=SnapshotBounds(250, 20, 350, 220, 100, 200, 300.0, 120.0),
            )
        ]
    )
    texter = FakeTexter(None)

    receipt = resolved_text(
        fake_request(mode=TEXT_REPLACE_MODE),
        snapshot_provider=provider,
        texter=texter,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["operation"] == "replace_text"
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_target_stale"
    assert payload["target_resolution"] is not None
    assert payload["driver_result"] is None
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert payload["after_snapshot_status"] == "not_attempted"
    assert texter.calls == []


def test_non_input_target_blocks_before_driver_call() -> None:
    provider = FakeSnapshotProvider([fake_snapshot_result("fresh", role=SemanticRole.BUTTON)])
    texter = FakeTexter(None)

    receipt = resolved_text(
        fake_request(role=SemanticRole.BUTTON),
        snapshot_provider=provider,
        texter=texter,
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "blocked"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_target_not_input"
    assert payload["attempted_touch"] is False
    assert payload["touched_phone"] is False
    assert texter.calls == []


def test_driver_timeout_is_failed_with_possible_touch_and_after_snapshot() -> None:
    receipt = resolved_text(
        fake_request(),
        snapshot_provider=FakeSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=FakeTexter(
            fake_driver_result(
                ok=False,
                error=DriverError(code="driver_timeout", detail="timeout"),
            )
        ),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "failed"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_driver_timeout"
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert payload["after_snapshot_status"] == "completed"


def test_false_success_is_structured_failure() -> None:
    receipt = resolved_text(
        fake_request(),
        snapshot_provider=FakeSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=FakeTexter(fake_driver_result(confirmed=False)),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "failed"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_false_success"
    assert payload["attempted_touch"] is True


def test_malformed_driver_payload_is_structured_failure() -> None:
    receipt = resolved_text(
        fake_request(),
        snapshot_provider=FakeSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=FakeTexter(
            fake_driver_result(
                ok=False,
                error=DriverError(code="driver_probe_failed", detail="malformed"),
            )
        ),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "failed"
    assert cast(dict[str, object], payload["error"])["code"] == "primitive_driver_failed"
    assert payload["attempted_touch"] is True


def test_driver_failure_after_possible_touch_preserves_touched_truth() -> None:
    receipt = resolved_text(
        fake_request(),
        snapshot_provider=FakeSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=FakeTexter(
            fake_driver_result(
                ok=False,
                error=DriverError(code="input_failed", detail="failed"),
                metadata={"touch_may_have_occurred": True},
            )
        ),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "failed"
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert payload["after_snapshot_status"] == "completed"


def test_non_json_child_failure_receipt_preserves_possible_touch() -> None:
    driver = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=60,
        y=120,
        text="hakar smoke",
        mode=TEXT_INPUT_MODE,
        process_runner=FakeRunner(),
        python_executable="python",
    )

    receipt = resolved_text(
        fake_request(),
        snapshot_provider=FakeSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=FakeTexter(driver),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "failed"
    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert payload["after_snapshot_status"] == "completed"


def test_after_snapshot_failure_after_text_preserves_completed_execution() -> None:
    receipt = resolved_text(
        fake_request(),
        snapshot_provider=FakeSnapshotProvider(
            [
                fake_snapshot_result("fresh"),
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
        texter=FakeTexter(fake_driver_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["status"] == "completed"
    assert payload["ok"] is True
    assert payload["execution_status"] == "completed"
    assert payload["proof_status"] == "unavailable"
    assert payload["after_snapshot_status"] == "failed"
    assert payload["error"] is None


def test_receipt_json_excludes_raw_payloads_and_private_lease_id() -> None:
    receipt = resolved_text(
        fake_request(),
        snapshot_provider=FakeSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=FakeTexter(fake_driver_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert "lease_id" not in cast(dict[str, object], payload["lease"])
    serialized = str(payload)
    for forbidden in ("<hierarchy", "image_base64", "image_bytes", "selector", "prompt"):
        assert forbidden not in serialized


def test_receipt_json_excludes_raw_text_payload() -> None:
    receipt = resolved_text(
        fake_request(),
        snapshot_provider=FakeSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=FakeTexter(fake_driver_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    serialized = json.dumps(payload)
    assert "hakar smoke" not in serialized
    assert cast(dict[str, object], payload["request"])["text_length"] == 11
