from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from importlib import import_module
from time import sleep

from snap_tap.backends.android.uiautomator2.device_state import (
    STATE_UNKNOWN,
    dimensions_from_info,
    is_false,
    is_true,
    read_device_state,
)
from snap_tap.device.identity import normalize_serial


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation", choices=["back", "home", "swipe", "wake", "unlock"]
    )
    parser.add_argument("--device", required=True)
    parser.add_argument("--direction", choices=["up", "down", "left", "right"])
    parser.add_argument("--x1", type=float)
    parser.add_argument("--y1", type=float)
    parser.add_argument("--x2", type=float)
    parser.add_argument("--y2", type=float)
    parser.add_argument("--duration-ms", type=int)
    parser.add_argument("--distance-ratio", type=float)
    args = parser.parse_args(argv)
    serial = normalize_serial(args.device)
    if serial is None:
        return _failure(
            code="device_offline",
            detail="Device serial is required and must be a valid ADB serial.",
        )

    if args.operation in {"back", "home"}:
        return _press(serial, args.operation)
    if args.operation == "wake":
        return _wake(serial)
    if args.operation == "unlock":
        return _unlock(serial)
    if (
        args.direction is None
        or args.x1 is None
        or args.y1 is None
        or args.x2 is None
        or args.y2 is None
        or args.duration_ms is None
    ):
        return _failure(
            code="navigation_failed",
            detail="Swipe requires direction, derived coordinates, and duration.",
        )
    return _swipe(
        serial,
        direction=args.direction,
        x1=args.x1,
        y1=args.y1,
        x2=args.x2,
        y2=args.y2,
        duration_ms=args.duration_ms,
        distance_ratio=args.distance_ratio,
    )


def _press(device_id: str, operation: str) -> int:
    touch_may_have_occurred = False
    try:
        device = _connect(device_id)
        touch_may_have_occurred = True
        result = _call_press(device, operation)
        payload: dict[str, object] = {
            "ok": True,
            "pressed": True,
            "metadata": {
                "press_returned": result is not None,
                "touch_may_have_occurred": touch_may_have_occurred,
            },
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_bridge_error_code(exc),
            detail=f"{type(exc).__name__}: {exc}",
            metadata={"touch_may_have_occurred": touch_may_have_occurred},
        )


def _wake(device_id: str) -> int:
    touch_may_have_occurred = False
    attempted = False
    try:
        device = _connect(device_id)
        before = read_device_state(device)
        if not is_true(before.get("screen_on")):
            attempted = True
            touch_may_have_occurred = True
            _call_screen_on(device)
            sleep(0.3)
        after = read_device_state(device)
        metadata = _state_metadata(
            before=before,
            after=after,
            attempted=attempted,
            touch_may_have_occurred=touch_may_have_occurred,
        )
        if not is_true(after.get("screen_on")):
            return _failure(
                code="wake_failed",
                detail="Screen did not report awake after wake.",
                metadata=metadata,
            )
        payload: dict[str, object] = {
            "ok": True,
            "woke": True,
            "metadata": metadata,
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_bridge_error_code(exc),
            detail=f"{type(exc).__name__}: {exc}",
            metadata={
                "attempted": attempted,
                "touch_may_have_occurred": touch_may_have_occurred,
            },
        )


def _unlock(device_id: str) -> int:
    touch_may_have_occurred = False
    attempted = False
    try:
        device = _connect(device_id)
        before = read_device_state(device)
        current = before
        if not is_true(current.get("screen_on")):
            attempted = True
            touch_may_have_occurred = True
            _call_screen_on(device)
            sleep(0.3)
            current = read_device_state(device)

        if is_false(current.get("keyguard_locked")) and is_true(
            current.get("screen_on")
        ):
            metadata = _state_metadata(
                before=before,
                after=current,
                attempted=attempted,
                touch_may_have_occurred=touch_may_have_occurred,
            )
            payload: dict[str, object] = {
                "ok": True,
                "unlocked": True,
                "metadata": metadata,
            }
            print(json.dumps(payload, sort_keys=True))
            return 0

        if is_true(current.get("keyguard_secure")) and not is_false(
            current.get("keyguard_locked")
        ):
            metadata = _state_metadata(
                before=before,
                after=current,
                attempted=attempted,
                touch_may_have_occurred=touch_may_have_occurred,
            )
            return _failure(
                code="secure_keyguard_required",
                detail="Secure keyguard requires manual unlock.",
                metadata=metadata,
            )

        attempted = True
        touch_may_have_occurred = True
        _dismiss_keyguard(device)
        sleep(0.5)
        after = read_device_state(device)
        metadata = _state_metadata(
            before=before,
            after=after,
            attempted=attempted,
            touch_may_have_occurred=touch_may_have_occurred,
        )
        metadata["dismiss_attempted"] = True
        if is_false(after.get("keyguard_locked")) and is_true(after.get("screen_on")):
            payload = {
                "ok": True,
                "unlocked": True,
                "metadata": metadata,
            }
            print(json.dumps(payload, sort_keys=True))
            return 0
        if is_true(after.get("keyguard_secure")):
            return _failure(
                code="secure_keyguard_required",
                detail="Secure keyguard requires manual unlock.",
                metadata=metadata,
            )
        return _failure(
            code="unlock_failed",
            detail="Keyguard remained locked after unlock gesture.",
            metadata=metadata,
        )
    except Exception as exc:
        return _failure(
            code=_bridge_error_code(exc),
            detail=f"{type(exc).__name__}: {exc}",
            metadata={
                "attempted": attempted,
                "touch_may_have_occurred": touch_may_have_occurred,
            },
        )


