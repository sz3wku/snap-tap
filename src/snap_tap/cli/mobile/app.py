from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from snap_tap.backends.android.uiautomator2.app_awareness import (
    Uiautomator2AppAwarenessReader,
)
from snap_tap.backends.android.uiautomator2.app_lifecycle import (
    Uiautomator2AppLifecycle,
)
from snap_tap.backends.android.uiautomator2.backend import Uiautomator2Backend
from snap_tap.backends.android.uiautomator2.lifecycle import (
    Uiautomator2LifecycleRunner,
)
from snap_tap.backends.android.uiautomator2.screenshot import (
    Uiautomator2ScreenshotCapturer,
)
from snap_tap.backends.android.uiautomator2.xml_dump import (
    Uiautomator2XmlDumper,
    dump_device_xml,
)
from snap_tap.backends.contracts import (
    DriverAppAwarenessReader,
    DriverAppLifecycle,
    DriverBackend,
    DriverHealth,
    DriverLifecycleResult,
    DriverLifecycleRunner,
    DriverScreenshot,
    DriverScreenshotCapturer,
    DriverXmlDump,
    DriverXmlDumper,
    check_device_health,
)
from snap_tap.cli.mobile.app_awareness_command import register_app_awareness_commands
from snap_tap.cli.mobile.app_lifecycle_command import (
    AppOpenExecutor,
    register_app_lifecycle_commands,
)
from snap_tap.cli.mobile.device_discovery import (
    blocked_health,
    devices_failure_payload,
    discovery_health_failure,
    discovery_lifecycle_failure,
    discovery_xml_failure,
    read_visible_devices,
    resolve_requested_serial,
)
from snap_tap.cli.mobile.navigation_command import register_navigation_commands
from snap_tap.cli.mobile.primitive_navigation_command import (
    PrimitiveNavigationExecutor,
    register_primitive_navigation_commands,
)
from snap_tap.cli.mobile.primitive_tap_command import (
    PrimitiveTapExecutor,
    register_primitive_tap_command,
)
from snap_tap.cli.mobile.primitive_text_command import (
    PrimitiveTextExecutor,
    register_primitive_text_commands,
)
from snap_tap.cli.mobile.screenshot_command import run_screenshot_command
from snap_tap.cli.mobile.snap_command import register_snap_commands
from snap_tap.cli.mobile.snapshot_command import register_snapshot_commands
from snap_tap.cli.mobile.tap_command import register_tap_command
from snap_tap.cli.mobile.text_command import register_text_commands
from snap_tap.cli.output import (
    device_to_dict,
    emit_json,
    health_to_dict,
    lifecycle_to_dict,
    screenshot_to_dict,
    xml_dump_to_dict,
)
from snap_tap.device.discovery import AdbDeviceDiscovery, DeviceDiscovery
from snap_tap.device.identity import DeviceInfo, select_device
from snap_tap.primitives import (
    PrimitiveAppOpener,
    PrimitiveNavigator,
    PrimitiveTapper,
    PrimitiveTexter,
)
from snap_tap.snapshots import DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT


@dataclass(frozen=True)
class MobileDependencies:
    discovery: DeviceDiscovery
    backend: DriverBackend
    lifecycle_runner: DriverLifecycleRunner
    xml_dumper: DriverXmlDumper
    screenshot_capturer: DriverScreenshotCapturer | None = None
    app_reader: DriverAppAwarenessReader | None = None
    app_lifecycle: DriverAppLifecycle | None = None
    primitive_tapper: PrimitiveTapper | None = None
    primitive_tap_executor: PrimitiveTapExecutor | None = None
    primitive_texter: PrimitiveTexter | None = None
    primitive_text_executor: PrimitiveTextExecutor | None = None
    primitive_navigator: PrimitiveNavigator | None = None
    primitive_navigation_executor: PrimitiveNavigationExecutor | None = None
    primitive_app_opener: PrimitiveAppOpener | None = None
    primitive_app_open_executor: AppOpenExecutor | None = None
    latest_cache_root: Path = DEFAULT_LATEST_SNAPSHOT_CACHE_ROOT


