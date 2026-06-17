from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from snap_tap.backends.contracts import DriverError
from snap_tap.semantics import SemanticSnapshot
from snap_tap.targets import TargetResolution, TargetSignature

PRIMITIVE_RECEIPT_SCHEMA_VERSION = "primitive_receipt.v1"
DEFAULT_POST_ACTION_SETTLE_MS = 500
MAX_POST_ACTION_SETTLE_MS = 10000
MIN_POST_ACTION_SETTLE_MS = 0


@dataclass(frozen=True)
class PrimitiveLease:
    device_id: str
    acquired: bool
    holder_kind: str
    acquired_at: str
    expires_at: str
    timeout_s: float
    lease_id: str


@dataclass(frozen=True)
class PrimitiveTapRequest:
    device_id: str
    signature: TargetSignature
    timeout_s: float = 10.0
    lease_timeout_s: float = 30.0
    post_action_settle_ms: int = DEFAULT_POST_ACTION_SETTLE_MS


@dataclass(frozen=True)
class PrimitiveTextRequest:
    device_id: str
    signature: TargetSignature
    text: str
    mode: str
    timeout_s: float = 10.0
    lease_timeout_s: float = 30.0
    post_action_settle_ms: int = DEFAULT_POST_ACTION_SETTLE_MS


@dataclass(frozen=True)
class PrimitiveNavigationRequest:
    device_id: str
    operation: str
    direction: str | None = None
    distance_ratio: float = 0.55
    duration_ms: int = 300
    seconds: float = 1.0
    timeout_s: float = 10.0
    lease_timeout_s: float = 30.0
    post_action_settle_ms: int = DEFAULT_POST_ACTION_SETTLE_MS


@dataclass(frozen=True)
class PrimitiveAppOpenRequest:
    device_id: str
    query: str
    package: str
    activity: str | None = None
    timeout_s: float = 10.0
    lease_timeout_s: float = 30.0
    post_action_settle_ms: int = DEFAULT_POST_ACTION_SETTLE_MS


@dataclass(frozen=True)
class PrimitiveDriverResult:
    ok: bool
    backend: str
    operation: str
    elapsed_ms: float
    attempted: bool
    confirmed: bool
    checked_at: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: DriverError | None = None


@dataclass(frozen=True)
class PrimitiveSnapshotResult:
    ok: bool
    status: str
    device_id: str | None
    checked_at: str
    elapsed_ms: float
    snapshot: SemanticSnapshot | None = None
    backend: str | None = None
    error: DriverError | None = None


@dataclass(frozen=True)
class PrimitiveReceipt:
    schema_version: str
    receipt_id: str
    operation: str
    ok: bool
    status: str
    device_id: str | None
    started_at: str
    finished_at: str
    elapsed_ms: float
    lease: PrimitiveLease | None
    request: Mapping[str, object]
    target_resolution: TargetResolution | None
    driver_result: PrimitiveDriverResult | None
    attempted_touch: bool
    touched_phone: bool
    execution_status: str
    proof_status: str
    after_snapshot_required: bool
    post_action_settle_ms: int
    before_snapshot: SemanticSnapshot | None
    fresh_snapshot: SemanticSnapshot | None
    after_snapshot: SemanticSnapshot | None
    after_snapshot_status: str
    blocking_reason: Mapping[str, object] | None = None
    error: DriverError | None = None


class PrimitiveLeaseConflict(Exception):
    def __init__(self, *, detail: str, lease: PrimitiveLease | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.lease = lease


class PrimitiveRequestError(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
