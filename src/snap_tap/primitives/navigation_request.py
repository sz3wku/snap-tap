from __future__ import annotations

import math

from snap_tap.backends.android.uiautomator2.navigation import (
    NAVIGATION_BACK,
    NAVIGATION_HOME,
    NAVIGATION_SWIPE,
    SWIPE_DIRECTIONS,
)
from snap_tap.primitives.models import PrimitiveNavigationRequest
from snap_tap.primitives.proof import normalize_post_action_settle_ms


NAVIGATION_WAIT = "wait"
NAVIGATION_PRIMITIVES = {
    NAVIGATION_BACK,
    NAVIGATION_HOME,
    NAVIGATION_SWIPE,
    NAVIGATION_WAIT,
}
MIN_SWIPE_DISTANCE_RATIO = 0.05
MAX_SWIPE_DISTANCE_RATIO = 0.90
MIN_SWIPE_DURATION_MS = 50
MAX_SWIPE_DURATION_MS = 1500
MAX_WAIT_SECONDS = 60.0


def navigation_request_payload(
    request: PrimitiveNavigationRequest,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "operation": request.operation,
        "device_id": request.device_id,
        "timeout_s": request.timeout_s,
        "lease_timeout_s": request.lease_timeout_s,
        "post_action_settle_ms": normalize_post_action_settle_ms(
            request.post_action_settle_ms
        ),
    }
    if request.operation == NAVIGATION_SWIPE:
        payload["direction"] = request.direction
        payload["distance_ratio"] = request.distance_ratio
        payload["duration_ms"] = request.duration_ms
    if request.operation == NAVIGATION_WAIT:
        payload["seconds"] = request.seconds
    return payload


def invalid_navigation_request_detail(
    request: PrimitiveNavigationRequest,
    serial: str | None,
) -> str | None:
    if serial is None:
        return "Device serial is required and must be a valid ADB serial."
    if request.operation not in NAVIGATION_PRIMITIVES:
        return "Primitive operation must be back, home, swipe, or wait."
    if not _positive_finite(request.timeout_s) or not _positive_finite(
        request.lease_timeout_s
    ):
        return "Primitive timeout values must be positive finite numbers."
    if request.operation == NAVIGATION_WAIT:
        if not _bounded_number(request.seconds, minimum=0.0, maximum=MAX_WAIT_SECONDS):
            return "Wait seconds must be between 0 and 60 seconds."
    if request.operation == NAVIGATION_SWIPE:
        if request.direction not in SWIPE_DIRECTIONS:
            return "Swipe direction must be up, down, left, or right."
        if not _bounded_number(
            request.distance_ratio,
            minimum=MIN_SWIPE_DISTANCE_RATIO,
            maximum=MAX_SWIPE_DISTANCE_RATIO,
        ):
            return "Swipe distance ratio must be between 0.05 and 0.90."
        if (
            not isinstance(request.duration_ms, int)
            or isinstance(request.duration_ms, bool)
            or request.duration_ms < MIN_SWIPE_DURATION_MS
            or request.duration_ms > MAX_SWIPE_DURATION_MS
        ):
            return "Swipe duration must be between 50 and 1500 ms."
    return None


def safe_navigation_operation(operation: str) -> str:
    return operation if operation in NAVIGATION_PRIMITIVES else NAVIGATION_BACK


def _positive_finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (
        math.isfinite(float(value)) and float(value) > 0
    )


def _bounded_number(value: object, *, minimum: float, maximum: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (
        math.isfinite(float(value)) and minimum <= float(value) <= maximum
    )
