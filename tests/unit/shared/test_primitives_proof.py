from __future__ import annotations

from pytest import MonkeyPatch

from snap_tap.primitives import PrimitiveDriverResult
from snap_tap.primitives.models import (
    DEFAULT_POST_ACTION_SETTLE_MS,
    MAX_POST_ACTION_SETTLE_MS,
)
from snap_tap.primitives.proof import (
    normalize_post_action_settle_ms,
    settle_after_driver_action,
)
from snap_tap.primitives.receipt import utc_now


def test_normalize_post_action_settle_ms_bounds_debug_override() -> None:
    assert normalize_post_action_settle_ms(-1) == 0
    assert normalize_post_action_settle_ms(1234) == 1234
    assert normalize_post_action_settle_ms(MAX_POST_ACTION_SETTLE_MS + 1) == 10000
    assert normalize_post_action_settle_ms(True) == DEFAULT_POST_ACTION_SETTLE_MS


def test_settle_applies_only_to_real_attempted_driver(monkeypatch: MonkeyPatch) -> None:
    calls: list[float] = []
    monkeypatch.setattr("snap_tap.primitives.proof.sleep", calls.append)

    settle_after_driver_action(
        PrimitiveDriverResult(
            ok=True,
            backend="fake",
            operation="tap",
            elapsed_ms=1.0,
            attempted=True,
            confirmed=True,
            checked_at=utc_now(),
        ),
        settle_ms=2000,
    )
    assert calls == []

    settle_after_driver_action(
        PrimitiveDriverResult(
            ok=True,
            backend="uiautomator2",
            operation="tap",
            elapsed_ms=1.0,
            attempted=True,
            confirmed=True,
            checked_at=utc_now(),
        ),
        settle_ms=2000,
    )
    assert calls == [2.0]
