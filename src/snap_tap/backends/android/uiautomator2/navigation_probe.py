from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from importlib import import_module

from snap_tap.device.identity import normalize_serial


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["back", "home", "swipe"])
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


def _call_press(device: object, operation: str) -> object:
    press = getattr(device, "press", None)
    if not callable(press):
        raise RuntimeError("Connected device does not expose press.")
    return press(operation)


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
    payload: dict[str, object] = {"ok": False, "error": {"code": code, "detail": detail}}
    if metadata is not None:
        payload["metadata"] = _safe_metadata(metadata)
    print(json.dumps(payload, sort_keys=True))
    return 1


def _safe_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    public: dict[str, object] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            public[str(key)] = value
    return public


if __name__ == "__main__":
    raise SystemExit(main())
