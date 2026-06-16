from __future__ import annotations

from collections.abc import Sequence
import json
import os
import subprocess
import sys

from snap_tap.backends.android.uiautomator2.process_runner import ProcessResult, ProcessRunner, ProcessTimeoutError
from snap_tap.backends.android.uiautomator2.tap import tap_uiautomator2


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


def test_uiautomator2_tap_uses_arg_list_and_confirms_clicked() -> None:
    runner = FakeRunner(ProcessResult(0, json.dumps({"ok": True, "clicked": True}), ""))

    result = tap_uiautomator2(
        device_id="RFCN4010FCK",
        x=60.0,
        y=120.0,
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
            "snap_tap.backends.android.uiautomator2.probes",
            "tap",
            "--device",
            "RFCN4010FCK",
            "--x",
            "60.0",
            "--y",
            "120.0",
        ]
    ]


def test_uiautomator2_tap_blocks_malformed_serial_before_subprocess() -> None:
    runner = FakeRunner(ProcessResult(0, "{}", ""))

    result = tap_uiautomator2(
        device_id="bad serial",
        x=1,
        y=2,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "device_offline"
    assert result.attempted is False
    assert runner.calls == []


def test_uiautomator2_tap_timeout_marks_attempted() -> None:
    runner = FakeRunner(exc=ProcessTimeoutError("timeout"))

    result = tap_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_timeout"
    assert result.attempted is True
    assert result.metadata["touch_may_have_occurred"] is True


def test_uiautomator2_tap_malformed_payload_fails() -> None:
    runner = FakeRunner(ProcessResult(0, json.dumps({"ok": True}), ""))

    result = tap_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_probe_failed"
    assert result.attempted is True


def test_driver_tap_module_does_not_create_snapshot_import_cycle() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import snap_tap.snapshots; import snap_tap.backends.android.uiautomator2.tap",
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
