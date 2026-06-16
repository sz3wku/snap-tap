from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Protocol

import typer

from snap_tap.backends.android.uiautomator2.app_awareness import (
    Uiautomator2AppAwarenessReader,
)
from snap_tap.backends.contracts import (
    DriverAppAwareness,
    DriverAppAwarenessReader,
    normalize_package,
    read_device_app_current,
    read_device_package_info,
)
from snap_tap.cli.mobile.device_discovery import (
    read_command_devices,
    read_visible_devices,
    resolve_requested_serial,
)
from snap_tap.cli.output import app_awareness_to_dict, emit_json
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.device.identity import DeviceInfo


class AppAwarenessDependencies(Protocol):
    @property
    def discovery(self) -> DeviceDiscovery: ...

    @property
    def app_reader(self) -> DriverAppAwarenessReader | None: ...


def register_app_awareness_commands(
    app: typer.Typer,
    dependencies: AppAwarenessDependencies,
) -> None:
    @app.command("app-current")
    def app_current(
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
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Per-device timeout."),
        ] = 5.0,
    ) -> None:
        reader = _reader(dependencies)
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            _emit_app_result(
                _blocked_result(
                    reader=reader,
                    operation="app_current",
                    code=serial_error.code,
                    detail=serial_error.detail,
                    device_id=serial or device,
                )
            )
            return
        if all_devices and requested_serial is not None:
            _emit_app_result(
                _blocked_result(
                    reader=reader,
                    operation="app_current",
                    code="invalid_arguments",
                    detail="Use either --all or an explicit device serial, not both.",
                    device_id=requested_serial,
                )
            )
            return

        snapshot = (
            read_visible_devices(dependencies.discovery)
            if all_devices
            else read_command_devices(
                dependencies.discovery,
                requested_serial=requested_serial,
            )
        )
        if snapshot.error is not None:
            result = _blocked_result(
                reader=reader,
                operation="app_current",
                code=snapshot.error.code,
                detail=snapshot.error.detail,
                device_id=requested_serial,
            )
            if all_devices:
                _emit_all_results([result])
                return
            _emit_app_result(result)
            return
        visible = snapshot.devices
        if all_devices:
            results = [
                read_device_app_current(
                    reader=reader,
                    devices=visible,
                    requested_serial=visible_device.serial,
                    timeout_s=timeout_s,
                )
                for visible_device in visible
            ]
            _emit_all_results(results)
            return

        result = read_device_app_current(
            reader=reader,
            devices=visible,
            requested_serial=requested_serial,
            timeout_s=timeout_s,
        )
        _emit_app_result(result)

    @app.command("package-info")
    def package_info(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to inspect."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to inspect."),
        ] = None,
        package: Annotated[
            str | None,
            typer.Option("--package", help="Android package name to inspect."),
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
        reader = _reader(dependencies)
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            _emit_app_result(
                _blocked_result(
                    reader=reader,
                    operation="package_info",
                    code=serial_error.code,
                    detail=serial_error.detail,
                    device_id=serial or device,
                )
            )
            return
        if all_devices and requested_serial is not None:
            _emit_app_result(
                _blocked_result(
                    reader=reader,
                    operation="package_info",
                    code="invalid_arguments",
                    detail="Use either --all or an explicit device serial, not both.",
                    device_id=requested_serial,
                )
            )
            return

        package_name = normalize_package(package)
        snapshot = (
            read_visible_devices(dependencies.discovery)
            if all_devices
            else read_command_devices(
                dependencies.discovery,
                requested_serial=requested_serial,
            )
        )
        if snapshot.error is not None:
            result = _blocked_result(
                reader=reader,
                operation="package_info",
                code=snapshot.error.code,
                detail=snapshot.error.detail,
                device_id=requested_serial,
            )
            if all_devices:
                _emit_all_results([result])
                return
            _emit_app_result(result)
            return
        visible = snapshot.devices
        if all_devices:
            if package_name is None:
                results = _blocked_all_package_results(reader, visible)
            else:
                results = [
                    read_device_package_info(
                        reader=reader,
                        devices=visible,
                        requested_serial=visible_device.serial,
                        package=package_name,
                        timeout_s=timeout_s,
                    )
                    for visible_device in visible
                ]
            _emit_all_results(results)
            return

        result = read_device_package_info(
            reader=reader,
            devices=visible,
            requested_serial=requested_serial,
            package=package or "",
            timeout_s=timeout_s,
        )
        _emit_app_result(result)

    app.command("app-info")(package_info)


def _emit_app_result(result: DriverAppAwareness) -> None:
    emit_json({"ok": result.ok, "result": app_awareness_to_dict(result)})
    if not result.ok:
        raise typer.Exit(code=1)


def _emit_all_results(results: Sequence[DriverAppAwareness]) -> None:
    payload = {
        "ok": bool(results) and all(result.ok for result in results),
        "count": len(results),
        "results": [app_awareness_to_dict(result) for result in results],
    }
    emit_json(payload)
    if payload["ok"] is not True:
        raise typer.Exit(code=1)


def _blocked_all_package_results(
    reader: DriverAppAwarenessReader,
    visible: Sequence[DeviceInfo],
) -> list[DriverAppAwareness]:
    if not visible:
        return [
            _blocked_result(
                reader=reader,
                operation="package_info",
                code="app_unavailable",
                detail="Package is required and must be a valid Android package name.",
                device_id=None,
            )
        ]
    return [
        _blocked_result(
            reader=reader,
            operation="package_info",
            code="app_unavailable",
            detail="Package is required and must be a valid Android package name.",
            device_id=device.serial,
        )
        for device in visible
    ]


def _blocked_result(
    *,
    reader: DriverAppAwarenessReader,
    operation: str,
    code: str,
    detail: str,
    device_id: str | None,
) -> DriverAppAwareness:
    return DriverAppAwareness.failure(
        backend=reader.backend_name,
        operation=operation,
        code=code,
        detail=detail,
        device_id=device_id,
        elapsed_ms=0.0,
        status="blocked",
    )


def _reader(dependencies: AppAwarenessDependencies) -> DriverAppAwarenessReader:
    return dependencies.app_reader or Uiautomator2AppAwarenessReader()
