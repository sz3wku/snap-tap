from __future__ import annotations

from time import perf_counter
from typing import Protocol

from snap_tap.device.identity import normalize_serial
from snap_tap.backends.contracts import DriverAppOpen, DriverError
from snap_tap.primitives.app_open_receipt import build_app_open_receipt
from snap_tap.primitives.app_open_request import (
    app_open_request_payload,
    invalid_app_open_request_detail,
)
from snap_tap.primitives.lease import PrimitiveLeaseManager, default_lease_manager
from snap_tap.primitives.models import (
    PrimitiveAppOpenRequest,
    PrimitiveDriverResult,
    PrimitiveLease,
    PrimitiveLeaseConflict,
    PrimitiveReceipt,
    PrimitiveSnapshotResult,
)
from snap_tap.primitives.navigation_snapshot import (
    capture_navigation_snapshot,
    exception_detail,
)
from snap_tap.primitives.proof import settle_after_driver_action, status_for_driver_and_proof
from snap_tap.primitives.receipt import invalid_request_receipt, utc_now
from snap_tap.primitives.snapshot_provider import PrimitiveSnapshotProvider


class PrimitiveAppOpener(Protocol):
    backend_name: str

    def open_app(
        self,
        *,
        device_id: str,
        package: str,
        activity: str | None = None,
        timeout_s: float = 10.0,
    ) -> DriverAppOpen: ...


def app_open_primitive(
    request: PrimitiveAppOpenRequest,
    *,
    snapshot_provider: PrimitiveSnapshotProvider,
    opener: PrimitiveAppOpener | None = None,
    lease_manager: PrimitiveLeaseManager | None = None,
) -> PrimitiveReceipt:
    started = perf_counter()
    started_at = utc_now()
    serial = normalize_serial(request.device_id)
    invalid_detail = invalid_app_open_request_detail(request, serial)
    if invalid_detail is not None:
        return invalid_request_receipt(
            device_id=serial,
            request=app_open_request_payload(request),
            detail=invalid_detail,
            operation="app_open",
            started_at=started_at,
        )
    assert serial is not None

    manager = lease_manager or default_lease_manager()
    lease: PrimitiveLease | None = None
    try:
        lease = manager.acquire(
            device_id=serial,
            holder_kind="primitive",
            timeout_s=request.lease_timeout_s,
        )
        driver = _run_driver(
            request,
            device_id=serial,
            opener=opener,
            started=started,
        )
        settle_after_driver_action(
            driver,
            settle_ms=request.post_action_settle_ms,
        )
        after = (
            capture_navigation_snapshot(
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
            driver=None,
            after=None,
            blocking_code="primitive_lease_conflict",
            blocking_detail=exc.detail,
            error=DriverError(code="primitive_lease_conflict", detail=exc.detail),
        )
    finally:
        if lease is not None:
            manager.release(lease)


def _run_driver(
    request: PrimitiveAppOpenRequest,
    *,
    device_id: str,
    opener: PrimitiveAppOpener | None,
    started: float,
) -> PrimitiveDriverResult:
    if opener is None:
        from snap_tap.backends.android.uiautomator2.app_lifecycle import (
            Uiautomator2AppLifecycle,
        )

        opener = Uiautomator2AppLifecycle()
    try:
        return _primitive_driver_result(
            opener.open_app(
                device_id=device_id,
                package=request.package,
                activity=request.activity,
                timeout_s=request.timeout_s,
            )
        )
    except Exception as exc:
        return PrimitiveDriverResult(
            ok=False,
            backend=getattr(opener, "backend_name", "unknown"),
            operation="app_open",
            elapsed_ms=round((perf_counter() - started) * 1000, 3),
            attempted=True,
            confirmed=False,
            checked_at=utc_now(),
            metadata={"touch_may_have_occurred": True},
            error=DriverError(
                code="primitive_driver_failed",
                detail=exception_detail(exc),
            ),
        )


def _primitive_driver_result(result: DriverAppOpen) -> PrimitiveDriverResult:
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
    request: PrimitiveAppOpenRequest,
    status: str,
    driver: PrimitiveDriverResult | None,
    after: PrimitiveSnapshotResult | None,
    blocking_code: str | None = None,
    blocking_detail: str | None = None,
    error: DriverError | None = None,
) -> PrimitiveReceipt:
    return build_app_open_receipt(
        elapsed_ms=round((perf_counter() - started) * 1000, 3),
        started_at=started_at,
        finished_at=utc_now(),
        status=status,
        device_id=device_id,
        lease=lease,
        request=request,
        driver=driver,
        after=after,
        blocking_code=blocking_code,
        blocking_detail=blocking_detail,
        error=error,
    )
