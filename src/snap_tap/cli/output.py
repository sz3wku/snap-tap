from __future__ import annotations

from collections.abc import Mapping
import json

import typer

from snap_tap.device.identity import DeviceInfo
from snap_tap.backends.contracts import (
    DriverAppAwareness,
    DriverError,
    DriverHealth,
    DriverLifecycleResult,
    DriverScreenshot,
    DriverXmlDump,
)


def emit_json(payload: Mapping[str, object]) -> None:
    typer.echo(json.dumps(payload, sort_keys=True))


def device_to_dict(device: DeviceInfo) -> dict[str, object]:
    return {
        "serial": device.serial,
        "state": device.state,
        "product": device.product,
        "model": device.model,
        "device": device.device,
    }


def health_to_dict(health: DriverHealth) -> dict[str, object]:
    return {
        "ok": health.ok,
        "status": health.status,
        "device_id": health.device_id,
        "backend": health.backend,
        "checked_at": health.checked_at,
        "elapsed_ms": health.elapsed_ms,
        "metadata": dict(health.metadata),
        "recovery": recovery_to_dict(health.metadata),
        "error": error_to_dict(health.error),
    }


def lifecycle_to_dict(result: DriverLifecycleResult) -> dict[str, object]:
    return {
        "ok": result.ok,
        "status": result.status,
        "device_id": result.device_id,
        "backend": result.backend,
        "operation": result.operation,
        "checked_at": result.checked_at,
        "elapsed_ms": result.elapsed_ms,
        "metadata": lifecycle_metadata_to_dict(result.metadata),
        "error": error_to_dict(result.error),
    }


def xml_dump_to_dict(result: DriverXmlDump) -> dict[str, object]:
    return {
        "ok": result.ok,
        "status": result.status,
        "device_id": result.device_id,
        "backend": result.backend,
        "operation": result.operation,
        "checked_at": result.checked_at,
        "elapsed_ms": result.elapsed_ms,
        "xml": result.xml,
        "metadata": dict(result.metadata),
        "recovery": recovery_to_dict(result.metadata),
        "error": error_to_dict(result.error),
    }


def screenshot_to_dict(result: DriverScreenshot) -> dict[str, object]:
    return {
        "ok": result.ok,
        "status": result.status,
        "device_id": result.device_id,
        "backend": result.backend,
        "operation": result.operation,
        "checked_at": result.checked_at,
        "elapsed_ms": result.elapsed_ms,
        "path": result.path,
        "metadata": screenshot_metadata_to_dict(result.metadata),
        "recovery": recovery_to_dict(result.metadata),
        "error": error_to_dict(result.error),
    }


def app_awareness_to_dict(result: DriverAppAwareness) -> dict[str, object]:
    return {
        "ok": result.ok,
        "status": result.status,
        "device_id": result.device_id,
        "backend": result.backend,
        "operation": result.operation,
        "checked_at": result.checked_at,
        "elapsed_ms": result.elapsed_ms,
        "metadata": app_awareness_metadata_to_dict(
            result.operation,
            result.metadata,
        ),
        "recovery": recovery_to_dict(result.metadata),
        "error": error_to_dict(result.error),
    }


def app_awareness_metadata_to_dict(
    operation: str,
    metadata: Mapping[str, object],
) -> dict[str, object]:
    public: dict[str, object] = {}
    if operation == "app_current":
        package = metadata.get("package")
        activity = metadata.get("activity")
        pid = metadata.get("pid")
        if isinstance(package, str):
            public["package"] = package
        if isinstance(activity, str):
            public["activity"] = activity
        if isinstance(pid, int) and not isinstance(pid, bool):
            public["pid"] = pid
    elif operation == "package_info":
        package = metadata.get("package")
        version_name = metadata.get("version_name")
        version_code = metadata.get("version_code")
        if isinstance(package, str):
            public["package"] = package
        if isinstance(version_name, str):
            public["version_name"] = version_name
        if isinstance(version_code, int) and not isinstance(version_code, bool):
            public["version_code"] = version_code
    return public


def screenshot_metadata_to_dict(metadata: Mapping[str, object]) -> dict[str, object]:
    public: dict[str, object] = {}
    image_format = metadata.get("format")
    if isinstance(image_format, str):
        public["format"] = image_format
    for key in ("width", "height", "byte_length"):
        value = metadata.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            public[key] = value
    sha256 = metadata.get("sha256")
    if isinstance(sha256, str):
        public["sha256"] = sha256
    return public


def lifecycle_metadata_to_dict(metadata: Mapping[str, object]) -> dict[str, object]:
    public: dict[str, object] = {}
    for key in ("returncode", "timeout_s", "stdout_present", "stderr_present"):
        value = metadata.get(key)
        if isinstance(value, str):
            public[key] = value
    return public


def recovery_to_dict(metadata: Mapping[str, object]) -> dict[str, object] | None:
    recovery_attempted = metadata.get("recovery_attempted")
    if recovery_attempted is not True:
        return None
    public: dict[str, object] = {"recovery_attempted": True}
    attempt = metadata.get("attempt")
    if isinstance(attempt, int) and not isinstance(attempt, bool):
        public["attempt"] = attempt
    recovery_ok = metadata.get("recovery_ok")
    if isinstance(recovery_ok, bool):
        public["recovery_ok"] = recovery_ok
    recovery_operation = metadata.get("recovery_operation")
    if isinstance(recovery_operation, str):
        public["recovery_operation"] = recovery_operation
    recovery_elapsed_ms = metadata.get("recovery_elapsed_ms")
    if isinstance(recovery_elapsed_ms, (int, float)) and not isinstance(
        recovery_elapsed_ms,
        bool,
    ):
        public["recovery_elapsed_ms"] = recovery_elapsed_ms
    recovered_after_failure = metadata.get("recovered_after_failure")
    if isinstance(recovered_after_failure, str):
        public["recovered_after_failure"] = recovered_after_failure
    recovery_error_code = metadata.get("recovery_error_code")
    if isinstance(recovery_error_code, str):
        public["recovery_error_code"] = recovery_error_code
    return public


def error_to_dict(error: DriverError | None) -> dict[str, object] | None:
    if error is None:
        return None
    payload: dict[str, object] = {"code": error.code, "detail": error.detail}
    if error.category is not None:
        payload["category"] = error.category
    if error.recoverable is not None:
        payload["recoverable"] = error.recoverable
    if error.retryable is not None:
        payload["retryable"] = error.retryable
    if error.recovery_hint is not None:
        payload["recovery_hint"] = error.recovery_hint
    return payload
