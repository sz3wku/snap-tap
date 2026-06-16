from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Protocol

import typer

from snap_tap.backends.android.uiautomator2.screenshot import (
    Uiautomator2ScreenshotCapturer,
)
from snap_tap.backends.android.uiautomator2.text import (
    TEXT_INPUT_MODE,
    TEXT_REPLACE_MODE,
    Uiautomator2Texter,
)
from snap_tap.backends.contracts import DriverScreenshotCapturer, DriverXmlDumper
from snap_tap.cli.mobile.device_discovery import read_command_devices
from snap_tap.cli.mobile.primitive_result_output import emit_primitive_receipt
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.device.identity import normalize_serial
from snap_tap.primitives import (
    CorePrimitiveSnapshotProvider,
    PrimitiveReceipt,
    PrimitiveRequestError,
    PrimitiveTexter,
    PrimitiveTextRequest,
    invalid_request_receipt,
    resolved_text,
    target_signature_from_dict,
)


class PrimitiveTextExecutor(Protocol):
    def input_text(self, request: PrimitiveTextRequest) -> PrimitiveReceipt: ...


class PrimitiveTextDependencies(Protocol):
    @property
    def discovery(self) -> DeviceDiscovery: ...

    @property
    def xml_dumper(self) -> DriverXmlDumper: ...

    @property
    def screenshot_capturer(self) -> DriverScreenshotCapturer | None: ...

    @property
    def primitive_texter(self) -> PrimitiveTexter | None: ...

    @property
    def primitive_text_executor(self) -> PrimitiveTextExecutor | None: ...


def register_primitive_text_commands(
    app: typer.Typer,
    dependencies: PrimitiveTextDependencies,
) -> None:
    @app.command("primitive-input")
    def primitive_input(
        device: Annotated[
            str,
            typer.Option("--device", "-d", help="ADB serial for text input."),
        ],
        signature_file: Annotated[
            Path,
            typer.Option(
                "--signature-file",
                help="target_signature.v1 JSON file.",
            ),
        ],
        text: Annotated[
            str,
            typer.Option("--text", help="Text payload to input."),
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
        run_primitive_text_command(
            dependencies=dependencies,
            device=device,
            signature_file=signature_file,
            text=text,
            mode=TEXT_INPUT_MODE,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )

    @app.command("primitive-replace-text")
    def primitive_replace_text(
        device: Annotated[
            str,
            typer.Option("--device", "-d", help="ADB serial for replace text."),
        ],
        signature_file: Annotated[
            Path,
            typer.Option(
                "--signature-file",
                help="target_signature.v1 JSON file.",
            ),
        ],
        text: Annotated[
            str,
            typer.Option("--text", help="Replacement text payload."),
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
        run_primitive_text_command(
            dependencies=dependencies,
            device=device,
            signature_file=signature_file,
            text=text,
            mode=TEXT_REPLACE_MODE,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )


def run_primitive_text_command(
    *,
    dependencies: PrimitiveTextDependencies,
    device: str,
    signature_file: Path,
    text: str,
    mode: str,
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
                request=_request_metadata(mode=mode, device_id=device, text=text),
                detail="Device serial is required and must be a valid ADB serial.",
                operation=mode,
            )
        )
        return
    if _normalized_text(text) is None:
        _emit_receipt(
            invalid_request_receipt(
                device_id=serial,
                request=_request_metadata(mode=mode, device_id=serial, text=text),
                detail="Text payload must be non-empty normalized text.",
                operation=mode,
            )
        )
        return
    try:
        signature = target_signature_from_dict(_read_signature_file(signature_file))
    except PrimitiveRequestError as exc:
        _emit_receipt(
            invalid_request_receipt(
                device_id=serial,
                request=_request_metadata(mode=mode, device_id=serial, text=text),
                code=exc.code,
                detail=exc.detail,
                operation=mode,
            )
        )
        return
    request = PrimitiveTextRequest(
        device_id=serial,
        signature=signature,
        text=text,
        mode=mode,
        timeout_s=timeout_s,
        lease_timeout_s=lease_timeout_s,
    )
    execute_primitive_text_request(dependencies=dependencies, request=request)


def execute_primitive_text_request(
    *,
    dependencies: PrimitiveTextDependencies,
    request: PrimitiveTextRequest,
) -> None:
    emit_primitive_receipt(
        run_primitive_text_request(dependencies=dependencies, request=request)
    )


def run_primitive_text_request(
    *,
    dependencies: PrimitiveTextDependencies,
    request: PrimitiveTextRequest,
) -> PrimitiveReceipt:
    executor = dependencies.primitive_text_executor
    if executor is not None:
        return executor.input_text(request)

    visible = read_command_devices(
        dependencies.discovery,
        requested_serial=request.device_id,
    )
    if visible.error is not None:
        return invalid_request_receipt(
            device_id=request.device_id,
            request=_request_metadata(
                mode=request.mode,
                device_id=request.device_id,
                text=request.text,
                signature_id=request.signature.signature_id,
                source_snapshot_id=request.signature.source_snapshot_id,
            ),
            detail=visible.error.detail,
            operation=request.mode,
        )
    provider = CorePrimitiveSnapshotProvider(
        devices=visible.devices,
        xml_dumper=dependencies.xml_dumper,
        screenshot_capturer=_screenshot_capturer(dependencies),
    )
    return resolved_text(
        request,
        snapshot_provider=provider,
        texter=dependencies.primitive_texter or Uiautomator2Texter(),
    )


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
    emit_primitive_receipt(receipt)


def _screenshot_capturer(
    dependencies: PrimitiveTextDependencies,
) -> DriverScreenshotCapturer:
    return dependencies.screenshot_capturer or Uiautomator2ScreenshotCapturer()


def _request_metadata(
    *,
    mode: str,
    device_id: str,
    text: str,
    signature_id: str | None = None,
    source_snapshot_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "operation": mode,
        "device_id": device_id,
        "mode": mode,
        "text_length": len(text) if isinstance(text, str) else 0,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()
        if isinstance(text, str)
        else None,
    }
    if signature_id is not None:
        payload["signature_id"] = signature_id
    if source_snapshot_id is not None:
        payload["source_snapshot_id"] = source_snapshot_id
    return payload


def _normalized_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if not value or not value.strip() or len(value) > 4096:
        return None
    if "\x00" in value:
        return None
    return value
