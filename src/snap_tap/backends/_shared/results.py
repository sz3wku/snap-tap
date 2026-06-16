from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from snap_tap.backends._shared.errors import DriverError


@dataclass(frozen=True)
class DriverTap:
    ok: bool
    status: str
    device_id: str | None
    backend: str
    operation: str
    checked_at: str
    elapsed_ms: float
    attempted: bool
    confirmed: bool
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: DriverError | None = None


@dataclass(frozen=True)
class DriverText:
    ok: bool
    status: str
    device_id: str | None
    backend: str
    operation: str
    checked_at: str
    elapsed_ms: float
    attempted: bool
    confirmed: bool
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: DriverError | None = None


@dataclass(frozen=True)
class DriverNavigation:
    ok: bool
    status: str
    device_id: str | None
    backend: str
    operation: str
    checked_at: str
    elapsed_ms: float
    attempted: bool
    confirmed: bool
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: DriverError | None = None


@dataclass(frozen=True)
class DriverXmlDump:
    ok: bool
    status: str
    device_id: str | None
    backend: str
    operation: str
    checked_at: str
    elapsed_ms: float
    xml: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    error: DriverError | None = None

    @classmethod
    def success(
        cls,
        *,
        device_id: str,
        backend: str,
        elapsed_ms: float,
        xml: str,
        metadata: Mapping[str, object] | None = None,
    ) -> DriverXmlDump:
        return cls(
            ok=True,
            status="completed",
            device_id=device_id,
            backend=backend,
            operation="dump_xml",
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            xml=xml,
            metadata=metadata or {},
        )

    @classmethod
    def failure(
        cls,
        *,
        backend: str,
        code: str,
        detail: str,
        elapsed_ms: float,
        device_id: str | None = None,
        status: str = "unhealthy",
        metadata: Mapping[str, object] | None = None,
    ) -> DriverXmlDump:
        return cls(
            ok=False,
            status=status,
            device_id=device_id,
            backend=backend,
            operation="dump_xml",
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            metadata=metadata or {},
            error=DriverError(code=code, detail=detail),
        )


class DriverXmlDumper(Protocol):
    backend_name: str

    def dump_xml(self, device_id: str, timeout_s: float = 10.0) -> DriverXmlDump: ...


@dataclass(frozen=True)
class DriverLifecycleResult:
    ok: bool
    status: str
    device_id: str | None
    backend: str
    operation: str
    checked_at: str
    elapsed_ms: float
    metadata: Mapping[str, str] = field(default_factory=dict)
    error: DriverError | None = None

    @classmethod
    def success(
        cls,
        *,
        device_id: str,
        backend: str,
        operation: str,
        elapsed_ms: float,
        metadata: Mapping[str, str] | None = None,
    ) -> DriverLifecycleResult:
        return cls(
            ok=True,
            status="completed",
            device_id=device_id,
            backend=backend,
            operation=operation,
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            metadata=metadata or {},
        )

    @classmethod
    def failure(
        cls,
        *,
        backend: str,
        operation: str,
        code: str,
        detail: str,
        elapsed_ms: float,
        device_id: str | None = None,
        status: str = "unhealthy",
        metadata: Mapping[str, str] | None = None,
    ) -> DriverLifecycleResult:
        return cls(
            ok=False,
            status=status,
            device_id=device_id,
            backend=backend,
            operation=operation,
            checked_at=_utc_now(),
            elapsed_ms=elapsed_ms,
            metadata=metadata or {},
            error=DriverError(code=code, detail=detail),
        )


class DriverLifecycleRunner(Protocol):
    backend_name: str

    def run(
        self,
        *,
        operation: str,
        device_id: str,
        timeout_s: float = 60.0,
    ) -> DriverLifecycleResult: ...


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()