def build_mobile_app(deps: MobileDependencies | None = None) -> typer.Typer:
    dependencies = deps or _default_dependencies()
    app = typer.Typer(no_args_is_help=True)

    @app.command("devices")
    def devices(
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Emit machine-readable JSON."),
        ] = False,
    ) -> None:
        snapshot = read_visible_devices(dependencies.discovery)
        if snapshot.error is not None:
            if json_output:
                emit_json(devices_failure_payload(snapshot.error))
            else:
                _emit_devices_failure(snapshot.error.code, snapshot.error.detail)
            raise typer.Exit(code=1)
        visible = snapshot.devices
        payload = {
            "ok": True,
            "count": len(visible),
            "devices": [device_to_dict(device) for device in visible],
        }
        if json_output:
            emit_json(payload)
            return
        _emit_devices_table(visible)

    @app.command("status")
    def status(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to inspect."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to inspect."),
        ] = None,
        all_devices: Annotated[
            bool,
            typer.Option("--all", help="Inspect every visible Android device."),
        ] = False,
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Emit machine-readable JSON."),
        ] = False,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Per-device timeout."),
        ] = 5.0,
    ) -> None:
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            health = blocked_health(
                backend=dependencies.backend.backend_name,
                code=serial_error.code,
                detail=serial_error.detail,
                device_id=serial or device,
            )
            _emit_status_result(health, json_output=json_output)
            return
        if all_devices and requested_serial is not None:
            health = blocked_health(
                backend=dependencies.backend.backend_name,
                code="invalid_arguments",
                detail="Use either --all or an explicit device serial, not both.",
                device_id=requested_serial,
            )
            _emit_status_result(health, json_output=json_output)
            return
        snapshot = read_visible_devices(dependencies.discovery)
        if snapshot.error is not None:
            health = discovery_health_failure(
                snapshot.error,
                backend=dependencies.backend.backend_name,
                device_id=requested_serial,
            )
            if all_devices:
                payload = {
                    "ok": False,
                    "count": 1,
                    "results": [health_to_dict(health)],
                }
                if json_output:
                    emit_json(payload)
                else:
                    _emit_status_table([health])
                raise typer.Exit(code=1)
            _emit_status_result(health, json_output=json_output)
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
            if json_output:
                emit_json(payload)
            else:
                _emit_status_table(results)
            if payload["ok"] is not True:
                raise typer.Exit(code=1)
            return

        health = check_device_health(
            backend=dependencies.backend,
            devices=visible,
            requested_serial=requested_serial,
            timeout_s=timeout_s,
        )
        _emit_status_result(health, json_output=json_output)

    @app.command("init")
    def init(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to prepare."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to prepare."),
        ] = None,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 60.0,
    ) -> None:
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            _emit_lifecycle_result(
                DriverLifecycleResult.failure(
                    backend=dependencies.lifecycle_runner.backend_name,
                    operation="init",
                    code=serial_error.code,
                    detail=serial_error.detail,
                    device_id=serial or device,
                    elapsed_ms=0.0,
                    status="blocked",
                )
            )
            return
        _run_lifecycle(
            dependencies=dependencies,
            operation="init",
            device=requested_serial,
            timeout_s=timeout_s,
        )

    @app.command("doctor")
    def doctor(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to diagnose."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to diagnose."),
        ] = None,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 60.0,
    ) -> None:
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            _emit_lifecycle_result(
                DriverLifecycleResult.failure(
                    backend=dependencies.lifecycle_runner.backend_name,
                    operation="doctor",
                    code=serial_error.code,
                    detail=serial_error.detail,
                    device_id=serial or device,
                    elapsed_ms=0.0,
                    status="blocked",
                )
            )
            return
        _run_lifecycle(
            dependencies=dependencies,
            operation="doctor",
            device=requested_serial,
            timeout_s=timeout_s,
        )

    @app.command("android-driver-purge")
    def android_driver_purge(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to clean up."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to clean up."),
        ] = None,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 60.0,
    ) -> None:
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            _emit_lifecycle_result(
                DriverLifecycleResult.failure(
                    backend=dependencies.lifecycle_runner.backend_name,
                    operation="purge",
                    code=serial_error.code,
                    detail=serial_error.detail,
                    device_id=serial or device,
                    elapsed_ms=0.0,
                    status="blocked",
                )
            )
            return
        _run_lifecycle(
            dependencies=dependencies,
            operation="purge",
            device=requested_serial,
            timeout_s=timeout_s,
            command_name="android-driver-purge",
        )

    @app.command("dump-xml")
    def dump_xml(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to read."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to read."),
        ] = None,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 10.0,
    ) -> None:
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            _emit_xml_dump_result(
                DriverXmlDump.failure(
                    backend=dependencies.xml_dumper.backend_name,
                    code=serial_error.code,
                    detail=serial_error.detail,
                    device_id=serial or device,
                    elapsed_ms=0.0,
                    status="blocked",
                )
            )
            return
        snapshot = read_visible_devices(dependencies.discovery)
        if snapshot.error is not None:
            result = discovery_xml_failure(
                snapshot.error,
                backend=dependencies.xml_dumper.backend_name,
                device_id=requested_serial,
            )
            _emit_xml_dump_result(result)
            return
        visible = snapshot.devices
        result = _dump_xml_result(
            dependencies=dependencies,
            visible=visible,
            device=requested_serial,
            timeout_s=timeout_s,
        )
        _emit_xml_dump_result(result)

    @app.command("screenshot")
    def screenshot(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to capture."),
        ] = None,
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
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            result = DriverScreenshot.failure(
                backend=dependencies.screenshot_capturer.backend_name
                if dependencies.screenshot_capturer is not None
                else "uiautomator2",
                code=serial_error.code,
                detail=serial_error.detail,
                device_id=serial or device,
                elapsed_ms=0.0,
                status="blocked",
            )
            emit_json(
                {
                    "ok": False,
                    "result": screenshot_to_dict(result),
                }
            )
            raise typer.Exit(code=1)
        run_screenshot_command(
            dependencies=dependencies,
            device=requested_serial,
            out=out,
            timeout_s=timeout_s,
        )

    register_app_awareness_commands(app, dependencies)
    register_app_lifecycle_commands(app, dependencies)
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
    command_name: str | None = None,
) -> None:
    if device is None:
        result = DriverLifecycleResult.failure(
            backend=dependencies.lifecycle_runner.backend_name,
            operation=operation,
            code="device_required",
            detail=(
                f"Pass a device serial to run snap-tap {command_name or operation}."
            ),
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


def _emit_devices_failure(code: str, detail: str) -> None:
    typer.echo(f"snap-tap devices blocked: {code} - {detail}")


def _emit_devices_table(devices: list[DeviceInfo]) -> None:
    if not devices:
        typer.echo("No Android devices visible.")
        return
    typer.echo(_format_row(["SERIAL", "STATE", "MODEL", "PRODUCT", "DEVICE"]))
    for device in devices:
        typer.echo(
            _format_row(
                [
                    device.serial,
                    device.state,
                    _display_value(device.model),
                    _display_value(device.product),
                    _display_value(device.device),
                ]
            )
        )


def _emit_status_result(health: DriverHealth, *, json_output: bool) -> None:
    if json_output:
        emit_json({"ok": health.ok, "result": health_to_dict(health)})
    else:
        _emit_status_line(health)
    if not health.ok:
        raise typer.Exit(code=1)


def _emit_status_table(results: list[DriverHealth]) -> None:
    if not results:
        typer.echo("No Android devices visible.")
        return
    typer.echo(_format_row(["SERIAL", "STATUS", "BACKEND", "DISPLAY", "SDK", "ELAPSED"]))
    for health in results:
        typer.echo(
            _format_row(
                [
                    _display_value(health.device_id),
                    health.status,
                    health.backend,
                    _display_size(health.metadata),
                    _display_sdk(health.metadata),
                    _display_elapsed(health.elapsed_ms),
                ]
            )
        )
        if not health.ok and health.error is not None:
            typer.echo(f"  {health.error.code}: {health.error.detail}")


def _emit_status_line(health: DriverHealth) -> None:
    if health.ok:
        typer.echo(
            "  ".join(
                [
                    _display_value(health.device_id),
                    health.status,
                    health.backend,
                    _display_size(health.metadata),
                    f"sdk {_display_sdk(health.metadata)}",
                    _display_elapsed(health.elapsed_ms),
                ]
            )
        )
        return
    if health.error is None:
        typer.echo(f"snap-tap status {health.status}: unavailable")
        return
    typer.echo(
        f"snap-tap status {health.status}: "
        f"{health.error.code} - {health.error.detail}"
    )


def _format_row(values: list[str]) -> str:
    widths = [18, 10, 18, 18, 12, 10]
    if values:
        widths[0] = max(widths[0], len(values[0]))
    return "  ".join(
        _format_cell(value, width, truncate=index != 0)
        for index, (value, width) in enumerate(zip(values, widths, strict=False))
    )


def _format_cell(value: str, width: int, *, truncate: bool) -> str:
    text = value.ljust(width)
    if truncate:
        return text[:width]
    return text


def _display_value(value: object | None) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text or "-"


def _display_size(metadata: Mapping[str, object]) -> str:
    width = metadata.get("displayWidth")
    height = metadata.get("displayHeight")
    if isinstance(width, str) and isinstance(height, str) and width and height:
        return f"{width}x{height}"
    return "-"


def _display_sdk(metadata: Mapping[str, object]) -> str:
    sdk = metadata.get("sdkInt")
    if isinstance(sdk, str) and sdk:
        return sdk
    return "-"


def _display_elapsed(elapsed_ms: float) -> str:
    return f"{elapsed_ms:.0f}ms"


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
        app_lifecycle=Uiautomator2AppLifecycle(),
    )


app = build_mobile_app()
