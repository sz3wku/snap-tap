from __future__ import annotations

from collections.abc import Mapping

from snap_tap.backends.android.uiautomator2.probe_payload import (
    probe_error_code as driver_probe_error_code,
    probe_error_detail as driver_probe_error_detail,
)


def probe_metadata(
    operation: str,
    payload: Mapping[str, object],
    *,
    timeout_s: float,
    package_name: str | None,
) -> dict[str, object]:
    metadata: dict[str, object] = {"timeout_s": timeout_s}
    raw_metadata = payload.get("metadata")
    if operation == "package_info" and package_name is not None:
        metadata["package"] = package_name
    if not isinstance(raw_metadata, Mapping):
        return metadata
    if operation == "app_current":
        _copy_string(metadata, raw_metadata, "package")
        _copy_string(metadata, raw_metadata, "activity")
        _copy_int(metadata, raw_metadata, "pid")
    elif operation == "package_info":
        _copy_string(metadata, raw_metadata, "version_name")
        _copy_int(metadata, raw_metadata, "version_code")
    return metadata


def has_required_metadata(operation: str, metadata: Mapping[str, object]) -> bool:
    if operation == "app_current":
        return isinstance(metadata.get("package"), str) and isinstance(
            metadata.get("activity"), str
        )
    if operation == "package_info":
        return isinstance(metadata.get("package"), str) and isinstance(
            metadata.get("version_name"), str
        )
    return False


def probe_error_code(payload: Mapping[str, object]) -> str:
    code = driver_probe_error_code(payload, default_code="app_unavailable")
    if code in {"app_unavailable", "driver_unavailable", "driver_timeout"}:
        return code
    return "app_unavailable"


def probe_error_detail(payload: Mapping[str, object], operation: str) -> str:
    return driver_probe_error_detail(payload, operation=operation)


def _copy_string(
    target: dict[str, object],
    source: Mapping[str, object],
    key: str,
) -> None:
    value = _non_empty_string(source.get(key))
    if value is not None:
        target[key] = value


def _copy_int(
    target: dict[str, object],
    source: Mapping[str, object],
    key: str,
) -> None:
    value = _non_negative_int(source.get(key))
    if value is not None:
        target[key] = value


def _non_empty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        candidate = value
    elif isinstance(value, str):
        try:
            candidate = int(value)
        except ValueError:
            return None
    else:
        return None
    if candidate < 0:
        return None
    return candidate
