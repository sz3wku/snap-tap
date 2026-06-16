from __future__ import annotations

from time import perf_counter
from typing import Protocol

from snap_tap.backends.contracts import DriverError, DriverTap
from snap_tap.device.identity import normalize_serial
from snap_tap.primitives.lease import PrimitiveLeaseManager, default_lease_manager
from snap_tap.primitives.models import (
    PRIMITIVE_RECEIPT_SCHEMA_VERSION,
    PrimitiveDriverResult,
    PrimitiveLease,
    PrimitiveLeaseConflict,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
    PrimitiveTapRequest,
)
from snap_tap.primitives.proof import (
    execution_status_for_driver,
    normalize_post_action_settle_ms,
    proof_status_for_after,
    settle_after_driver_action,
    status_for_driver_and_proof,
)
from snap_tap.primitives.receipt import invalid_request_receipt, new_receipt_id, utc_now
from snap_tap.primitives.snapshot_provider import PrimitiveSnapshotProvider
from snap_tap.primitives.target_guard import stale_target_block
from snap_tap.targets import TargetResolution, resolve_target_signature


class PrimitiveTapper(Protocol):
    backend_name: str

    def tap(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        timeout_s: float = 10.0,
    ) -> DriverTap: ...


def resolved_tap(
    request: PrimitiveTapRequest,
    *,
    snapshot_provider: PrimitiveSnapshotProvider,
    tapper: PrimitiveTapper,
    lease_manager: PrimitiveLeaseManager | None = None,
) -> PrimitiveReceipt:
    started = perf_counter()
    started_at = utc_now()
    serial = normalize_serial(request.device_id)
    if serial is None:
        return invalid_request_receipt(
            device_id=None,
            request=_request_payload(request),
            detail="Device serial is required and must be a valid ADB serial.",
            started_at=started_at,
        )
    if request.signature.device_id != serial:
        return invalid_request_receipt(
            device_id=serial,
            request=_request_payload(request),
            detail="Target signature device does not match requested device.",
            started_at=started_at,
        )

    manager = lease_manager or default_lease_manager()
    lease: PrimitiveLease | None = None
    try:
        lease = manager.acquire(
            device_id=serial,
            holder_kind="primitive",
            timeout_s=request.lease_timeout_s,
        )
        before = _capture_snapshot(
            snapshot_provider,
            device_id=serial,
            timeout_s=request.timeout_s,
            failure_code="primitive_resolution_blocked",
            started=started,
        )
        if not before.ok or before.snapshot is None:
            return _receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                status="blocked",
                before=before,
                fresh=before,
                resolution=None,
                driver=None,
                after=None,
                blocking_code="primitive_resolution_blocked",
                blocking_detail=_snapshot_failure_detail(before),
                error=DriverError(
                    code="primitive_resolution_blocked",
                    detail=_snapshot_failure_detail(before),
                ),
            )

        resolution = resolve_target_signature(request.signature, before.snapshot)
        if not resolution.ok or resolution.status != "resolved":
            reason = resolution.blocking_reason
            detail = reason.detail if reason else "Target resolution blocked."
            return _receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                status="blocked",
                before=before,
                fresh=before,
                resolution=resolution,
                driver=None,
                after=None,
                blocking_code="primitive_resolution_blocked",
                blocking_detail=detail,
                error=DriverError(
                    code="primitive_resolution_blocked",
                    detail=detail,
                ),
            )
        target = resolution.resolved_target
        if target is None:
            return _receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                status="blocked",
                before=before,
                fresh=before,
                resolution=resolution,
                driver=None,
                after=None,
                blocking_code="primitive_resolution_blocked",
                blocking_detail="Resolved target was missing.",
                error=DriverError(
                    code="primitive_resolution_blocked",
                    detail="Resolved target was missing.",
                ),
            )
        stale_block = stale_target_block(
            signature=request.signature,
            resolution=resolution,
            fresh_snapshot=before.snapshot,
        )
        if stale_block is not None:
            return _receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                status="blocked",
                before=before,
                fresh=before,
                resolution=resolution,
                driver=None,
                after=None,
                blocking_code=stale_block.code,
                blocking_detail=stale_block.detail,
                error=DriverError(code=stale_block.code, detail=stale_block.detail),
            )

        driver = _tap_safely(
            tapper,
            device_id=serial,
            x=target.bounds.center_x,
            y=target.bounds.center_y,
            timeout_s=request.timeout_s,
            started=started,
        )
        settle_after_driver_action(
            driver,
            settle_ms=request.post_action_settle_ms,
        )
        after = (
            _capture_snapshot(
                snapshot_provider,
                device_id=serial,
                timeout_s=request.timeout_s,
                failure_code="primitive_after_snapshot_failed",
                started=started,
            )
            if driver.attempted or driver.confirmed
            else None
        )
        status, error = status_for_driver_and_proof(
            driver,
            after,
            proof_required=False,
        )
        return _receipt(
            started=started,
            started_at=started_at,
            device_id=serial,
            lease=lease,
            request=request,
            status=status,
            before=before,
            fresh=before,
            resolution=resolution,
            driver=driver,
            after=after,
            error=error,
        )
    except PrimitiveLeaseConflict as exc:
        return _receipt(
            started=started,
            started_at=started_at,
            device_id=serial,
            lease=exc.lease,
            request=request,
            status="blocked",
            before=None,
            fresh=None,
            resolution=None,
            driver=None,
            after=None,
            blocking_code="primitive_lease_conflict",
            blocking_detail=exc.detail,
            error=DriverError(code="primitive_lease_conflict", detail=exc.detail),
        )
    finally:
        if lease is not None:
            manager.release(lease)


