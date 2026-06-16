from __future__ import annotations

from pathlib import Path

from snap_tap.backends.contracts import (
    ERROR_SPECS,
    DriverError,
    error_spec,
    is_driver_recoverable,
)


def test_driver_error_populates_taxonomy_fields() -> None:
    error = DriverError(code="driver_unavailable", detail="bridge down")

    assert error.category == "driver"
    assert error.recoverable is True
    assert error.retryable is True
    assert "Reinitialize" in (error.recovery_hint or "")


def test_timeout_is_not_recoverable() -> None:
    assert error_spec("driver_timeout").category == "timeout"
    assert is_driver_recoverable("driver_timeout") is False


def test_primitive_target_stale_is_structured_primitive_error() -> None:
    error = DriverError(code="primitive_target_stale", detail="target drifted")

    assert error.category == "primitive"
    assert error.recoverable is False
    assert error.retryable is False
    assert "fresh snapshot" in (error.recovery_hint or "")


def test_latest_snap_source_errors_are_structured_target_source_errors() -> None:
    error = DriverError(
        code="latest_snap_source_target_not_tappable",
        detail="not tappable",
    )

    assert error.category == "target_source"
    assert error.recoverable is False
    assert error.retryable is False
    assert "tap target" in (error.recovery_hint or "")


def test_unknown_error_is_not_recoverable() -> None:
    error = DriverError(code="future_code", detail="unknown")

    assert error.category == "unknown"
    assert error.recoverable is False
    assert error.retryable is False


def test_driver_contract_lists_all_public_error_specs() -> None:
    contract = Path("docs/contracts/driver-backend-v1.md").read_text(encoding="utf-8")

    missing = [code for code in ERROR_SPECS if f"`{code}`" not in contract]

    assert missing == []
