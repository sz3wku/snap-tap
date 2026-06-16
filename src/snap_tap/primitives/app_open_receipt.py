from __future__ import annotations

from snap_tap.backends.contracts import DriverError
from snap_tap.primitives.app_open_request import (
    app_open_request_payload,
)
from snap_tap.primitives.models import (
    PRIMITIVE_RECEIPT_SCHEMA_VERSION,
    PrimitiveAppOpenRequest,
    PrimitiveDriverResult,
    PrimitiveLease,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
)
from snap_tap.primitives.proof import (
    execution_status_for_driver,
    normalize_post_action_settle_ms,
    proof_status_for_after,
)
from snap_tap.primitives.receipt import new_receipt_id


def build_app_open_receipt(
    *,
    elapsed_ms: float,
    started_at: str,
    finished_at: str,
    device_id: str,
    lease: PrimitiveLease | None,
    request: PrimitiveAppOpenRequest,
    status: str,
    driver: PrimitiveDriverResult | None,
    after: PrimitiveSnapshotResult | None,
    blocking_code: str | None = None,
    blocking_detail: str | None = None,
    error: DriverError | None = None,
) -> PrimitiveReceipt:
    attempted = driver.attempted if driver is not None else False
    touched = bool(
        driver is not None
        and (
            driver.confirmed
            or driver.metadata.get("touch_may_have_occurred") is True
        )
    )
    return PrimitiveReceipt(
        schema_version=PRIMITIVE_RECEIPT_SCHEMA_VERSION,
        receipt_id=new_receipt_id(),
        operation="app_open",
        ok=status == "completed",
        status=status,
        device_id=device_id,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_ms=elapsed_ms,
        lease=lease,
        request=app_open_request_payload(request),
        target_resolution=None,
        driver_result=driver,
        attempted_touch=attempted,
        touched_phone=touched,
        execution_status=execution_status_for_driver(driver),
        proof_status=proof_status_for_after(
            after=after,
            proof_requested=attempted or touched,
            proof_required=False,
        ),
        after_snapshot_required=False,
        post_action_settle_ms=normalize_post_action_settle_ms(
            request.post_action_settle_ms
        ),
        before_snapshot=None,
        fresh_snapshot=None,
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


def _after_status(after: PrimitiveSnapshotResult | None) -> str:
    if after is None:
        return "not_attempted"
    if after.ok and after.snapshot is not None:
        return "completed"
    return "failed"
