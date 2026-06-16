from __future__ import annotations

import argparse
import base64
import json
from collections.abc import Mapping, Sequence
from io import BytesIO
from typing import Any

from snap_tap.backends.android.uiautomator2.probe_payload import safe_error_detail
from snap_tap.backends.android.uiautomator2.text_probe import (
    enable_fast_input,
    safe_focused_text,
    send_text,
    text_was_applied,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation",
        choices=[
            "health",
            "dump_xml",
            "screenshot",
            "app_current",
            "package_info",
            "tap",
            "input_text",
            "replace_text",
        ],
    )
    parser.add_argument("--device", required=True)
    parser.add_argument("--package")
    parser.add_argument("--x", type=float)
    parser.add_argument("--y", type=float)
    parser.add_argument("--text")
    args = parser.parse_args(argv)

    if args.operation == "health":
        return _health(args.device)
    if args.operation == "dump_xml":
        return _dump_xml(args.device)
    if args.operation == "screenshot":
        return _screenshot(args.device)
    if args.operation == "app_current":
        return _app_current(args.device)
    if args.operation == "package_info":
        if args.package is None:
            return _failure(
                code="app_unavailable",
                detail="Package is required for package_info.",
            )
        return _package_info(args.device, args.package)
    if args.operation == "tap":
        if args.x is None or args.y is None:
            return _failure(
                code="tap_failed",
                detail="Coordinates are required for tap.",
            )
        return _tap(args.device, args.x, args.y)
    if args.operation in {"input_text", "replace_text"}:
        if args.x is None or args.y is None or args.text is None:
            return _failure(
                code="input_failed",
                detail="Coordinates and text are required for text input.",
            )
        return _text_input(
            args.device,
            args.x,
            args.y,
            args.text,
            replace=args.operation == "replace_text",
        )
    return 2


def _health(device_id: str) -> int:
    try:
        import uiautomator2 as u2  # type: ignore[import-untyped]

        device = u2.connect(device_id)
        payload: dict[str, object] = {
            "ok": True,
            "metadata": _metadata_from_info(_read_info(device)),
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_bridge_error_code(exc, "driver_unavailable"),
            detail=f"{type(exc).__name__}: {exc}",
        )


def _dump_xml(device_id: str) -> int:
    try:
        import uiautomator2 as u2

        device = u2.connect(device_id)
        xml = _read_xml(device)
        payload: dict[str, object] = {
            "ok": True,
            "xml": xml,
            "metadata": {
                "byte_length": str(len(xml.encode("utf-8"))),
                "node_count": str(xml.count("<node")),
            },
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_bridge_error_code(exc, "dump_failed"),
            detail=f"{type(exc).__name__}: {exc}",
        )


def _screenshot(device_id: str) -> int:
    try:
        import uiautomator2 as u2

        device = u2.connect(device_id)
        image_bytes, width, height = _read_screenshot_png(device)
        payload: dict[str, object] = {
            "ok": True,
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "metadata": {
                "format": "png",
                "width": width,
                "height": height,
            },
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_bridge_error_code(exc, "screenshot_failed"),
            detail=f"{type(exc).__name__}: {exc}",
        )


def _app_current(device_id: str) -> int:
    try:
        import uiautomator2 as u2

        device = u2.connect(device_id)
        payload: dict[str, object] = {
            "ok": True,
            "metadata": _metadata_from_current_app(_read_current_app(device)),
        }
        if not payload["metadata"]:
            raise RuntimeError("focused app is unavailable.")
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_app_error_code(exc),
            detail=f"{type(exc).__name__}: {exc}",
        )


def _package_info(device_id: str, package: str) -> int:
    try:
        import uiautomator2 as u2

        device = u2.connect(device_id)
        payload: dict[str, object] = {
            "ok": True,
            "metadata": _metadata_from_package_info(
                _read_package_info(device, package),
                package=package,
            ),
        }
        if not payload["metadata"]:
            raise RuntimeError(f"package {package!r} is unavailable.")
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_app_error_code(exc),
            detail=f"{type(exc).__name__}: {exc}",
        )


