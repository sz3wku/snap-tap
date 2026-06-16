from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

from snap_tap.backends.contracts import DriverError
from snap_tap.primitives.models import (
    PRIMITIVE_RECEIPT_SCHEMA_VERSION,
    PrimitiveDriverResult,
    PrimitiveLease,
    PrimitiveReceipt,
)
from snap_tap.semantics import SemanticSnapshot
from snap_tap.snapshots import SnapshotArtifactRef
from snap_tap.targets import TargetResolution, target_resolution_to_dict


def new_receipt_id() -> str:
    return f"primitive_receipt:{uuid4()}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def primitive_receipt_to_dict(receipt: PrimitiveReceipt) -> dict[str, object]:
    return {
        "schema_version": receipt.schema_version,
        "receipt_id": receipt.receipt_id,
        "operation": receipt.operation,
        "ok": receipt.ok,
        "status": receipt.status,
        "device_id": receipt.device_id,
        "started_at": receipt.started_at,
        "finished_at": receipt.finished_at,
        "elapsed_ms": receipt.elapsed_ms,
        "lease": _lease_to_dict(receipt.lease),
        "request": dict(receipt.request),
        "target_resolution": _resolution_to_dict(receipt.target_resolution),
        "driver_result": _driver_result_to_dict(receipt.driver_result),
        "attempted_touch": receipt.attempted_touch,
        "touched_phone": receipt.touched_phone,
        "execution_status": receipt.execution_status,
        "proof_status": receipt.proof_status,
        "after_snapshot_required": receipt.after_snapshot_required,
        "post_action_settle_ms": receipt.post_action_settle_ms,
        "before_snapshot": _snapshot_to_dict(receipt.before_snapshot),
        "fresh_snapshot": _snapshot_to_dict(receipt.fresh_snapshot),
        "after_snapshot": _snapshot_to_dict(receipt.after_snapshot),
        "after_snapshot_status": receipt.after_snapshot_status,
        "blocking_reason": _optional_mapping(receipt.blocking_reason),
        "error": _error_to_dict(receipt.error),
    }


def invalid_request_receipt(
    *,
    device_id: str | None,
    request: Mapping[str, object],
    code: str = "primitive_invalid_request",
    detail: str,
    operation: str = "tap",
    started_at: str | None = None,
) -> PrimitiveReceipt:
    started = started_at or utc_now()
    finished = utc_now()
    error = DriverError(code=code, detail=detail)
    return PrimitiveReceipt(
        schema_version=PRIMITIVE_RECEIPT_SCHEMA_VERSION,
        receipt_id=new_receipt_id(),
        operation=operation,
        ok=False,
        status="blocked",
        device_id=device_id,
        started_at=started,
        finished_at=finished,
        elapsed_ms=0.0,
        lease=None,
        request=dict(request),
        target_resolution=None,
        driver_result=None,
        attempted_touch=False,
        touched_phone=False,
        execution_status="blocked",
        proof_status="not_requested",
        after_snapshot_required=False,
        post_action_settle_ms=0,
        before_snapshot=None,
        fresh_snapshot=None,
        after_snapshot=None,
        after_snapshot_status="not_attempted",
        blocking_reason={"code": code, "detail": detail, "touched_phone": False},
        error=error,
    )


def _lease_to_dict(lease: PrimitiveLease | None) -> dict[str, object] | None:
    if lease is None:
        return None
    return {
        "device_id": lease.device_id,
        "acquired": lease.acquired,
        "holder_kind": lease.holder_kind,
        "acquired_at": lease.acquired_at,
        "expires_at": lease.expires_at,
        "timeout_s": lease.timeout_s,
    }


def _resolution_to_dict(
    resolution: TargetResolution | None,
) -> dict[str, object] | None:
    if resolution is None:
        return None
    return target_resolution_to_dict(resolution)


def _driver_result_to_dict(
    result: PrimitiveDriverResult | None,
) -> dict[str, object] | None:
    if result is None:
        return None
    return {
        "ok": result.ok,
        "backend": result.backend,
        "operation": result.operation,
        "elapsed_ms": result.elapsed_ms,
        "attempted": result.attempted,
        "confirmed": result.confirmed,
        "checked_at": result.checked_at,
        "metadata": _safe_metadata(result.metadata),
        "error": _error_to_dict(result.error),
    }


def _snapshot_to_dict(snapshot: SemanticSnapshot | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "schema_version": snapshot.schema_version,
        "snapshot_id": snapshot.snapshot_id,
        "device_id": snapshot.device_id,
        "captured_at": snapshot.captured_at,
        "refs": {
            name: _ref_to_dict(ref)
            for name, ref in snapshot.refs.items()
            if name in {"xml", "screenshot", "manifest"}
        },
    }


def _ref_to_dict(ref: SnapshotArtifactRef) -> dict[str, object]:
    return {
        "path": ref.path,
        "sha256": ref.sha256,
        "byte_length": ref.byte_length,
        "metadata": _safe_metadata(ref.metadata),
    }


def _error_to_dict(error: DriverError | None) -> dict[str, object] | None:
    if error is None:
        return None
    return {
        "code": error.code,
        "detail": error.detail,
        "category": error.category,
        "recoverable": error.recoverable,
        "retryable": error.retryable,
        "recovery_hint": error.recovery_hint,
    }


def _optional_mapping(value: Mapping[str, object] | None) -> dict[str, object] | None:
    if value is None:
        return None
    return dict(value)


def _safe_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    return {
        str(key): value
        for key, value in metadata.items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }
