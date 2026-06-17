from __future__ import annotations

from typing import Annotated, Protocol

import typer

from snap_tap.backends.android.uiautomator2.navigation import (
    NAVIGATION_BACK,
    NAVIGATION_HOME,
    NAVIGATION_SWIPE,
    NAVIGATION_UNLOCK,
    NAVIGATION_WAKE,
    Uiautomator2Navigator,
)
from snap_tap.backends.android.uiautomator2.screenshot import (
    Uiautomator2ScreenshotCapturer,
)
from snap_tap.backends.contracts import DriverScreenshotCapturer, DriverXmlDumper
from snap_tap.cli.mobile.device_discovery import read_command_devices
from snap_tap.cli.mobile.primitive_result_output import emit_primitive_receipt
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.device.identity import normalize_serial
from snap_tap.primitives import (
    NAVIGATION_WAIT,
    CorePrimitiveSnapshotProvider,
    PrimitiveNavigationRequest,
    PrimitiveNavigator,
    PrimitiveReceipt,
    invalid_request_receipt,
    navigation_primitive,
)
from snap_tap.primitives.navigation_request import (
    invalid_navigation_request_detail,
    navigation_request_payload,
    safe_navigation_operation,
)


class PrimitiveNavigationExecutor(Protocol):
    def run(self, request: PrimitiveNavigationRequest) -> PrimitiveReceipt: ...


class PrimitiveNavigationDependencies(Protocol):
    @property
    def discovery(self) -> DeviceDiscovery: ...

    @property
    def xml_dumper(self) -> DriverXmlDumper: ...

    @property
    def screenshot_capturer(self) -> DriverScreenshotCapturer | None: ...

    @property
    def primitive_navigator(self) -> PrimitiveNavigator | None: ...

    @property
    def primitive_navigation_executor(self) -> PrimitiveNavigationExecutor | None: ...


def register_primitive_navigation_commands(
    app: typer.Typer,
    dependencies: PrimitiveNavigationDependencies,
) -> None:
    @app.command("primitive-back")
    def primitive_back(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        run_primitive_navigation_request(
            dependencies=dependencies,
            request=PrimitiveNavigationRequest(
                device_id=device,
                operation=NAVIGATION_BACK,
                timeout_s=timeout_s,
                lease_timeout_s=lease_timeout_s,
            ),
            json_output=json_output,
        )

    @app.command("primitive-home")
    def primitive_home(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        run_primitive_navigation_request(
            dependencies=dependencies,
            request=PrimitiveNavigationRequest(
                device_id=device,
                operation=NAVIGATION_HOME,
                timeout_s=timeout_s,
                lease_timeout_s=lease_timeout_s,
            ),
            json_output=json_output,
        )

    @app.command("primitive-wake")
    def primitive_wake(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        run_primitive_navigation_request(
            dependencies=dependencies,
            request=PrimitiveNavigationRequest(
                device_id=device,
                operation=NAVIGATION_WAKE,
                timeout_s=timeout_s,
                lease_timeout_s=lease_timeout_s,
            ),
            json_output=json_output,
        )

    @app.command("primitive-unlock")
    def primitive_unlock(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        run_primitive_navigation_request(
            dependencies=dependencies,
            request=PrimitiveNavigationRequest(
                device_id=device,
                operation=NAVIGATION_UNLOCK,
                timeout_s=timeout_s,
                lease_timeout_s=lease_timeout_s,
            ),
            json_output=json_output,
        )

    @app.command("primitive-swipe")
    def primitive_swipe(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        direction: Annotated[str, typer.Option("--direction", help="Swipe direction.")],
        distance_ratio: Annotated[
            float,
            typer.Option("--distance-ratio", help="Viewport distance ratio."),
        ] = 0.55,
        duration_ms: Annotated[
            int,
            typer.Option("--duration-ms", help="Swipe duration in milliseconds."),
        ] = 300,
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        run_primitive_navigation_request(
            dependencies=dependencies,
            request=PrimitiveNavigationRequest(
                device_id=device,
                operation=NAVIGATION_SWIPE,
                direction=direction,
                distance_ratio=distance_ratio,
                duration_ms=duration_ms,
                timeout_s=timeout_s,
                lease_timeout_s=lease_timeout_s,
            ),
            json_output=json_output,
        )

    @app.command("primitive-wait")
    def primitive_wait(
        device: Annotated[str, typer.Option("--device", "-d", help="ADB serial.")],
        seconds: Annotated[float, typer.Option("--seconds", help="Wait seconds.")],
        json_output: Annotated[bool, typer.Option("--json")] = False,
        timeout_s: Annotated[float, typer.Option("--timeout-s")] = 10.0,
        lease_timeout_s: Annotated[float, typer.Option("--lease-timeout-s")] = 30.0,
    ) -> None:
        run_primitive_navigation_request(
            dependencies=dependencies,
            request=PrimitiveNavigationRequest(
                device_id=device,
                operation=NAVIGATION_WAIT,
                seconds=seconds,
                timeout_s=timeout_s,
                lease_timeout_s=lease_timeout_s,
            ),
            json_output=json_output,
        )


def run_primitive_navigation_request(
    *,
    dependencies: PrimitiveNavigationDependencies,
    request: PrimitiveNavigationRequest,
    json_output: bool,
) -> None:
    del json_output
    emit_primitive_receipt(
        execute_primitive_navigation_request(
            dependencies=dependencies,
            request=request,
        )
    )


def execute_primitive_navigation_request(
    *,
    dependencies: PrimitiveNavigationDependencies,
    request: PrimitiveNavigationRequest,
) -> PrimitiveReceipt:
    serial = normalize_serial(request.device_id)
    invalid_detail = invalid_navigation_request_detail(request, serial)
    if invalid_detail is not None:
        return invalid_request_receipt(
            device_id=serial,
            request=navigation_request_payload(request),
            detail=invalid_detail,
            operation=safe_navigation_operation(request.operation),
        )
    assert serial is not None
    normalized = PrimitiveNavigationRequest(
        device_id=serial,
        operation=request.operation,
        direction=request.direction,
        distance_ratio=request.distance_ratio,
        duration_ms=request.duration_ms,
        seconds=request.seconds,
        timeout_s=request.timeout_s,
        lease_timeout_s=request.lease_timeout_s,
        post_action_settle_ms=request.post_action_settle_ms,
    )
    executor = dependencies.primitive_navigation_executor
    if executor is not None:
        return executor.run(normalized)
    visible = read_command_devices(
        dependencies.discovery,
        requested_serial=serial,
    )
    if visible.error is not None:
        return invalid_request_receipt(
            device_id=serial,
            request=navigation_request_payload(normalized),
            detail=visible.error.detail,
            operation=normalized.operation,
        )
    provider = CorePrimitiveSnapshotProvider(
        devices=visible.devices,
        xml_dumper=dependencies.xml_dumper,
        screenshot_capturer=_screenshot_capturer(dependencies),
    )
    return navigation_primitive(
        normalized,
        snapshot_provider=provider,
        navigator=dependencies.primitive_navigator or Uiautomator2Navigator(),
    )


def _screenshot_capturer(
    dependencies: PrimitiveNavigationDependencies,
) -> DriverScreenshotCapturer:
    return dependencies.screenshot_capturer or Uiautomator2ScreenshotCapturer()
