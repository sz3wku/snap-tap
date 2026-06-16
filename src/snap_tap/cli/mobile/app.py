from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from snap_tap.cli.output import (
    device_to_dict,
    emit_json,
    health_to_dict,
    lifecycle_to_dict,
    xml_dump_to_dict,
)
from snap_tap.cli.mobile.app_awareness_command import register_app_awareness_commands
from snap_tap.cli.mobile.device_discovery import (
    blocked_health,
    devices_failure_payload,
    discovery_health_failure,
    discovery_lifecycle_failure,
    discovery_xml_failure,
    read_visible_devices,
)
from snap_tap.cli.mobile.primitive_tap_command import (
    PrimitiveTapExecutor,
    register_primitive_tap_command,
)
from snap_tap.cli.mobile.primitive_text_command import (
    PrimitiveTextExecutor,
    register_primitive_text_commands,
)
from snap_tap.cli.mobile.primitive_navigation_command import (
    PrimitiveNavigationExecutor,
    register_primitive_navigation_commands,
)
from snap_tap.cli.mobile.navigation_command import register_navigation_commands
from snap_tap.cli.mobile.screenshot_command import run_screenshot_command
from snap_tap.cli.mobile.snap_command import register_snap_commands
from snap_tap.cli.mobile.snapshot_command import register_snapshot_commands
from snap_tap.cli.mobile.tap_command import register_tap_command
from snap_tap.cli.mobile.text_command import register_text_commands
from snap_tap.device.discovery import AdbDeviceDiscovery, DeviceDiscovery
from snap_tap.device.identity import DeviceInfo, select_device
from snap_tap.backends.contracts import (
    DriverAppAwarenessReader,
    DriverBackend,
    DriverHealth,
    DriverLifecycleResult,
    DriverLifecycleRunner,
    DriverScreenshotCapturer,
    DriverXmlDump,
    DriverXmlDumper,
    check_device_health,
)
from snap_tap.backends.android.uiautomator2.lifecycle import (
    Uiautomator2LifecycleRunner,
)
from snap_tap.primitives import PrimitiveNavigator, PrimitiveTapper, PrimitiveTexter
from snap_tap.backends.android.uiautomator2.screenshot import Uiautomator2ScreenshotCapturer
from snap_tap.backends.android.uiautomator2.backend import Uiautomator2Backend
from snap_tap.backends.android.uiautomator2.app_awareness import Uiautomator2AppAwarenessReader
from snap_tap.backends.android.uiautomator2.xml_dump import Uiautomator2XmlDumper, dump_device_xml
from snap_tap.snapshots import DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT


@dataclass(frozen=True)
class MobileDependencies:
    discovery: DeviceDiscovery
    backend: DriverBackend
    lifecycle_runner: DriverLifecycleRunner
    xml_dumper: DriverXmlDumper
    screenshot_capturer: DriverScreenshotCapturer | None = None
    app_reader: DriverAppAwarenessReader | None = None
    primitive_tapper: PrimitiveTapper | None = None
    primitive_tap_executor: PrimitiveTapExecutor | None = None
    primitive_texter: PrimitiveTexter | None = None
    primitive_text_executor: PrimitiveTextExecutor | None = None
    primitive_navigator: PrimitiveNavigator | None = None
    primitive_navigation_executor: PrimitiveNavigationExecutor | None = None
    latest_cache_root: Path = DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT


