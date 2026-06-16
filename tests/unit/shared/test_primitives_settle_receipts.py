from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from primitives_tap_helpers import (
    FakeSnapshotProvider as TapSnapshotProvider,
)
from primitives_tap_helpers import (
    FakeTapper,
    fake_driver_tap_result,
    fake_tap_request,
    fake_tap_snapshot_result,
)
from primitives_text_helpers import (
    FakeSnapshotProvider as TextSnapshotProvider,
)
from primitives_text_helpers import (
    FakeTexter,
    fake_driver_result,
    fake_request,
    fake_snapshot_result,
)
from test_primitives_navigation import FakeNavigator, FakeProvider, _driver_result

from snap_tap.backends.android.uiautomator2.navigation import NAVIGATION_BACK
from snap_tap.backends.android.uiautomator2.text import TEXT_INPUT_MODE
from snap_tap.primitives import (
    PrimitiveLeaseManager,
    PrimitiveNavigationRequest,
    navigation_primitive,
    primitive_receipt_to_dict,
    resolved_tap,
    resolved_text,
)
from snap_tap.primitives.models import (
    DEFAULT_POST_ACTION_SETTLE_MS,
    MAX_POST_ACTION_SETTLE_MS,
)


@pytest.mark.parametrize(
    ("raw_settle", "expected"),
    [
        (-1, 0),
        (True, DEFAULT_POST_ACTION_SETTLE_MS),
        (MAX_POST_ACTION_SETTLE_MS + 1, MAX_POST_ACTION_SETTLE_MS),
    ],
)
def test_tap_receipt_records_applied_post_action_settle_ms(
    raw_settle: int,
    expected: int,
) -> None:
    receipt = resolved_tap(
        replace(fake_tap_request(), post_action_settle_ms=raw_settle),
        snapshot_provider=TapSnapshotProvider(
            [fake_tap_snapshot_result("fresh"), fake_tap_snapshot_result("after")]
        ),
        tapper=FakeTapper(fake_driver_tap_result()),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["post_action_settle_ms"] == expected
    assert cast(dict[str, object], payload["request"])["post_action_settle_ms"] == expected


@pytest.mark.parametrize(
    ("raw_settle", "expected"),
    [
        (-1, 0),
        (True, DEFAULT_POST_ACTION_SETTLE_MS),
        (MAX_POST_ACTION_SETTLE_MS + 1, MAX_POST_ACTION_SETTLE_MS),
    ],
)
def test_text_receipt_records_applied_post_action_settle_ms(
    raw_settle: int,
    expected: int,
) -> None:
    receipt = resolved_text(
        replace(fake_request(mode=TEXT_INPUT_MODE), post_action_settle_ms=raw_settle),
        snapshot_provider=TextSnapshotProvider(
            [fake_snapshot_result("fresh"), fake_snapshot_result("after")]
        ),
        texter=FakeTexter(fake_driver_result(operation=TEXT_INPUT_MODE)),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["post_action_settle_ms"] == expected
    assert cast(dict[str, object], payload["request"])["post_action_settle_ms"] == expected


@pytest.mark.parametrize(
    ("raw_settle", "expected"),
    [
        (-1, 0),
        (True, DEFAULT_POST_ACTION_SETTLE_MS),
        (MAX_POST_ACTION_SETTLE_MS + 1, MAX_POST_ACTION_SETTLE_MS),
    ],
)
def test_navigation_receipt_records_applied_post_action_settle_ms(
    raw_settle: int,
    expected: int,
) -> None:
    receipt = navigation_primitive(
        PrimitiveNavigationRequest(
            device_id="RFCN4010FCK",
            operation=NAVIGATION_BACK,
            post_action_settle_ms=raw_settle,
        ),
        snapshot_provider=FakeProvider([fake_snapshot_result("after")]),
        navigator=FakeNavigator(_driver_result(operation=NAVIGATION_BACK)),
        lease_manager=PrimitiveLeaseManager(in_memory_only=True),
    )

    payload = primitive_receipt_to_dict(receipt)
    assert payload["post_action_settle_ms"] == expected
    assert cast(dict[str, object], payload["request"])["post_action_settle_ms"] == expected
