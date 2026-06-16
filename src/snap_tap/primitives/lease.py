from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from uuid import uuid4

from snap_tap.primitives.models import PrimitiveLease, PrimitiveLeaseConflict

DEFAULT_PRIMITIVE_LEASE_ROOT = (
    Path(__file__).resolve().parents[3] / "temp" / "mobile-primitives" / "leases"
)


class PrimitiveLeaseManager:
    def __init__(
        self,
        *,
        lock_root: Path | None = DEFAULT_PRIMITIVE_LEASE_ROOT,
        in_memory_only: bool = False,
    ) -> None:
        self._lock = Lock()
        self._active: dict[str, PrimitiveLease] = {}
        self._lock_root = None if in_memory_only else lock_root

    def acquire(
        self,
        *,
        device_id: str,
        holder_kind: str = "primitive",
        timeout_s: float = 30.0,
    ) -> PrimitiveLease:
        if timeout_s <= 0:
            raise ValueError("Primitive lease timeout must be positive.")
        now = datetime.now(UTC)
        with self._lock:
            current = self._active.get(device_id)
            if current is not None and _parse_utc(current.expires_at) > now:
                raise PrimitiveLeaseConflict(
                    detail="A primitive operation lease is already active.",
                    lease=current,
                )
            if current is not None:
                self._active.pop(device_id, None)
            lease = PrimitiveLease(
                device_id=device_id,
                acquired=True,
                holder_kind=holder_kind,
                acquired_at=now.isoformat(),
                expires_at=(now + timedelta(seconds=timeout_s)).isoformat(),
                timeout_s=timeout_s,
                lease_id=f"primitive_lease:{uuid4()}",
            )
            self._acquire_file_lock(lease)
            self._active[device_id] = lease
            return lease

    def release(self, lease: PrimitiveLease) -> None:
        with self._lock:
            current = self._active.get(lease.device_id)
            if current is not None and current.lease_id == lease.lease_id:
                self._active.pop(lease.device_id, None)
            self._release_file_lock(lease)

    def _acquire_file_lock(self, lease: PrimitiveLease) -> None:
        if self._lock_root is None:
            return
        path = _lease_path(self._lock_root, lease.device_id)
        payload = _lease_payload(lease)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PrimitiveLeaseConflict(
                detail="Could not prepare primitive operation lease.",
            ) from exc
        for _ in range(2):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                current = _read_file_lease(path)
                raise PrimitiveLeaseConflict(
                    detail="A primitive operation lease is already active.",
                    lease=current,
                ) from exc
            except OSError as exc:
                raise PrimitiveLeaseConflict(
                    detail="Could not acquire primitive operation lease.",
                ) from exc
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, sort_keys=True)
                    handle.write("\n")
                return
            except OSError as exc:
                _unlink_file_lock(path)
                raise PrimitiveLeaseConflict(
                    detail="Could not write primitive operation lease.",
                ) from exc
        raise PrimitiveLeaseConflict(
            detail="A primitive operation lease is already active.",
            lease=_read_file_lease(path),
        )

    def _release_file_lock(self, lease: PrimitiveLease) -> None:
        if self._lock_root is None:
            return
        path = _lease_path(self._lock_root, lease.device_id)
        current = _read_file_lease(path)
        if current is not None and current.lease_id == lease.lease_id:
            _unlink_file_lock(path)


_GLOBAL_LEASE_MANAGER = PrimitiveLeaseManager()


def default_lease_manager() -> PrimitiveLeaseManager:
    return _GLOBAL_LEASE_MANAGER


def _lease_path(root: Path, device_id: str) -> Path:
    digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
    return root / f"{digest}.json"


def _lease_payload(lease: PrimitiveLease) -> dict[str, object]:
    return {
        "device_id": lease.device_id,
        "acquired": lease.acquired,
        "holder_kind": lease.holder_kind,
        "acquired_at": lease.acquired_at,
        "expires_at": lease.expires_at,
        "timeout_s": lease.timeout_s,
        "lease_id": lease.lease_id,
    }


def _read_file_lease(path: Path) -> PrimitiveLease | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return PrimitiveLease(
            device_id=_required_text(payload.get("device_id")),
            acquired=_required_bool(payload.get("acquired")),
            holder_kind=_required_text(payload.get("holder_kind")),
            acquired_at=_required_text(payload.get("acquired_at")),
            expires_at=_required_text(payload.get("expires_at")),
            timeout_s=_required_number(payload.get("timeout_s")),
            lease_id=_required_text(payload.get("lease_id")),
        )
    except (TypeError, ValueError):
        return None


def _unlink_file_lock(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _required_text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Expected non-empty text.")
    return value


def _required_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("Expected bool.")
    return value


def _required_number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("Expected number.")
    return float(value)
