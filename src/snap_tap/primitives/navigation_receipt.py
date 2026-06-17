from __future__ import annotations

from snap_tap.backends.contracts import DriverError
from snap_tap.primitives.models import (
    PRIMITIVE_RECEIPT_SCHEMA_VERSION,
    PrimitiveDriverResult,
    PrimitiveLease,
    PrimitiveNavigationRequest,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
)
from snap_tap.primitives.navigation_request import navigation_request_payload
from snap_tap.primitives.proof import (
    EXECUTION_COMPLETED,
    EXECUTION_FAILED,
    execution_status_for_driver,
    normalize_post_action_settle_ms,
    proof_status_for_after,
)
from snap_tap.primitives.receipt import new_receipt_id


def build_navigation_receipt(
    *,
    elapsed_ms: float,
    started_at: str,
    finished_at: str,
    device_id: str,
    lease: PrimitiveLease | None,
    request: PrimitiveNavigationRequest,
    status: str,
    before: PrimitiveSnapshotResult | None,
    fresh: PrimitiveSnapshotResult | None,
    driver: PrimitiveDriverResult | None,
    after: PrimitiveSnapshotResult | None,
    blocking_code: str | None = None,
    blocking_detail: str | None = None,
    error: DriverError | None = None,
) -> PrimitiveReceipt:
    attempted = driver.attempted if driver is not None else False
    touched = _touched_phone(driver)
    return PrimitiveReceipt(
        schema_version=PRIMITIVE_RECEIPT_SCHEMA_VERSION,
        receipt_id=new_receipt_id(),
        operation=request.operation,
        ok=status == "completed",
        status=status,
        device_id=device_id,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_ms=elapsed_ms,
        lease=lease,
        request=navigation_request_payload(request),
        target_resolution=None,
        driver_result=driver,
        attempted_touch=attempted,
        touched_phone=touched,
        execution_status=_execution_status(
            request=request,
            status=status,
            driver=driver,
            blocking_code=blocking_code,
        ),
        proof_status=proof_status_for_after(
            after=after,
            proof_requested=_proof_requested(
                request=request,
                attempted=attempted,
                touched=touched,
            ),
            proof_required=_proof_required(request),
        ),
        after_snapshot_required=_proof_required(request),
        post_action_settle_ms=normalize_post_action_settle_ms(
            request.post_action_settle_ms
        ),
        before_snapshot=before.snapshot if before and before.ok else None,
        fresh_snapshot=fresh.snapshot if fresh and fresh.ok else None,
        after_snapshot=after.snapshot if after and after.ok else None,
        after_snapshot_status=_after_status(after),
        blocking_reason=_blocking_reason(blocking_code, blocking_detail),
        error=error,
    )


def _blocking_reason(
    code: str | None,
    detail: str | None,
) -> dict[str, object] | None:
    if code is None:
        return None
    return {"code": code, "detail": detail or code, "touched_phone": False}


def _touched_phone(driver: PrimitiveDriverResult | None) -> bool:
    if driver is None:
        return False
    if driver.metadata.get("touch_may_have_occurred") is False:
        return False
    return bool(
        driver.confirmed or driver.metadata.get("touch_may_have_occurred") is True
    )


def _after_status(after: PrimitiveSnapshotResult | None) -> str:
    if after is None:
        return "not_attempted"
    if after.ok and after.snapshot is not None:
        return "completed"
    return "failed"


def _execution_status(
    *,
    request: PrimitiveNavigationRequest,
    status: str,
    driver: PrimitiveDriverResult | None,
    blocking_code: str | None,
) -> str:
    if driver is not None:
        return execution_status_for_driver(driver)
    if blocking_code is not None:
        return "blocked"
    if request.operation == "wait":
        return (
            EXECUTION_COMPLETED
            if status in {"completed", "partial"}
            else EXECUTION_FAILED
        )
    return "blocked"


def _proof_required(request: PrimitiveNavigationRequest) -> bool:
    return request.operation == "wait"


def _proof_requested(
    *,
    request: PrimitiveNavigationRequest,
    attempted: bool,
    touched: bool,
) -> bool:
    return request.operation == "wait" or attempted or touched
