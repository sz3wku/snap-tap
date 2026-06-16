from __future__ import annotations

from collections.abc import Mapping
import json

from snap_tap.backends.contracts import ERROR_SPECS


DEFAULT_DETAIL_LIMIT = 500


def parse_probe_payload(stdout: str) -> Mapping[str, object]:
    text = stdout.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, Mapping):
        return {}
    return payload


def probe_error_code(
    payload: Mapping[str, object],
    *,
    default_code: str,
) -> str:
    error = payload.get("error")
    if isinstance(error, Mapping):
        code = error.get("code")
        if isinstance(code, str) and code in ERROR_SPECS:
            return code
    return default_code


def probe_error_detail(
    payload: Mapping[str, object],
    *,
    operation: str,
    sensitive_markers: tuple[str, ...] = (),
    default_detail: str | None = None,
) -> str:
    error = payload.get("error")
    if isinstance(error, Mapping):
        detail = error.get("detail")
        if isinstance(detail, str) and detail.strip():
            return safe_error_detail(
                detail.strip(),
                operation=operation,
                sensitive_markers=sensitive_markers,
            )
    if default_detail is not None:
        return default_detail
    return f"uiautomator2 {operation} probe failed without a structured error."


def safe_error_detail(
    detail: str,
    *,
    operation: str,
    sensitive_markers: tuple[str, ...] = (),
    limit: int = DEFAULT_DETAIL_LIMIT,
) -> str:
    lowered = detail.lower()
    if any(marker.lower() in lowered for marker in sensitive_markers):
        return f"uiautomator2 {operation} probe failed with redacted error detail."
    if len(detail) > limit:
        return f"uiautomator2 {operation} probe failed with oversized error detail."
    return detail
