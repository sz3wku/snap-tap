from __future__ import annotations

from snap_tap.backends.contracts import (
    DriverAppAwareness,
    DriverError,
    DriverLifecycleResult,
    DriverScreenshot,
)
from snap_tap.cli.output import (
    app_awareness_to_dict,
    error_to_dict,
    lifecycle_to_dict,
    screenshot_to_dict,
)


def test_error_to_dict_keeps_code_detail_and_adds_taxonomy() -> None:
    payload = error_to_dict(
        DriverError(code="driver_unavailable", detail="bridge down")
    )

    assert payload is not None
    assert payload["code"] == "driver_unavailable"
    assert payload["detail"] == "bridge down"
    assert payload["category"] == "driver"
    assert payload["recoverable"] is True
    assert payload["retryable"] is True
    assert "Reinitialize" in str(payload["recovery_hint"])


def test_screenshot_to_dict_exposes_recovery_outside_image_metadata() -> None:
    payload = screenshot_to_dict(
        DriverScreenshot.success(
            device_id="RFCN4010FCK",
            backend="uiautomator2",
            elapsed_ms=1.0,
            image_bytes=b"\x89PNG\r\n\x1a\nfake",
            metadata={
                "format": "png",
                "width": 1,
                "height": 1,
                "byte_length": 12,
                "sha256": "hash",
                "attempt": 2,
                "recovery_attempted": True,
                "recovery_ok": True,
                "recovery_operation": "init",
                "recovery_elapsed_ms": 12.3,
                "recovered_after_failure": "driver_unavailable",
            },
        )
    )

    metadata = payload["metadata"]
    assert isinstance(metadata, dict)
    assert "recovery_attempted" not in metadata
    assert payload["recovery"] == {
        "attempt": 2,
        "recovery_attempted": True,
        "recovery_ok": True,
        "recovery_operation": "init",
        "recovery_elapsed_ms": 12.3,
        "recovered_after_failure": "driver_unavailable",
    }


def test_app_awareness_to_dict_exposes_recovery_without_widening_metadata() -> None:
    payload = app_awareness_to_dict(
        DriverAppAwareness.success(
            device_id="RFCN4010FCK",
            backend="uiautomator2",
            operation="app_current",
            elapsed_ms=1.0,
            metadata={
                "package": "com.example",
                "activity": ".Main",
                "attempt": 2,
                "recovery_attempted": True,
                "recovery_ok": True,
                "recovery_operation": "init",
                "recovery_elapsed_ms": 12.3,
                "recovered_after_failure": "driver_unavailable",
            },
        )
    )

    assert payload["metadata"] == {
        "package": "com.example",
        "activity": ".Main",
    }
    assert payload["recovery"] == {
        "attempt": 2,
        "recovery_attempted": True,
        "recovery_ok": True,
        "recovery_operation": "init",
        "recovery_elapsed_ms": 12.3,
        "recovered_after_failure": "driver_unavailable",
    }


def test_lifecycle_to_dict_whitelists_public_metadata() -> None:
    payload = lifecycle_to_dict(
        DriverLifecycleResult.success(
            device_id="RFCN4010FCK",
            backend="uiautomator2",
            operation="doctor",
            elapsed_ms=1.0,
            metadata={
                "returncode": "0",
                "timeout_s": "3.0",
                "stdout_present": "true",
                "stderr_present": "false",
                "stdout": "secret stdout",
                "stderr": "secret stderr",
            },
        )
    )

    assert payload["metadata"] == {
        "returncode": "0",
        "timeout_s": "3.0",
        "stdout_present": "true",
        "stderr_present": "false",
    }