def build_mobile_app(deps: MobileDependencies | None = None) -> typer.Typer:
    dependencies = deps or _default_dependencies()
    app = typer.Typer(no_args_is_help=True)

    @app.command("devices")
    def devices() -> None:
        snapshot = read_visible_devices(dependencies.discovery)
        if snapshot.error is not None:
            emit_json(devices_failure_payload(snapshot.error))
            raise typer.Exit(code=1)
        visible = snapshot.devices
        emit_json(
            {
                "ok": True,
                "count": len(visible),
                "devices": [device_to_dict(device) for device in visible],
            }
        )

    @app.command("status")
    def status(
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to inspect."),
        ] = None,
        all_devices: Annotated[
            bool,
            typer.Option("--all", help="Inspect every visible Android device."),
        ] = False,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Per-device timeout."),
        ] = 5.0,
    ) -> None:
        if all_devices and device is not None:
            health = blocked_health(
                backend=dependencies.backend.backend_name,
                code="invalid_arguments",
                detail="Use either --all or --device, not both.",
                device_id=device,
            )
            _emit_status_result(health)
        snapshot = read_visible_devices(dependencies.discovery)
        if snapshot.error is not None:
            health = discovery_health_failure(
                snapshot.error,
                backend=dependencies.backend.backend_name,
                device_id=device,
            )
            if all_devices:
                emit_json(
                    {
                        "ok": False,
                        "count": 1,
                        "results": [health_to_dict(health)],
                    }
                )
                raise typer.Exit(code=1)
            _emit_status_result(health)
            return
        visible = snapshot.devices
        if all_devices:
            results = [
                check_device_health(
                    backend=dependencies.backend,
                    devices=visible,
                    requested_serial=visible_device.serial,
                    timeout_s=timeout_s,
                )
                for visible_device in visible
            ]
            payload = {
                "ok": bool(results) and all(result.ok for result in results),
                "count": len(results),
                "results": [health_to_dict(result) for result in results],
            }
            emit_json(payload)
            if payload["ok"] is not True:
                raise typer.Exit(code=1)
            return

        health = check_device_health(
            backend=dependencies.backend,
            devices=visible,
            requested_serial=device,
            timeout_s=timeout_s,
        )
        _emit_status_result(health)

    @app.command("init")
    def init(
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to prepare."),
        ] = None,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 60.0,
    ) -> None:
        _run_lifecycle(
            dependencies=dependencies,
            operation="init",
            device=device,
            timeout_s=timeout_s,
        )

    @app.command("doctor")
    def doctor(
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to diagnose."),
        ] = None,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 60.0,
    ) -> None:
        _run_lifecycle(
            dependencies=dependencies,
            operation="doctor",
            device=device,
            timeout_s=timeout_s,
        )

    @app.command("dump-xml")
    def dump_xml(
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to read."),
        ] = None,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 10.0,
    ) -> None:
        snapshot = read_visible_devices(dependencies.discovery)
        if snapshot.error is not None:
            result = discovery_xml_failure(
                snapshot.error,
                backend=dependencies.xml_dumper.backend_name,
                device_id=device,
            )
            _emit_xml_dump_result(result)
            return
        visible = snapshot.devices
        result = _dump_xml_result(
            dependencies=dependencies,
            visible=visible,
            device=device,
            timeout_s=timeout_s,
        )
        _emit_xml_dump_result(result)

    @app.command("screenshot")
    def screenshot(
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to capture."),
        ] = None,
        out: Annotated[
            Path | None,
            typer.Option("--out", help="Explicit PNG output path."),
        ] = None,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 10.0,
    ) -> None:
        run_screenshot_command(
            dependencies=dependencies,
            device=device,
            out=out,
            timeout_s=timeout_s,
        )

    register_app_awareness_commands(app, dependencies)
    register_primitive_tap_command(app, dependencies)
    register_primitive_text_commands(app, dependencies)
    register_primitive_navigation_commands(app, dependencies)
    register_snap_commands(app, dependencies)
    register_snapshot_commands(app, dependencies)
    register_tap_command(app, dependencies)
    register_text_commands(app, dependencies)
    register_navigation_commands(app, dependencies)

    return app


def _run_lifecycle(
    *,
    dependencies: MobileDependencies,
    operation: str,
    device: str | None,
    timeout_s: float,
) -> None:
    if device is None:
        result = DriverLifecycleResult.failure(
            backend=dependencies.lifecycle_runner.backend_name,
            operation=operation,
            code="device_required",
            detail=f"Pass --device to run mobile {operation}.",
            elapsed_ms=0.0,
            status="blocked",
        )
        _emit_lifecycle_result(result)
        return

    snapshot = read_visible_devices(dependencies.discovery)
    if snapshot.error is not None:
        result = discovery_lifecycle_failure(
            snapshot.error,
            backend=dependencies.lifecycle_runner.backend_name,
            operation=operation,
            device_id=device,
        )
        _emit_lifecycle_result(result)
        return
    visible = snapshot.devices
    selection = select_device(visible, device)
    if not selection.ok or selection.device is None:
        result = DriverLifecycleResult.failure(
            backend=dependencies.lifecycle_runner.backend_name,
            operation=operation,
            code=selection.error_code or "device_offline",
            detail=selection.error_detail or "Device selection failed.",
            device_id=selection.device.serial if selection.device else device,
            elapsed_ms=0.0,
            status="blocked",
        )
        _emit_lifecycle_result(result)
        return
    result = dependencies.lifecycle_runner.run(
        operation=operation,
        device_id=selection.device.serial,
        timeout_s=timeout_s,
    )
    _emit_lifecycle_result(result)


def _emit_status_result(health: DriverHealth) -> None:
    emit_json({"ok": health.ok, "result": health_to_dict(health)})
    if not health.ok:
        raise typer.Exit(code=1)


def _emit_lifecycle_result(result: DriverLifecycleResult) -> None:
    emit_json({"ok": result.ok, "result": lifecycle_to_dict(result)})
    if not result.ok:
        raise typer.Exit(code=1)


def _dump_xml_result(
    *,
    dependencies: MobileDependencies,
    visible: list[DeviceInfo],
    device: str | None,
    timeout_s: float,
) -> DriverXmlDump:
    return dump_device_xml(
        dumper=dependencies.xml_dumper,
        devices=visible,
        requested_serial=device,
        timeout_s=timeout_s,
    )


def _emit_xml_dump_result(result: DriverXmlDump) -> None:
    emit_json({"ok": result.ok, "result": xml_dump_to_dict(result)})
    if not result.ok:
        raise typer.Exit(code=1)


def _default_dependencies() -> MobileDependencies:
    return MobileDependencies(
        discovery=AdbDeviceDiscovery(),
        backend=Uiautomator2Backend(),
        lifecycle_runner=Uiautomator2LifecycleRunner(),
        xml_dumper=Uiautomator2XmlDumper(),
        screenshot_capturer=Uiautomator2ScreenshotCapturer(),
        app_reader=Uiautomator2AppAwarenessReader(),
    )


app = build_mobile_app()
