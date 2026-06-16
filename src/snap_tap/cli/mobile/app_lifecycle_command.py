from __future__ import annotations

from pathlib import Path
from typing import Annotated, Protocol

import typer

from snap_tap.backends.android.uiautomator2.app_lifecycle import (
    Uiautomator2AppLifecycle,
)
from snap_tap.backends.android.uiautomator2.screenshot import (
    Uiautomator2ScreenshotCapturer,
)
from snap_tap.backends.contracts import (
    DriverAppCatalog,
    DriverAppLifecycle,
    DriverError,
    DriverScreenshotCapturer,
    DriverXmlDumper,
    normalize_package,
    read_device_launchable_apps,
)
from snap_tap.cli.mobile.device_discovery import (
    read_visible_devices,
    resolve_requested_serial,
)
from snap_tap.cli.mobile.primitive_result_output import emit_primitive_result
from snap_tap.cli.output import app_catalog_to_dict, emit_json
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.primitives import (
    CorePrimitiveSnapshotProvider,
    PrimitiveAppOpener,
    PrimitiveAppOpenRequest,
    PrimitiveReceipt,
    app_open_primitive,
    invalid_request_receipt,
)
from snap_tap.primitives.app_open_request import app_open_request_payload
from snap_tap.snapshots import (
    DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    LatestSnapshotRefError,
    normalize_latest_snapshot_session_id,
)


class AppOpenExecutor(Protocol):
    def run(self, request: PrimitiveAppOpenRequest) -> PrimitiveReceipt: ...


class AppLifecycleDependencies(Protocol):
    @property
    def discovery(self) -> DeviceDiscovery: ...

    @property
    def xml_dumper(self) -> DriverXmlDumper: ...

    @property
    def screenshot_capturer(self) -> DriverScreenshotCapturer | None: ...

    @property
    def app_lifecycle(self) -> DriverAppLifecycle | None: ...

    @property
    def primitive_app_opener(self) -> PrimitiveAppOpener | None: ...

    @property
    def primitive_app_open_executor(self) -> AppOpenExecutor | None: ...

    @property
    def latest_cache_root(self) -> Path: ...


def register_app_lifecycle_commands(
    app: typer.Typer,
    dependencies: AppLifecycleDependencies,
) -> None:
    @app.command("apps")
    def apps(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to inspect."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to inspect."),
        ] = None,
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Emit machine-readable JSON."),
        ] = False,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 5.0,
    ) -> None:
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        lifecycle = _app_lifecycle(dependencies)
        if serial_error is not None:
            _emit_apps_result(
                DriverAppCatalog.failure(
                    backend=lifecycle.backend_name,
                    code=serial_error.code,
                    detail=serial_error.detail,
                    device_id=serial or device,
                    elapsed_ms=0.0,
                    status="blocked",
                ),
                json_output=json_output,
            )
            return
        snapshot = read_visible_devices(dependencies.discovery)
        if snapshot.error is not None:
            _emit_apps_result(
                DriverAppCatalog.failure(
                    backend=lifecycle.backend_name,
                    code=snapshot.error.code,
                    detail=snapshot.error.detail,
                    device_id=requested_serial,
                    elapsed_ms=0.0,
                    status="blocked",
                ),
                json_output=json_output,
            )
            return
        result = read_device_launchable_apps(
            lifecycle=lifecycle,
            devices=snapshot.devices,
            requested_serial=requested_serial,
            timeout_s=timeout_s,
        )
        _emit_apps_result(result, json_output=json_output)

    @app.command("app-open")
    def app_open(
        serial_or_app: Annotated[
            str | None,
            typer.Argument(help="ADB serial or app package/component."),
        ] = None,
        app_target: Annotated[
            str | None,
            typer.Argument(help="App package or package/activity component."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial."),
        ] = None,
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Emit primitive_result.v1 JSON."),
        ] = False,
        session: Annotated[
            str,
            typer.Option("--session", help="Latest snap source cache session id."),
        ] = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 10.0,
        lease_timeout_s: Annotated[
            float,
            typer.Option("--lease-timeout-s", min=0.001, help="Lease timeout."),
        ] = 30.0,
    ) -> None:
        requested_device, target, arg_error = _app_open_arguments(
            serial_or_app=serial_or_app,
            app_target=app_target,
            device=device,
        )
        package, activity, target_error = _parse_app_target(target)
        if arg_error is not None or target_error is not None:
            error = arg_error or target_error
            assert error is not None
            emit_primitive_result(
                invalid_request_receipt(
                    device_id=requested_device,
                    request={
                        "operation": "app_open",
                        "device_id": requested_device,
                        "query": target or "",
                    },
                    code=error.code,
                    detail=error.detail,
                    operation="app_open",
                ),
                dependencies=dependencies,
                session_id=session,
                json_output=json_output,
            )
            return
        try:
            normalized_session = normalize_latest_snapshot_session_id(session)
        except LatestSnapshotRefError as exc:
            emit_primitive_result(
                invalid_request_receipt(
                    device_id=requested_device,
                    request={
                        "operation": "app_open",
                        "device_id": requested_device,
                        "query": target or "",
                        "session_id": session,
                    },
                    code=exc.code,
                    detail=exc.detail,
                    operation="app_open",
                ),
                dependencies=dependencies,
                session_id=session,
                json_output=json_output,
            )
            return
        assert package is not None
        receipt = execute_primitive_app_open_request(
            dependencies=dependencies,
            request=PrimitiveAppOpenRequest(
                device_id=requested_device or "",
                query=target or package,
                package=package,
                activity=activity,
                timeout_s=timeout_s,
                lease_timeout_s=lease_timeout_s,
            ),
        )
        emit_primitive_result(
            receipt,
            dependencies=dependencies,
            session_id=normalized_session,
            json_output=json_output,
        )