def _tap(device_id: str, x: float, y: float) -> int:
    try:
        import uiautomator2 as u2

        device = u2.connect(device_id)
        click_result = _click(device, x, y)
        payload: dict[str, object] = {
            "ok": True,
            "clicked": True,
            "metadata": {
                "click_return": _public_click_result(click_result),
                "x": x,
                "y": y,
            },
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_bridge_error_code(exc, "tap_failed"),
            detail=f"{type(exc).__name__}: {exc}",
        )


def _click(device: object, x: float, y: float) -> object:
    click = getattr(device, "click", None)
    if not callable(click):
        raise RuntimeError("Connected device does not expose click.")
    return click(x, y)


def _text_input(device_id: str, x: float, y: float, text: str, *, replace: bool) -> int:
    stage = "connect"
    touch_may_have_occurred = False
    try:
        import uiautomator2 as u2

        device = u2.connect(device_id)
        stage = "input_method"
        touch_may_have_occurred = True
        input_method = enable_fast_input(device)
        stage = "click"
        click_result = _click(device, x, y)
        stage = "before_verify"
        before_text, before_error = safe_focused_text(_read_xml(device))
        stage = "send_text"
        text_result = send_text(device, text, replace=replace)
        stage = "after_verify"
        after_text, after_error = safe_focused_text(_read_xml(device))
        text_applied = text_was_applied(
            before_text,
            after_text,
            text,
            replace=replace,
        )
        payload: dict[str, object] = {
            "ok": True,
            "text_applied": text_applied,
            "metadata": {
                "click_return": _public_click_result(click_result),
                "input_method": input_method,
                "replace": replace,
                "text_call_returned": text_result is not None,
                "text_length": len(text),
                "text_verified": text_applied,
                "touch_may_have_occurred": touch_may_have_occurred,
            },
        }
        metadata = payload["metadata"]
        if isinstance(metadata, dict):
            if before_text is not None:
                metadata["before_text_length"] = len(before_text)
            if after_text is not None:
                metadata["after_text_length"] = len(after_text)
            if before_error is not None:
                metadata["before_verification_error"] = before_error
            if after_error is not None:
                metadata["after_verification_error"] = after_error
        print(json.dumps(payload, sort_keys=True))
        return 0
    except Exception as exc:
        return _failure(
            code=_bridge_error_code(exc, "input_failed"),
            detail=_safe_exception_detail(exc, operation="text input", text=text),
            metadata={
                "stage": stage,
                "text_length": len(text),
                "touch_may_have_occurred": touch_may_have_occurred,
            },
        )


