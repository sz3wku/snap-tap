from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Any
import sys

from snap_tap.device.identity import normalize_serial
from snap_tap.backends.contracts import DriverError
from snap_tap.backends.contracts import DriverHealth
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessRunner,
    ProcessTimeoutError,
    SubprocessRunner,
)
from snap_tap.backends.android.uiautomator2.probe_payload import (
    parse_probe_payload,
    probe_error_code,
    probe_error_detail,
)
from snap_tap.backends.android.uiautomator2.recovery import retry_once_after_recovery


class Uiautomator2Backend:
    backend_name = "uiautomator2"

    def __init__(
        self,
        connector: Callable[[str], object] | None = None,
        *,
        process_runner: ProcessRunner | None = None,
        python_executable: str | None = None,
    ) -> None:
        self._connector = connector
        self._process_runner = process_runner or SubprocessRunner()
        self._python_executable = python_executable or sys.executable

    def health(self, device_id: str, timeout_s: float = 5.0) -> DriverHealth:
        started = perf_counter()
        serial = normalize_serial(device_id)
        if serial is None:
            return DriverHealth.failure(
                backend=self.backend_name,
                code="device_offline",
                detail="Device serial is required and must be a valid ADB serial.",
                device_id=None,
                elapsed_ms=_elapsed_ms(started),
                status="blocked",
            )
        result = self._health_once(serial, timeout_s=timeout_s, started=started)
        if self._connector is not None:
            return result
        return retry_once_after_recovery(
            result,
            device_id=serial,
            operation="health",
            process_runner=self._process_runner,
            python_executable=self._python_executable,
            retry=lambda: self._health_once(
                serial,
                timeout_s=timeout_s,
                started=started,
            ),
        )

    def _health_once(
        self,
        device_id: str,
        *,
        timeout_s: float,
        started: float,
    ) -> DriverHealth:
        try:
            metadata = self._probe(device_id, timeout_s=timeout_s)
            metadata["timeout_s"] = str(timeout_s)
            return DriverHealth.success(
                device_id=device_id,
                backend=self.backend_name,
                elapsed_ms=_elapsed_ms(started),
                metadata=metadata,
            )
        except ProcessTimeoutError as exc:
            return DriverHealth.failure(
                backend=self.backend_name,
                code="driver_timeout",
                detail=str(exc) or "uiautomator2 health check timed out.",
                device_id=device_id,
                metadata={"timeout_s": str(timeout_s)},
                elapsed_ms=_elapsed_ms(started),
            )
        except _ProbeFailure as exc:
            return DriverHealth.failure(
                backend=self.backend_name,
                code=exc.error.code,
                detail=exc.error.detail,
                device_id=device_id,
                metadata={"timeout_s": str(timeout_s)},
                elapsed_ms=_elapsed_ms(started),
            )
        except OSError as exc:
            return DriverHealth.failure(
                backend=self.backend_name,
                code="driver_unavailable",
                detail=str(exc) or "uiautomator2 driver is unavailable.",
                device_id=device_id,
                metadata={"timeout_s": str(timeout_s)},
                elapsed_ms=_elapsed_ms(started),
            )
        except Exception as exc:
            return DriverHealth.failure(
                backend=self.backend_name,
                code="driver_unavailable",
                detail=f"{type(exc).__name__}: {exc}",
                device_id=device_id,
                metadata={"timeout_s": str(timeout_s)},
                elapsed_ms=_elapsed_ms(started),
            )

    def _probe(self, device_id: str, timeout_s: float) -> dict[str, object]:
        if timeout_s <= 0:
            raise ProcessTimeoutError("uiautomator2 health timeout must be positive.")
        if self._connector is not None:
            return self._connect_and_read_info(device_id)
        args = [
            self._python_executable,
            "-m",
            "snap_tap.backends.android.uiautomator2.probes",
            "health",
            "--device",
            device_id,
        ]
        result = self._process_runner.run(args, timeout_s=timeout_s)
        payload = parse_probe_payload(result.stdout)
        if result.returncode != 0 or payload.get("ok") is not True:
            raise _ProbeFailure(
                DriverError(
                    code=probe_error_code(
                        payload,
                        default_code="driver_probe_failed",
                    ),
                    detail=probe_error_detail(
                        payload,
                        operation="health",
                        default_detail=(
                            "uiautomator2 health probe returned malformed output."
                        ),
                    ),
                )
            )
        metadata = payload.get("metadata")
        if not isinstance(metadata, Mapping):
            return {}
        return {str(key): str(value) for key, value in metadata.items()}

    def _connect(self, device_id: str) -> object:
        if self._connector is not None:
            return self._connector(device_id)
        import uiautomator2 as u2  # type: ignore[import-untyped]

        return u2.connect(device_id)

    def _connect_and_read_info(self, device_id: str) -> dict[str, object]:
        device = self._connect(device_id)
        return _metadata_from_info(_read_info(device))


def _read_info(device: object) -> object:
    info = getattr(device, "info", None)
    if callable(info):
        return info()
    return info


def _metadata_from_info(info: object) -> dict[str, object]:
    if not isinstance(info, Mapping):
        return {}
    metadata: dict[str, object] = {}
    for key in ("brand", "model", "sdkInt", "displayWidth", "displayHeight"):
        value: Any = info.get(key)
        if value is not None:
            metadata[key] = str(value)
    return metadata


class _ProbeFailure(Exception):
    def __init__(self, error: DriverError) -> None:
        self.error = error
        super().__init__(error.detail)


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
