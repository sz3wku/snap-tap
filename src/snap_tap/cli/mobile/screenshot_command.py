from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import typer

from snap_tap.cli.output import emit_json, screenshot_to_dict
from snap_tap.cli.mobile.device_discovery import read_visible_devices
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.backends.contracts import (
    DriverScreenshot,
    DriverScreenshotCapturer,
    capture_device_screenshot,
)
from snap_tap.backends.android.uiautomator2.screenshot import Uiautomator2ScreenshotCapturer


class ScreenshotDependencies(Protocol):
    @property
    def discovery(self) -> DeviceDiscovery: ...

    @property
    def screenshot_capturer(self) -> DriverScreenshotCapturer | None: ...


def run_screenshot_command(
    *,
    dependencies: ScreenshotDependencies,
    device: str | None,
    out: Path | None,
    timeout_s: float,
) -> None:
    capturer = _screenshot_capturer(dependencies)
    if out is None:
        result = DriverScreenshot.failure(
            backend=capturer.backend_name,
            code="invalid_arguments",
            detail="Pass --out to write the screenshot PNG.",
            device_id=device,
            elapsed_ms=0.0,
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )
        _emit_screenshot_result(result)
        return

    snapshot = read_visible_devices(dependencies.discovery)
    if snapshot.error is not None:
        result = DriverScreenshot.failure(
            backend=capturer.backend_name,
            code=snapshot.error.code,
            detail=snapshot.error.detail,
            device_id=device,
            elapsed_ms=0.0,
            status="blocked",
            metadata={"timeout_s": timeout_s},
        )
        _emit_screenshot_result(result)
        return
    visible = snapshot.devices
    result = capture_device_screenshot(
        capturer=capturer,
        devices=visible,
        requested_serial=device,
        timeout_s=timeout_s,
    )
    if result.ok:
        result = _write_screenshot_png(result, out)
    _emit_screenshot_result(result)


def _emit_screenshot_result(result: DriverScreenshot) -> None:
    emit_json({"ok": result.ok, "result": screenshot_to_dict(result)})
    if not result.ok:
        raise typer.Exit(code=1)


def _write_screenshot_png(result: DriverScreenshot, out: Path) -> DriverScreenshot:
    image_bytes = result.image_bytes
    target = out.expanduser()
    if image_bytes is None:
        return DriverScreenshot.failure(
            backend=result.backend,
            code="screenshot_failed",
            detail="Screenshot capture completed without image bytes.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            path=str(target),
            metadata=result.metadata,
        )

    temp_path: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.parent / f".{target.name or 'screenshot'}.{uuid4().hex}.tmp"
        temp_path.write_bytes(image_bytes)
        os.replace(temp_path, target)
    except OSError:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        return DriverScreenshot.failure(
            backend=result.backend,
            code="screenshot_failed",
            detail="Failed to write screenshot PNG.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            path=str(target),
            metadata=result.metadata,
        )
    return result.with_path(str(target))


def _screenshot_capturer(
    dependencies: ScreenshotDependencies,
) -> DriverScreenshotCapturer:
    return dependencies.screenshot_capturer or Uiautomator2ScreenshotCapturer()