def execute_primitive_app_open_request(
    *,
    dependencies: AppLifecycleDependencies,
    request: PrimitiveAppOpenRequest,
) -> PrimitiveReceipt:
    executor = dependencies.primitive_app_open_executor
    if executor is not None:
        return executor.run(request)
    snapshot = read_visible_devices(dependencies.discovery)
    if snapshot.error is not None:
        return invalid_request_receipt(
            device_id=request.device_id,
            request=app_open_request_payload(request),
            code=snapshot.error.code,
            detail=snapshot.error.detail,
            operation="app_open",
        )
    provider = CorePrimitiveSnapshotProvider(
        devices=snapshot.devices,
        xml_dumper=dependencies.xml_dumper,
        screenshot_capturer=_screenshot_capturer(dependencies),
    )
    return app_open_primitive(
        request,
        snapshot_provider=provider,
        opener=dependencies.primitive_app_opener or _app_lifecycle(dependencies),
    )


def _emit_apps_result(
    result: DriverAppCatalog,
    *,
    json_output: bool,
) -> None:
    if json_output:
        emit_json({"ok": result.ok, "result": app_catalog_to_dict(result)})
    else:
        _emit_apps_table(result)
    if not result.ok:
        raise typer.Exit(code=1)


def _emit_apps_table(result: DriverAppCatalog) -> None:
    if not result.apps:
        typer.echo("No launchable apps found.")
        return
    typer.echo(_format_row(["PACKAGE", "ACTIVITY"]))
    for app in result.apps:
        typer.echo(_format_row([app.package, app.activity or "-"]))


def _format_row(values: list[str]) -> str:
    widths = [38, 52]
    return "  ".join(
        _format_cell(value, width)
        for value, width in zip(values, widths, strict=False)
    )


def _format_cell(value: str, width: int) -> str:
    text = value.strip() or "-"
    if len(text) > width:
        return text[: width - 1] + "~"
    return text.ljust(width)



def _app_open_arguments(
    *,
    serial_or_app: str | None,
    app_target: str | None,
    device: str | None,
) -> tuple[str | None, str | None, DriverError | None]:
    if app_target is None:
        return device, serial_or_app, None
    if device is not None:
        return (
            device,
            app_target,
            DriverError(
                code="invalid_arguments",
                detail="Use either positional serial or --device, not both.",
            ),
        )
    return serial_or_app, app_target, None


def _parse_app_target(
    target: str | None,
) -> tuple[str | None, str | None, DriverError | None]:
    if target is None or not target.strip():
        return (
            None,
            None,
            DriverError(
                code="app_unavailable",
                detail="Pass an app package or package/activity component.",
            ),
        )
    text = target.strip()
    if "/" not in text:
        package = normalize_package(text)
        if package is None or "." not in package:
            return (
                None,
                None,
                DriverError(
                    code="app_unavailable",
                    detail="App target must be a valid package or component.",
                ),
            )
        return package, None, None
    package_text, activity_text = text.split("/", 1)
    package = normalize_package(package_text)
    activity = activity_text.strip()
    if package is None or "." not in package or not activity:
        return (
            None,
            None,
            DriverError(
                code="app_unavailable",
                detail="App component must look like package/activity.",
            ),
        )
    return package, activity, None


def _app_lifecycle(dependencies: AppLifecycleDependencies) -> DriverAppLifecycle:
    return dependencies.app_lifecycle or Uiautomator2AppLifecycle()


def _screenshot_capturer(
    dependencies: AppLifecycleDependencies,
) -> DriverScreenshotCapturer:
    return dependencies.screenshot_capturer or Uiautomator2ScreenshotCapturer()
