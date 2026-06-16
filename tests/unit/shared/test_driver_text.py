from __future__ import annotations

from collections.abc import Sequence
import json

from snap_tap.backends.android.uiautomator2.process_runner import ProcessResult, ProcessRunner, ProcessTimeoutError
from snap_tap.backends.android.uiautomator2.text import TEXT_INPUT_MODE, TEXT_REPLACE_MODE, text_uiautomator2


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


def test_input_text_uses_arg_list_and_confirms_text_applied() -> None:
    runner = FakeRunner(
        ProcessResult(0, json.dumps({"ok": True, "text_applied": True}), "")
    )

    result = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=60.0,
        y=120.0,
        text="hakar smoke",
        mode=TEXT_INPUT_MODE,
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
            "input_text",
            "--device",
            "RFCN4010FCK",
            "--x",
            "60.0",
            "--y",
            "120.0",
            "--text",
            "hakar smoke",
        ]
    ]


def test_replace_text_uses_explicit_probe_operation() -> None:
    runner = FakeRunner(
        ProcessResult(0, json.dumps({"ok": True, "text_applied": True}), "")
    )

    result = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        text="new text",
        mode=TEXT_REPLACE_MODE,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is True
    assert runner.calls[0][3] == "replace_text"
    assert runner.calls[0][-1] == "new text"


def test_input_text_blocks_malformed_serial_before_subprocess() -> None:
    runner = FakeRunner(ProcessResult(0, "{}", ""))

    result = text_uiautomator2(
        device_id="bad serial",
        x=1,
        y=2,
        text="hello",
        mode=TEXT_INPUT_MODE,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "device_offline"
    assert result.attempted is False
    assert runner.calls == []


def test_input_text_blocks_empty_text_before_subprocess() -> None:
    runner = FakeRunner(ProcessResult(0, "{}", ""))

    result = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        text="",
        mode=TEXT_INPUT_MODE,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "input_failed"
    assert result.attempted is False
    assert runner.calls == []


def test_input_text_timeout_marks_possible_touch() -> None:
    runner = FakeRunner(exc=ProcessTimeoutError("timeout"))

    result = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        text="hello",
        mode=TEXT_INPUT_MODE,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_timeout"
    assert result.attempted is True
    assert result.metadata["touch_may_have_occurred"] is True


def test_input_text_malformed_payload_fails() -> None:
    runner = FakeRunner(ProcessResult(0, json.dumps({"ok": True}), ""))

    result = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        text="hello",
        mode=TEXT_INPUT_MODE,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "driver_probe_failed"
    assert result.attempted is True
    assert result.metadata["touch_may_have_occurred"] is True


def test_input_text_non_json_child_failure_is_possible_touch() -> None:
    runner = FakeRunner(ProcessResult(1, "not json", ""))

    result = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        text="hello",
        mode=TEXT_INPUT_MODE,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "input_failed"
    assert result.attempted is True
    assert result.metadata["touch_may_have_occurred"] is True


def test_input_text_probe_false_confirmation_is_not_confirmed() -> None:
    runner = FakeRunner(
        ProcessResult(0, json.dumps({"ok": True, "text_applied": False}), "")
    )

    result = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        text="hello",
        mode=TEXT_INPUT_MODE,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is True
    assert result.attempted is True
    assert result.confirmed is False


def test_input_text_probe_metadata_is_whitelisted() -> None:
    runner = FakeRunner(
        ProcessResult(
            0,
            json.dumps(
                {
                    "ok": True,
                    "text_applied": True,
                    "metadata": {
                        "after_text_length": 12,
                        "input_method": "set_input_ime",
                        "stage": "after_verify",
                        "text_return": "secret payload",
                        "arbitrary": "secret payload",
                    },
                }
            ),
            "",
        )
    )

    result = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        text="secret payload",
        mode=TEXT_INPUT_MODE,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is True
    assert result.metadata["after_text_length"] == 12
    assert result.metadata["input_method"] == "set_input_ime"
    assert result.metadata["stage"] == "after_verify"
    assert "text_return" not in result.metadata
    assert "arbitrary" not in result.metadata
    assert "secret payload" not in str(result.metadata)


def test_input_text_probe_failure_redacts_text_and_preserves_possible_touch() -> None:
    runner = FakeRunner(
        ProcessResult(
            1,
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "input_failed",
                        "detail": "send_keys failed with secret payload",
                    },
                    "metadata": {
                        "stage": "send_text",
                        "text_return": "secret payload",
                        "text_length": 14,
                        "touch_may_have_occurred": True,
                    },
                }
            ),
            "",
        )
    )

    result = text_uiautomator2(
        device_id="RFCN4010FCK",
        x=1,
        y=2,
        text="secret payload",
        mode=TEXT_INPUT_MODE,
        process_runner=runner,
        python_executable="python",
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "input_failed"
    assert "secret payload" not in result.error.detail
    assert result.metadata["touch_may_have_occurred"] is True
    assert result.metadata["stage"] == "send_text"
    assert "text_return" not in result.metadata
