from __future__ import annotations

from typing import Annotated, Protocol

import typer

from snap_tap.cli.mobile.primitive_navigation_command import (
    PrimitiveNavigationDependencies,
    run_primitive_navigation_request,
)
from snap_tap.backends.android.uiautomator2.navigation import NAVIGATION_BACK, NAVIGATION_HOME, NAVIGATION_SWIPE
from snap_tap.primitives import NAVIGATION_WAIT, PrimitiveNavigationRequest


class NavigationAliasDependencies(PrimitiveNavigationDependencies, Protocol):
    pass


def register_navigation_commands(
    app: typer.Typer,
    dependencies: NavigationAliasDependencies,
) -> None:
    @app.command("back")
    def back(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        _run(
            dependencies=dependencies,
            device=device,
            operation=NAVIGATION_BACK,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )

    @app.command("home")
    def home(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        _run(
            dependencies=dependencies,
            device=device,
            operation=NAVIGATION_HOME,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )

    @app.command("swipe")
    def swipe(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        direction: Annotated[str, typer.Option("--direction", help="Swipe direction.")],
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        _run(
            dependencies=dependencies,
            device=device,
            operation=NAVIGATION_SWIPE,
            direction=direction,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )

    @app.command("wait")
    def wait(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        seconds: Annotated[float, typer.Option("--seconds", help="Wait seconds.")],
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        _run(
            dependencies=dependencies,
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
    device: str,
    operation: str,
    json_output: bool,
    timeout_s: float,
    lease_timeout_s: float,
    direction: str | None = None,
    seconds: float = 1.0,
) -> None:
    run_primitive_navigation_request(
        dependencies=dependencies,
        request=PrimitiveNavigationRequest(
            device_id=device,
            operation=operation,
            direction=direction,
            seconds=seconds,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        ),
        json_output=json_output,
    )
