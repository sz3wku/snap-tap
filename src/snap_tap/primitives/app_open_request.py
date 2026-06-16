from __future__ import annotations

import math

from snap_tap.backends.contracts import normalize_package
from snap_tap.primitives.models import PrimitiveAppOpenRequest
from snap_tap.primitives.proof import normalize_post_action_settle_ms

APP_OPEN_OPERATION = "app_open"


def app_open_request_payload(
    request: PrimitiveAppOpenRequest,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "operation": APP_OPEN_OPERATION,
        "device_id": request.device_id,
        "query": request.query,
        "package": request.package,
        "timeout_s": request.timeout_s,
        "lease_timeout_s": request.lease_timeout_s,
        "post_action_settle_ms": normalize_post_action_settle_ms(
            request.post_action_settle_ms
        ),
    }
    if request.activity is not None:
        payload["activity"] = request.activity
    return payload


def invalid_app_open_request_detail(
    request: PrimitiveAppOpenRequest,
    serial: str | None,
) -> str | None:
    if serial is None:
        return "Device serial is required and must be a valid ADB serial."
    if not request.query.strip():
        return "App query is required."
    package = normalize_package(request.package)
    if package is None or "." not in package:
        return "App package must be a valid Android package name."
    if not _positive_finite(request.timeout_s) or not _positive_finite(
        request.lease_timeout_s
    ):
        return "Primitive timeout values must be positive finite numbers."
    return None


def _positive_finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (
        math.isfinite(float(value)) and float(value) > 0
    )