def _capture_snapshot(
    provider: PrimitiveSnapshotProvider,
    *,
    device_id: str,
    timeout_s: float,
    failure_code: str,
    started: float,
) -> PrimitiveSnapshotResult:
    try:
        return provider.capture(device_id, timeout_s=timeout_s)
    except Exception as exc:
        return PrimitiveSnapshotResult(
            ok=False,
            status="failed",
            device_id=device_id,
            checked_at=utc_now(),
            elapsed_ms=round((perf_counter() - started) * 1000, 3),
            error=DriverError(
                code=failure_code,
                detail=_exception_detail(exc),
            ),
        )


def _tap_safely(
    tapper: PrimitiveTapper,
    *,
    device_id: str,
    x: float,
    y: float,
    timeout_s: float,
    started: float,
) -> PrimitiveDriverResult:
    try:
        return _primitive_driver_result(
            tapper.tap(device_id=device_id, x=x, y=y, timeout_s=timeout_s)
        )
    except Exception as exc:
        return PrimitiveDriverResult(
            ok=False,
            backend=getattr(tapper, "backend_name", "unknown"),
            operation="tap",
            elapsed_ms=round((perf_counter() - started) * 1000, 3),
            attempted=True,
            confirmed=False,
            checked_at=utc_now(),
            metadata={"touch_may_have_occurred": True},
            error=DriverError(
                code="primitive_driver_failed",
                detail=_exception_detail(exc),
            ),
        )


def _primitive_driver_result(result: DriverTap) -> PrimitiveDriverResult:
    return PrimitiveDriverResult(
        ok=result.ok,
        backend=result.backend,
        operation=result.operation,
        elapsed_ms=result.elapsed_ms,
        attempted=result.attempted,
        confirmed=result.confirmed,
        checked_at=result.checked_at,
        metadata=dict(result.metadata),
        error=result.error,
    )


def _receipt(
    *,
    started: float,
    started_at: str,
    device_id: str,
    lease: PrimitiveLease | None,
    request: PrimitiveTapRequest,
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
        operation="tap",
        ok=status == "completed",
        status=status,
        device_id=device_id,
        started_at=started_at,
        finished_at=utc_now(),
        elapsed_ms=round((perf_counter() - started) * 1000, 3),
        lease=lease,
        request=_request_payload(request),
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


def _request_payload(request: PrimitiveTapRequest) -> dict[str, object]:
    return {
        "operation": "tap",
        "device_id": request.device_id,
        "signature_id": request.signature.signature_id,
        "source_snapshot_id": request.signature.source_snapshot_id,
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


def _snapshot_failure_detail(snapshot: PrimitiveSnapshotResult) -> str:
    if snapshot.error is not None:
        return snapshot.error.detail
    return "Primitive snapshot capture failed."


def _exception_detail(exc: Exception) -> str:
    detail = f"{type(exc).__name__}: {exc}".strip()
    if len(detail) > 300:
        return "Primitive operation failed with oversized error detail."
    return detail