def _public_click_result(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return type(value).__name__


def _safe_exception_detail(exc: Exception, *, operation: str, text: str) -> str:
    return safe_error_detail(
        f"{type(exc).__name__}: {exc}",
        operation=operation,
        sensitive_markers=(text,),
    )


def _read_screenshot_png(device: object) -> tuple[bytes, int, int]:
    screenshot = getattr(device, "screenshot", None)
    if not callable(screenshot):
        raise RuntimeError("Connected device does not expose screenshot.")
    image = screenshot(format="pillow")
    save = getattr(image, "save", None)
    if not callable(save):
        raise RuntimeError("screenshot(format='pillow') returned a non-image.")
    width, height = _image_dimensions(image)
    output = BytesIO()
    save(output, format="PNG")
    image_bytes = output.getvalue()
    if not image_bytes:
        raise RuntimeError("screenshot returned empty PNG bytes.")
    return image_bytes, width, height


def _image_dimensions(image: object) -> tuple[int, int]:
    size = getattr(image, "size", None)
    if (
        isinstance(size, tuple)
        and len(size) == 2
        and isinstance(size[0], int)
        and isinstance(size[1], int)
    ):
        width_obj: object = size[0]
        height_obj: object = size[1]
    else:
        width_obj = getattr(image, "width", None)
        height_obj = getattr(image, "height", None)
    if not isinstance(width_obj, int) or not isinstance(height_obj, int):
        raise RuntimeError("screenshot image does not expose dimensions.")
    width = width_obj
    height = height_obj
    if width <= 0 or height <= 0:
        raise RuntimeError("screenshot image dimensions must be positive.")
    return width, height


def _read_xml(device: object) -> str:
    dump_hierarchy = getattr(device, "dump_hierarchy", None)
    if not callable(dump_hierarchy):
        raise RuntimeError("Connected device does not expose dump_hierarchy.")
    xml = dump_hierarchy()
    if not isinstance(xml, str) or not xml.strip():
        raise RuntimeError("dump_hierarchy returned empty XML.")
    return xml


def _read_current_app(device: object) -> object:
    app_current = getattr(device, "app_current", None)
    if not callable(app_current):
        raise RuntimeError("Connected device does not expose app_current.")
    return app_current()


def _read_package_info(device: object, package: str) -> object:
    app_info = getattr(device, "app_info", None)
    if not callable(app_info):
        raise RuntimeError("Connected device does not expose app_info.")
    return app_info(package)


def _read_info(device: object) -> object:
    info = getattr(device, "info", None)
    if callable(info):
        return info()
    return info


def _metadata_from_info(info: object) -> dict[str, str]:
    if not isinstance(info, Mapping):
        return {}
    metadata: dict[str, str] = {}
    for key in ("brand", "model", "sdkInt", "displayWidth", "displayHeight"):
        value: Any = info.get(key)
        if value is not None:
            metadata[key] = str(value)
    return metadata


def _metadata_from_current_app(info: object) -> dict[str, object]:
    if not isinstance(info, Mapping):
        return {}
    metadata: dict[str, object] = {}
    package = info.get("package")
    activity = info.get("activity")
    pid = info.get("pid")
    if isinstance(package, str) and package.strip():
        metadata["package"] = package.strip()
    if isinstance(activity, str) and activity.strip():
        metadata["activity"] = activity.strip()
    if isinstance(pid, int) and not isinstance(pid, bool) and pid >= 0:
        metadata["pid"] = pid
    return metadata


def _metadata_from_package_info(info: object, *, package: str) -> dict[str, object]:
    metadata: dict[str, object] = {"package": package}
    if not isinstance(info, Mapping):
        return metadata
    reported_package = info.get("packageName") or info.get("package")
    version_name = info.get("versionName") or info.get("version_name")
    version_code = info.get("versionCode") or info.get("version_code")
    if isinstance(reported_package, str) and reported_package.strip():
        metadata["package"] = reported_package.strip()
    if isinstance(version_name, str) and version_name.strip():
        metadata["version_name"] = version_name.strip()
    if isinstance(version_code, int) and not isinstance(version_code, bool):
        metadata["version_code"] = version_code
    elif isinstance(version_code, str) and version_code.isdigit():
        metadata["version_code"] = int(version_code)
    return metadata


def _app_error_code(exc: Exception) -> str:
    return _bridge_error_code(exc, "app_unavailable")


def _bridge_error_code(exc: Exception, default: str) -> str:
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "driver_unavailable"
    message = f"{type(exc).__name__}: {exc}".lower()
    if "device offline" in message:
        return "device_offline"
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
    if any(marker in message for marker in bridge_markers):
        return "driver_unavailable"
    return default


def _failure(
    *,
    code: str,
    detail: str,
    metadata: Mapping[str, object] | None = None,
) -> int:
    payload: dict[str, object] = {"ok": False, "error": {"code": code, "detail": detail}}
    if metadata is not None:
        payload["metadata"] = dict(metadata)
    print(json.dumps(payload, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
