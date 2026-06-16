from __future__ import annotations

import hashlib

from snap_tap.backends.contracts import DriverError
from snap_tap.primitives.models import (
    PRIMITIVE_RECEIPT_SCHEMA_VERSION,
    PrimitiveDriverResult,
    PrimitiveLease,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
    PrimitiveTextRequest,
)
from snap_tap.primitives.proof import (
    execution_status_for_driver,
    normalize_post_action_settle_ms,
    proof_status_for_after,
    status_for_driver_and_proof,
)
from snap_tap.primitives.receipt import new_receipt_id
from snap_tap.targets import TargetResolution


def build_text_receipt(
    *,
    elapsed_ms: float,
    started_at: str,
    finished_at: str,
    device_id: str,
    lease: PrimitiveLease | None,
    request: PrimitiveTextRequest,
    status: str,
    before: PrimitiveSnapshotResult | None,
    fresh: PrimitiveSnapshotResult | None,
    resolution: TargetResolution | None,
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
        operation=request.mode,
        ok=status == "completed",
        status=status,
        device_id=device_id,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_ms=elapsed_ms,
        lease=lease,
        request=text_request_payload(request),
        target_resolution=resolution,
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
        before_snapshot=before.snapshot if before and before.ok else None,
        fresh_snapshot=fresh.snapshot if fresh and fresh.ok else None,
        after_snapshot=after.snapshot if after and after.ok else None,
        after_snapshot_status=_after_status(after, attempted, touched),
        blocking_reason=_blocking_reason(blocking_code, blocking_detail),
        error=error,
    )


def build_blocked_text_target_receipt(
    *,
    elapsed_ms: float,
    started_at: str,
    finished_at: str,
    device_id: str,
    lease: PrimitiveLease,
    request: PrimitiveTextRequest,
    before: PrimitiveSnapshotResult,
    resolution: TargetResolution,
    code: str,
    detail: str,
) -> PrimitiveReceipt:
    return build_text_receipt(
        elapsed_ms=elapsed_ms,
        started_at=started_at,
        finished_at=finished_at,
        device_id=device_id,
        lease=lease,
        request=request,
        status="blocked",
        before=before,
        fresh=before,
        resolution=resolution,
        driver=None,
        after=None,
        blocking_code=code,
        blocking_detail=detail,
        error=DriverError(code=code, detail=detail),
    )


def text_driver_status(
    driver: PrimitiveDriverResult,
    after: PrimitiveSnapshotResult | None,
) -> tuple[str, DriverError | None]:
    return status_for_driver_and_proof(driver, after, proof_required=False)


def text_snapshot_failure_detail(snapshot: PrimitiveSnapshotResult | None) -> str:
    if snapshot is not None and snapshot.error is not None:
        return snapshot.error.detail
    return "Primitive snapshot capture failed."


def text_request_payload(request: PrimitiveTextRequest) -> dict[str, object]:
    return {
        "operation": request.mode,
        "device_id": request.device_id,
        "signature_id": request.signature.signature_id,
        "source_snapshot_id": request.signature.source_snapshot_id,
        "mode": request.mode,
        "text_length": len(request.text) if isinstance(request.text, str) else 0,
        "text_sha256": _text_sha256(request.text),
        "timeout_s": request.timeout_s,
        "lease_timeout_s": request.lease_timeout_s,
        "post_action_settle_ms": normalize_post_action_settle_ms(
            request.post_action_settle_ms
        ),
    }


def _blocking_reason(
    code: str | None,
    detail: str | None,
) -> dict[str, object] | None:
    if code is None:
        return None
    return {"code": code, "detail": detail or code, "touched_phone": False}


def _after_status(
    after: PrimitiveSnapshotResult | None,
    attempted: bool,
    touched: bool,
) -> str:
    if not attempted and not touched:
        return "not_attempted"
    if after is None:
        return "not_attempted"
    if after.ok and after.snapshot is not None:
        return "completed"
    return "failed"


def _text_sha256(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
