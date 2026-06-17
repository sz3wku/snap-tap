from __future__ import annotations

from time import sleep

from snap_tap.backends.contracts import DriverError
from snap_tap.primitives.models import (
    DEFAULT_POST_ACTION_SETTLE_MS,
    MAX_POST_ACTION_SETTLE_MS,
    MIN_POST_ACTION_SETTLE_MS,
    PrimitiveDriverResult,
    PrimitiveSnapshotResult,
)

EXECUTION_BLOCKED = "blocked"
EXECUTION_COMPLETED = "completed"
EXECUTION_FAILED = "failed"
EXECUTION_UNKNOWN_AFTER_TIMEOUT = "unknown_after_timeout"

PROOF_NOT_REQUESTED = "not_requested"
PROOF_COMPLETED = "completed"
PROOF_UNAVAILABLE = "unavailable"
PROOF_REQUIRED_FAILED = "required_failed"

REAL_SETTLE_BACKENDS = {"uiautomator2"}
PUBLIC_DRIVER_FAILURE_CODES = {
    "secure_keyguard_required",
    "unlock_failed",
    "wake_failed",
}


def normalize_post_action_settle_ms(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_POST_ACTION_SETTLE_MS
    return max(MIN_POST_ACTION_SETTLE_MS, min(MAX_POST_ACTION_SETTLE_MS, value))


def settle_after_driver_action(
    driver: PrimitiveDriverResult, *, settle_ms: int
) -> None:
    normalized = normalize_post_action_settle_ms(settle_ms)
    if normalized <= 0 or not (driver.attempted or driver.confirmed):
        return
    if driver.backend not in REAL_SETTLE_BACKENDS:
        return
    sleep(normalized / 1000)


def execution_status_for_driver(driver: PrimitiveDriverResult | None) -> str:
    if driver is None:
        return EXECUTION_BLOCKED
    if driver.ok and driver.confirmed:
        return EXECUTION_COMPLETED
    if driver.error is not None and driver.error.code == "driver_timeout":
        return EXECUTION_UNKNOWN_AFTER_TIMEOUT
    return EXECUTION_FAILED


def proof_status_for_after(
    *,
    after: PrimitiveSnapshotResult | None,
    proof_requested: bool,
    proof_required: bool,
) -> str:
    if not proof_requested:
        return PROOF_NOT_REQUESTED
    if after is not None and after.ok and after.snapshot is not None:
        return PROOF_COMPLETED
    return PROOF_REQUIRED_FAILED if proof_required else PROOF_UNAVAILABLE


def status_for_driver_and_proof(
    driver: PrimitiveDriverResult,
    after: PrimitiveSnapshotResult | None,
    *,
    proof_required: bool,
) -> tuple[str, DriverError | None]:
    if driver.ok and not driver.confirmed:
        return (
            "failed",
            DriverError(
                code="primitive_false_success",
                detail=f"Driver reported ok without confirmed {driver.operation}.",
            ),
        )
    if not driver.ok:
        code = "primitive_driver_failed"
        if driver.error is not None and driver.error.code == "driver_timeout":
            code = "primitive_driver_timeout"
        elif driver.error is not None and driver.error.code == "driver_unavailable":
            code = "primitive_driver_unavailable"
        elif (
            driver.error is not None
            and driver.error.code in PUBLIC_DRIVER_FAILURE_CODES
        ):
            code = driver.error.code
        detail = driver.error.detail if driver.error else "Driver primitive failed."
        return "failed", DriverError(code=code, detail=detail)
    if proof_required and (after is None or not after.ok or after.snapshot is None):
        return (
            "partial",
            DriverError(
                code="primitive_after_snapshot_failed",
                detail=(
                    snapshot_failure_detail(after)
                    if after is not None
                    else "After snapshot was not attempted."
                ),
            ),
        )
    return "completed", None


def snapshot_failure_detail(snapshot: PrimitiveSnapshotResult | None) -> str:
    if snapshot is not None and snapshot.error is not None:
        return snapshot.error.detail
    return "Primitive snapshot capture failed."
