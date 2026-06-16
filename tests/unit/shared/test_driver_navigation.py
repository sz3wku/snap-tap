from __future__ import annotations

from collections.abc import Sequence
import json
import sys
from types import SimpleNamespace

import pytest

from snap_tap.backends.android.uiautomator2 import (
    navigation_probe as uiautomator2_navigation_probe,
)
from snap_tap.backends.android.uiautomator2.navigation import (
    NAVIGATION_BACK,
    NAVIGATION_SWIPE,
    navigation_uiautomator2,
)
from snap_tap.backends.android.uiautomator2.process_runner import ProcessResult, ProcessRunner, ProcessTimeoutError


class FakeRunner(ProcessRunner):
    def __init__(
        self,
        result: ProcessResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.result = result
        self.exc = exc
        self.calls: list[list[str]] = []

    def run(self, args: Sequence[str], timeout_s: float) -> ProcessResult:
        self.calls.append(list(args))
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result


def test_back_uses_argument_list_and_confirms_press() -> None:
    runner = FakeRunner(ProcessResult(0, json.dumps({"ok": True, "pressed": True}), ""))

    result = navigation_uiautomator2(
        operation=NAVIGATION_BACK,
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is True
    assert result.attempted is True
    assert result.confirmed is True
    assert runner.calls == [
        [
            "python",
            "-m",
            "snap_tap.backends.android.uiautomator2.navigation_probe",
            "back",
            "--device",
            "RFCN4010FCK",
        ]
    ]


def test_swipe_uses_derived_coordinates_but_public_metadata_excludes_them() -> None:
    runner = FakeRunner(
        ProcessResult(
            0,
            json.dumps(
                {
                    "ok": True,
                    "swiped": True,
                    "metadata": {"touch_may_have_occurred": True, "x1": 1},
                }
            ),
            "",
        )
    )

    result = navigation_uiautomator2(
        operation=NAVIGATION_SWIPE,
        device_id="RFCN4010FCK",
        direction="left",
        x1=800,
        y1=1200,
        x2=200,
        y2=1200,
        duration_ms=300,
        distance_ratio=0.55,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is True
    assert result.metadata["direction"] == "left"
    assert result.metadata["distance_ratio"] == 0.55
    assert result.metadata["duration_ms"] == 300
    assert "x1" not in result.metadata
    assert "--x1" in runner.calls[0]


def test_navigation_blocks_bad_serial_before_subprocess() -> None:
    runner = FakeRunner(ProcessResult(0, "{}", ""))

    result = navigation_uiautomator2(
        operation=NAVIGATION_BACK,
        device_id="bad serial",
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "device_offline"
    assert result.attempted is False
    assert runner.calls == []


def test_navigation_timeout_preserves_possible_touch_truth() -> None:
    runner = FakeRunner(exc=ProcessTimeoutError("timeout"))

    result = navigation_uiautomator2(
        operation=NAVIGATION_BACK,
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_timeout"
    assert result.attempted is True
    assert result.metadata["touch_may_have_occurred"] is True


def test_navigation_non_json_child_payload_fails_with_possible_touch() -> None:
    runner = FakeRunner(ProcessResult(1, "not json", ""))

    result = navigation_uiautomator2(
        operation=NAVIGATION_BACK,
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "navigation_failed"
    assert result.metadata["touch_may_have_occurred"] is True


def test_child_probe_normalizes_uiautomator2_press_false_return(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Device:
        def press(self, operation: str) -> bool:
            assert operation == NAVIGATION_BACK
            return False

    monkeypatch.setitem(
        sys.modules,
        "uiautomator2",
        SimpleNamespace(connect=lambda device_id: Device()),
    )

    exit_code = uiautomator2_navigation_probe.main(
        [NAVIGATION_BACK, "--device", "RFCN4010FCK"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["pressed"] is True
    assert payload["metadata"]["press_returned"] is True


def test_child_probe_blocks_bad_serial_before_connect(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def connect(device_id: str) -> object:
        raise AssertionError("connect should not be called for malformed serial")

    monkeypatch.setitem(sys.modules, "uiautomator2", SimpleNamespace(connect=connect))

    exit_code = uiautomator2_navigation_probe.main(
        [NAVIGATION_BACK, "--device", "bad serial"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error"]["code"] == "device_offline"


def test_navigation_false_confirmation_from_untrusted_payload_is_not_confirmed() -> None:
    runner = FakeRunner(ProcessResult(0, json.dumps({"ok": True, "pressed": False}), ""))

    result = navigation_uiautomator2(
        operation=NAVIGATION_BACK,
        device_id="RFCN4010FCK",
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is True
    assert result.confirmed is False
