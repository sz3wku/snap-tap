from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Protocol

import typer

from snap_tap.backends.android.uiautomator2.screenshot import (
    Uiautomator2ScreenshotCapturer,
)
from snap_tap.backends.android.uiautomator2.tap import Uiautomator2Tapper
from snap_tap.backends.contracts import DriverScreenshotCapturer, DriverXmlDumper
from snap_tap.cli.mobile.device_discovery import read_visible_devices
from snap_tap.cli.output import emit_json
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.device.identity import normalize_serial
from snap_tap.primitives import (
    CorePrimitiveSnapshotProvider,
    PrimitiveReceipt,
    PrimitiveRequestError,
    PrimitiveTapper,
    PrimitiveTapRequest,
    invalid_request_receipt,
    primitive_receipt_to_dict,
    resolved_tap,
    target_signature_from_dict,
)


class PrimitiveTapExecutor(Protocol):
    def tap(self, request: PrimitiveTapRequest) -> PrimitiveReceipt: ...


class PrimitiveTapDependencies(Protocol):
    @property
    def discovery(self) -> DeviceDiscovery: ...

    @property
    def xml_dumper(self) -> DriverXmlDumper: ...

    @property
    def screenshot_capturer(self) -> DriverScreenshotCapturer | None: ...

    @property
    def primitive_tapper(self) -> PrimitiveTapper | None: ...

    @property
    def primitive_tap_executor(self) -> PrimitiveTapExecutor | None: ...


def register_primitive_tap_command(
    app: typer.Typer,
    dependencies: PrimitiveTapDependencies,
) -> None:
    @app.command("primitive-tap")
    def primitive_tap(
        device: Annotated[
            str,
            typer.Option("--device", "-d", help="ADB serial to tap."),
        ],
        signature_file: Annotated[
            Path,
            typer.Option(
                "--signature-file",
                help="target_signature.v1 JSON file.",
            ),
        ],
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Emit primitive_receipt.v1 JSON."),
        ] = False,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 10.0,
        lease_timeout_s: Annotated[
            float,
            typer.Option("--lease-timeout-s", min=0.001, help="Lease timeout."),
        ] = 30.0,
    ) -> None:
        run_primitive_tap_command(
            dependencies=dependencies,
            device=device,
            signature_file=signature_file,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )


def run_primitive_tap_command(
    *,
    dependencies: PrimitiveTapDependencies,
    device: str,
    signature_file: Path,
    json_output: bool,
    timeout_s: float,
    lease_timeout_s: float,
) -> None:
    del json_output
    serial = normalize_serial(device)
    if serial is None:
        _emit_receipt(
            invalid_request_receipt(
                device_id=None,
                request={"operation": "tap", "device_id": device},
                detail="Device serial is required and must be a valid ADB serial.",
            )
        )
        return
    try:
        signature = target_signature_from_dict(_read_signature_file(signature_file))
    except PrimitiveRequestError as exc:
        _emit_receipt(
            invalid_request_receipt(
                device_id=serial,
                request={"operation": "tap", "device_id": serial},
                code=exc.code,
                detail=exc.detail,
            )
        )
        return
    request = PrimitiveTapRequest(
        device_id=serial,
        signature=signature,
        timeout_s=timeout_s,
        lease_timeout_s=lease_timeout_s,
    )
    executor = dependencies.primitive_tap_executor
    if executor is not None:
        _emit_receipt(executor.tap(request))
        return

    visible = read_visible_devices(dependencies.discovery)
    if visible.error is not None:
        _emit_receipt(
            invalid_request_receipt(
                device_id=serial,
                request={
                    "operation": "tap",
                    "device_id": serial,
                    "signature_id": signature.signature_id,
                    "source_snapshot_id": signature.source_snapshot_id,
                },
                detail=visible.error.detail,
            )
        )
        return
    provider = CorePrimitiveSnapshotProvider(
        devices=visible.devices,
        xml_dumper=dependencies.xml_dumper,
        screenshot_capturer=_screenshot_capturer(dependencies),
    )
    receipt = resolved_tap(
        request,
        snapshot_provider=provider,
        tapper=dependencies.primitive_tapper or Uiautomator2Tapper(),
    )
    _emit_receipt(receipt)


def _read_signature_file(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail=f"Could not read target signature file: {exc}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail=f"Target signature file is not valid JSON: {exc.msg}",
        ) from exc
    if not isinstance(payload, Mapping):
        raise PrimitiveRequestError(
            code="primitive_invalid_request",
            detail="Target signature file must contain a JSON object.",
        )
    return payload


def _emit_receipt(receipt: PrimitiveReceipt) -> None:
    emit_json(primitive_receipt_to_dict(receipt))
    if not receipt.ok:
        raise typer.Exit(code=1)


def _screenshot_capturer(
    dependencies: PrimitiveTapDependencies,
) -> DriverScreenshotCapturer:
    return dependencies.screenshot_capturer or Uiautomator2ScreenshotCapturer()