def _swipe(
    device_id: str,
    *,
    direction: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    duration_ms: int,
    distance_ratio: float | None,
) -> int:
    touch_may_have_occurred = False
    try:
        device = _connect(device_id)
        touch_may_have_occurred = True
        result = _call_swipe(device, x1, y1, x2, y2, duration_ms=duration_ms)
        metadata: dict[str, object] = {
            "direction": direction,
            "duration_ms": duration_ms,
            "swipe_returned": result is not None,
            "touch_may_have_occurred": touch_may_have_occurred,
        }
        if distance_ratio is not None:
            metadata["distance_ratio"] = distance_ratio
        payload: dict[str, object] = {
            "ok": True,
            "swiped": _confirmed(result),
            "metadata": metadata,
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_bridge_error_code(exc),
            detail=f"{type(exc).__name__}: {exc}",
            metadata={
                "direction": direction,
                "duration_ms": duration_ms,
                "touch_may_have_occurred": touch_may_have_occurred,
            },
        )


def _connect(device_id: str) -> object:
    module = import_module("uiautomator2")
    connect = getattr(module, "connect", None)
    if not callable(connect):
        raise RuntimeError("uiautomator2 module does not expose connect.")
    return connect(device_id)


def _call_screen_on(device: object) -> object:
    screen_on = getattr(device, "screen_on", None)
    if callable(screen_on):
        return screen_on()
    return _call_press(device, "power")


def _call_press(device: object, operation: str) -> object:
    press = getattr(device, "press", None)
    if not callable(press):
        raise RuntimeError("Connected device does not expose press.")
    return press(operation)


def _dismiss_keyguard(device: object) -> object:
    info = getattr(device, "info", None)
    info_value = info() if callable(info) else info
    width, height = dimensions_from_info(info_value)
    swipe = getattr(device, "swipe", None)
    if callable(swipe):
        if width is not None and height is not None:
            return swipe(
                width * 0.5,
                height * 0.82,
                width * 0.5,
                height * 0.20,
                duration=0.25,
            )
        return swipe(0.5, 0.9, 0.5, 0.2, duration=0.25)
    unlock = getattr(device, "unlock", None)
    if callable(unlock):
        return unlock()
    raise RuntimeError("Connected device does not expose unlock or swipe.")


def _call_swipe(
    device: object,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    duration_ms: int,
) -> object:
    swipe = getattr(device, "swipe", None)
    if not callable(swipe):
        raise RuntimeError("Connected device does not expose swipe.")
    return swipe(x1, y1, x2, y2, duration=duration_ms / 1000)


def _confirmed(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return True


def _bridge_error_code(exc: Exception) -> str:
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "driver_unavailable"
    message = f"{type(exc).__name__}: {exc}".lower()
    bridge_markers = (
        "atx-agent",
        "connection aborted",
        "connection refused",
        "connection reset",
        "httpconnectionpool",
        "jsonrpc",
        "max retries exceeded",
        "uiautomator service",
        "uiautomator stopped",
    )
    if "device offline" in message:
        return "device_offline"
    if any(marker in message for marker in bridge_markers):
        return "driver_unavailable"
    return "navigation_failed"


def _failure(
    *,
    code: str,
    detail: str,
    metadata: Mapping[str, object] | None = None,
) -> int:
    payload: dict[str, object] = {
        "ok": False,
        "error": {"code": code, "detail": detail},
    }
    if metadata is not None:
        payload["metadata"] = _safe_metadata(metadata)
    print(json.dumps(payload, sort_keys=True))
    return 1


def _state_metadata(
    *,
    before: Mapping[str, str],
    after: Mapping[str, str],
    attempted: bool,
    touch_may_have_occurred: bool,
) -> dict[str, object]:
    return {
        "attempted": attempted,
        "touch_may_have_occurred": touch_may_have_occurred,
        "screen_on_before": before.get("screen_on", STATE_UNKNOWN),
        "screen_on_after": after.get("screen_on", STATE_UNKNOWN),
        "keyguard_locked_before": before.get("keyguard_locked", STATE_UNKNOWN),
        "keyguard_locked_after": after.get("keyguard_locked", STATE_UNKNOWN),
        "keyguard_secure": after.get(
            "keyguard_secure",
            before.get("keyguard_secure", STATE_UNKNOWN),
        ),
    }


def _safe_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    public: dict[str, object] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            public[str(key)] = value
    return public


if __name__ == "__main__":
    raise SystemExit(main())
