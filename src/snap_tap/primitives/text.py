from __future__ import annotations

from time import perf_counter
from typing import Protocol

from snap_tap.backends.android.uiautomator2.text import TEXT_INPUT_MODE, TEXT_MODES
from snap_tap.backends.contracts import DriverError, DriverText
from snap_tap.device.identity import normalize_serial
from snap_tap.primitives.lease import PrimitiveLeaseManager, default_lease_manager
from snap_tap.primitives.models import (
    PrimitiveDriverResult,
    PrimitiveLease,
    PrimitiveLeaseConflict,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
    PrimitiveTextRequest,
)
from snap_tap.primitives.proof import settle_after_driver_action
from snap_tap.primitives.receipt import invalid_request_receipt, utc_now
from snap_tap.primitives.snapshot_provider import PrimitiveSnapshotProvider
from snap_tap.primitives.target_guard import stale_target_block
from snap_tap.primitives.text_receipt import (
    build_blocked_text_target_receipt,
    build_text_receipt,
    text_driver_status,
    text_request_payload,
    text_snapshot_failure_detail,
)
from snap_tap.semantics import SemanticRole
from snap_tap.targets import SnapshotTarget, TargetResolution, resolve_target_signature


class PrimitiveTexter(Protocol):
    backend_name: str

    def input_text(
        self,
        *,
        device_id: str,
        x: float,
        y: float,
        text: str,
        mode: str,
        timeout_s: float = 10.0,
    ) -> DriverText: ...


def resolved_text(
    request: PrimitiveTextRequest,
    *,
    snapshot_provider: PrimitiveSnapshotProvider,
    texter: PrimitiveTexter,
    lease_manager: PrimitiveLeaseManager | None = None,
) -> PrimitiveReceipt:
    started = perf_counter()
    started_at = utc_now()
    serial = normalize_serial(request.device_id)
    if serial is None:
        return invalid_request_receipt(
            device_id=None,
            request=text_request_payload(request),
            detail="Device serial is required and must be a valid ADB serial.",
            operation=_safe_operation(request.mode),
            started_at=started_at,
        )
    if request.mode not in TEXT_MODES:
        return invalid_request_receipt(
            device_id=serial,
            request=text_request_payload(request),
            detail="Text primitive mode must be input or replace_text.",
            operation=_safe_operation(request.mode),
            started_at=started_at,
        )
    if _normalized_text(request.text) is None:
        return invalid_request_receipt(
            device_id=serial,
            request=text_request_payload(request),
            detail="Text payload must be non-empty normalized text.",
            operation=request.mode,
            started_at=started_at,
        )
    if request.signature.device_id != serial:
        return invalid_request_receipt(
            device_id=serial,
            request=text_request_payload(request),
            detail="Target signature device does not match requested device.",
            operation=request.mode,
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
                blocking_detail=text_snapshot_failure_detail(before),
                error=DriverError(
                    code="primitive_resolution_blocked",
                    detail=text_snapshot_failure_detail(before),
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
            return _blocked_target_receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                before=before,
                resolution=resolution,
                detail="Resolved target was missing.",
            )
        stale_block = stale_target_block(
            signature=request.signature,
            resolution=resolution,
            fresh_snapshot=before.snapshot,
        )
        if stale_block is not None:
            return _blocked_target_receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                before=before,
                resolution=resolution,
                code=stale_block.code,
                detail=stale_block.detail,
            )
        if not _is_input_target(target):
            return _blocked_target_receipt(
                started=started,
                started_at=started_at,
                device_id=serial,
                lease=lease,
                request=request,
                before=before,
                resolution=resolution,
                detail="Resolved target is not an input-like editable target.",
            )

        driver = _text_safely(
            texter,
            device_id=serial,
            x=target.bounds.center_x,
            y=target.bounds.center_y,
            text=request.text,
            mode=request.mode,
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
        status, error = text_driver_status(driver, after)
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


def _blocked_target_receipt(
    *,
    started: float,
    started_at: str,
    device_id: str,
    lease: PrimitiveLease,
    request: PrimitiveTextRequest,
    before: PrimitiveSnapshotResult,
    resolution: TargetResolution,
    detail: str,
    code: str = "primitive_target_not_input",
) -> PrimitiveReceipt:
    return build_blocked_text_target_receipt(
        elapsed_ms=round((perf_counter() - started) * 1000, 3),
        started_at=started_at,
        finished_at=utc_now(),
        device_id=device_id,
        lease=lease,
        request=request,
        before=before,
        resolution=resolution,
        code=code,
        detail=detail,
    )


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


def _text_safely(
    texter: PrimitiveTexter,
    *,
    device_id: str,
    x: float,
    y: float,
    text: str,
    mode: str,
    timeout_s: float,
    started: float,
) -> PrimitiveDriverResult:
    try:
        return _primitive_driver_result(
            texter.input_text(
                device_id=device_id,
                x=x,
                y=y,
                text=text,
                mode=mode,
                timeout_s=timeout_s,
            )
        )
    except Exception as exc:
        return PrimitiveDriverResult(
            ok=False,
            backend=getattr(texter, "backend_name", "unknown"),
            operation=mode,
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


def _primitive_driver_result(result: DriverText) -> PrimitiveDriverResult:
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
    return build_text_receipt(
        elapsed_ms=round((perf_counter() - started) * 1000, 3),
        started_at=started_at,
        finished_at=utc_now(),
        device_id=device_id,
        lease=lease,
        request=request,
        status=status,
        before=before,
        fresh=fresh,
        resolution=resolution,
        driver=driver,
        after=after,
        blocking_code=blocking_code,
        blocking_detail=blocking_detail,
        error=error,
    )


def _is_input_target(target: SnapshotTarget) -> bool:
    return target.role is SemanticRole.INPUT and target.enabled


def _safe_operation(mode: str) -> str:
    return mode if mode in TEXT_MODES else TEXT_INPUT_MODE


def _normalized_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if not value or not value.strip() or len(value) > 4096:
        return None
    if "\x00" in value:
        return None
    return value


def _exception_detail(exc: Exception) -> str:
    detail = f"{type(exc).__name__}: {exc}".strip()
    if len(detail) > 300:
        return "Primitive operation failed with oversized error detail."
    return detail
