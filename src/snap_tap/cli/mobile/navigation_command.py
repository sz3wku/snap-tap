from __future__ import annotations

from typing import Annotated, Protocol

import typer

from snap_tap.cli.output import emit_json
from snap_tap.cli.mobile.device_discovery import resolve_requested_serial
from snap_tap.cli.mobile.primitive_navigation_command import (
    PrimitiveNavigationDependencies,
    run_primitive_navigation_request,
)
from snap_tap.backends.android.uiautomator2.navigation import NAVIGATION_BACK, NAVIGATION_HOME, NAVIGATION_SWIPE
from snap_tap.primitives import (
    NAVIGATION_WAIT,
    PrimitiveNavigationRequest,
    invalid_request_receipt,
    primitive_receipt_to_dict,
)


class NavigationAliasDependencies(PrimitiveNavigationDependencies, Protocol):
    pass


def register_navigation_commands(
    app: typer.Typer,
    dependencies: NavigationAliasDependencies,
) -> None:
    @app.command("back")
    def back(
        serial: Annotated[str | None, typer.Argument(help="ADB serial.")] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial."),
        ] = None,
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        _run(
            dependencies=dependencies,
            serial=serial,
            device=device,
            operation=NAVIGATION_BACK,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )

    @app.command("home")
    def home(
        serial: Annotated[str | None, typer.Argument(help="ADB serial.")] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial."),
        ] = None,
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        _run(
            dependencies=dependencies,
            serial=serial,
            device=device,
            operation=NAVIGATION_HOME,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )

    @app.command("swipe")
    def swipe(
        serial: Annotated[str | None, typer.Argument(help="ADB serial.")] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial."),
        ] = None,
        direction: Annotated[
            str | None,
            typer.Option("--direction", help="Swipe direction."),
        ] = None,
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        _run(
            dependencies=dependencies,
            serial=serial,
            device=device,
            operation=NAVIGATION_SWIPE,
            direction=direction,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )

    @app.command("wait")
    def wait(
        serial: Annotated[str | None, typer.Argument(help="ADB serial.")] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial."),
        ] = None,
        seconds: Annotated[
            float,
            typer.Option("--seconds", help="Wait seconds."),
        ] = 1.0,
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        _run(
            dependencies=dependencies,
            serial=serial,
            device=device,
            operation=NAVIGATION_WAIT,
            seconds=seconds,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )


def _run(
    *,
    dependencies: NavigationAliasDependencies,
    serial: str | None,
    device: str | None,
    operation: str,
    json_output: bool,
    timeout_s: float,
    lease_timeout_s: float,
    direction: str | None = None,
    seconds: float = 1.0,
) -> None:
    requested_serial, serial_error = resolve_requested_serial(
        serial=serial,
        device=device,
    )
    if serial_error is not None:
        receipt = invalid_request_receipt(
            device_id=serial or device,
            request={
                "operation": operation,
                "device_id": serial or device,
            },
            code=serial_error.code,
            detail=serial_error.detail,
            operation=operation,
        )
        emit_json(primitive_receipt_to_dict(receipt))
        raise typer.Exit(code=1)
    run_primitive_navigation_request(
        dependencies=dependencies,
        request=PrimitiveNavigationRequest(
            device_id=requested_serial or "",
            operation=operation,
            direction=direction,
            seconds=seconds,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        ),
        json_output=json_output,
    )
