from __future__ import annotations

from pathlib import Path
from typing import Annotated, Protocol

import typer

from snap_tap.cli.mobile.device_discovery import read_visible_devices
from snap_tap.cli.mobile.snap_command import (
    emit_snap_table,
    write_latest_snap_source_for_snap,
)
from snap_tap.cli.output import emit_json
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.device.identity import normalize_serial
from snap_tap.backends.contracts import DriverError, DriverScreenshotCapturer
from snap_tap.backends.android.uiautomator2.tap import Uiautomator2Tapper
from snap_tap.backends.android.uiautomator2.screenshot import Uiautomator2ScreenshotCapturer
from snap_tap.backends.contracts import DriverXmlDumper
from snap_tap.primitives import (
    CorePrimitiveSnapshotProvider,
    PrimitiveReceipt,
    PrimitiveTapRequest,
    PrimitiveTapper,
    invalid_request_receipt,
    primitive_receipt_to_dict,
    resolved_tap,
)
from snap_tap.snapshots import (
    DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    LatestSnapshotRefError,
    normalize_latest_snapshot_session_id,
)
from snap_tap.snapshots.manifest_source import (
    SnapshotManifestSourceError,
    read_snapshot_manifest_source,
)
from snap_tap.targets import (
    LatestSnapSourceError,
    MobileSnap,
    TargetSignatureError,
    build_latest_snap_source,
    build_mobile_snap_from_semantic,
    build_target_signature,
    latest_snap_source_target_for_tap,
    read_latest_snap_source,
    snapshot_targets_from_latest_snap_source,
)


class TapExecutor(Protocol):
    def tap(self, request: PrimitiveTapRequest) -> PrimitiveReceipt: ...


class TapDependencies(Protocol):
    @property
    def discovery(self) -> DeviceDiscovery: ...

    @property
    def xml_dumper(self) -> DriverXmlDumper: ...

    @property
    def screenshot_capturer(self) -> DriverScreenshotCapturer | None: ...

    @property
    def primitive_tapper(self) -> PrimitiveTapper | None: ...

    @property
    def primitive_tap_executor(self) -> TapExecutor | None: ...

    @property
    def latest_cache_root(self) -> Path: ...


def register_tap_command(app: typer.Typer, dependencies: TapDependencies) -> None:
    @app.command("tap")
    def tap(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial."),
        ] = None,
        target_id: Annotated[
            str | None,
            typer.Argument(help="Snapshot-local target id from latest snap-tap snap."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option(
                "--device",
                "-d",
                help="Compatibility/debug serial alias.",
            ),
        ] = None,
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
        session: Annotated[
            str,
            typer.Option("--session", help="Latest snap source cache session id."),
        ] = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
        snapshot: Annotated[
            Path | None,
            typer.Option(
                "--snapshot",
                help="Use a snapshot manifest or capture dir as source target facts.",
            ),
        ] = None,
    ) -> None:
        requested_device, requested_target, arg_error = _tap_arguments(
            serial_or_target=serial,
            target_id=target_id,
            device=device,
        )
        if arg_error is not None:
            _emit_receipt(
                _blocked(
                    device_id=requested_device,
                    request=_request_payload(
                        device=requested_device,
                        target_id=requested_target,
                        session=session,
                        snapshot=snapshot,
                    ),
                    code=arg_error.code,
                    detail=arg_error.detail,
                )
            )
            return
        run_tap_command(
            dependencies=dependencies,
            target_id=requested_target,
            device=requested_device,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
            session=session,
            snapshot=snapshot,
        )


def run_tap_command(
    *,
    dependencies: TapDependencies,
    target_id: str | None,
    device: str | None,
    json_output: bool,
    timeout_s: float,
    lease_timeout_s: float,
    session: str = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    snapshot: Path | None = None,
) -> None:
    request = _request_payload(
        device=device,
        target_id=target_id,
        session=session,
        snapshot=snapshot,
    )
    if target_id is None:
        _emit_receipt(
            _blocked(
                device_id=None,
                request=request,
                detail="Target id is required.",
            )
        )
        return
    target_id_error = _target_id_error(target_id)
    if target_id_error is not None:
        _emit_receipt(_blocked(device_id=None, request=request, detail=target_id_error))
        return

    serial = normalize_serial(device)
    if serial is None:
        _emit_receipt(
            _blocked(
                device_id=None,
                request=request,
                detail="Pass a valid device serial.",
            )
        )
        return

    session_error = _session_error(session=session, snapshot=snapshot)
    if session_error is not None:
        _emit_receipt(
            _blocked(
                device_id=serial,
                request=request,
                code=session_error[0],
                detail=session_error[1],
            )
        )
        return
    normalized_session = normalize_latest_snapshot_session_id(session)

    try:
        if snapshot is None:
            source = read_latest_snap_source(
                device_id=serial,
                session_id=normalized_session,
                cache_root=dependencies.latest_cache_root,
            )
            latest_snap_source_target_for_tap(source, target_id)
            source_targets = snapshot_targets_from_latest_snap_source(source)
        else:
            manifest_source = read_snapshot_manifest_source(
                snapshot,
                expected_device_id=serial,
                session_id=DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
            )
            latest_source = build_latest_snap_source(
                manifest_source.snap,
                session_id=DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
            )
            latest_snap_source_target_for_tap(latest_source, target_id)
            source_targets = manifest_source.targets
        signature = build_target_signature(
            source_targets,
            target_id,
        )
    except LatestSnapSourceError as exc:
        _emit_receipt(
            _blocked(
                device_id=serial,
                request=request,
                code=exc.code,
                detail=exc.detail,
            )
        )
        return
    except SnapshotManifestSourceError as exc:
        _emit_receipt(
            _blocked(
                device_id=serial,
                request=request,
                code=exc.code,
                detail=exc.detail,
            )
        )
        return
    except TargetSignatureError as exc:
        _emit_receipt(
            _blocked(
                device_id=serial,
                request=request,
                code=exc.code,
                detail=exc.detail,
            )
        )
        return

    primitive_request = PrimitiveTapRequest(
        device_id=serial,
        signature=signature,
        timeout_s=timeout_s,
        lease_timeout_s=lease_timeout_s,
    )
    executor = dependencies.primitive_tap_executor
    if executor is not None:
        _emit_tap_result(
            executor.tap(primitive_request),
            dependencies=dependencies,
            session_id=normalized_session,
            json_output=json_output,
        )
        return

    visible = read_visible_devices(dependencies.discovery)
    if visible.error is not None:
        _emit_receipt(
            _blocked(
                device_id=serial,
                request={
                    "operation": "tap",
                    "device_id": serial,
                    "target_id": target_id,
                    "session_id": normalized_session,
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
        primitive_request,
        snapshot_provider=provider,
        tapper=dependencies.primitive_tapper or Uiautomator2Tapper(),
    )
    _emit_tap_result(
        receipt,
        dependencies=dependencies,
        session_id=normalized_session,
        json_output=json_output,
    )


def _blocked(
    *,
    device_id: str | None,
    request: dict[str, object],
    detail: str,
    code: str = "primitive_invalid_request",
) -> PrimitiveReceipt:
    return invalid_request_receipt(
        device_id=device_id,
        request=request,
        code=code,
        detail=detail,
    )


def _tap_arguments(
    *,
    serial_or_target: str | None,
    target_id: str | None,
    device: str | None,
) -> tuple[str | None, str | None, DriverError | None]:
    if device is not None:
        if target_id is not None:
            return (
                device,
                target_id,
                DriverError(
                    code="invalid_arguments",
                    detail="Use either positional serial or --device, not both.",
                ),
            )
        return (device, serial_or_target, None)
    if serial_or_target is None:
        return (None, target_id, None)
    return (serial_or_target, target_id, None)


def _request_payload(
    *,
    device: str | None,
    target_id: str | None,
    session: str,
    snapshot: Path | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "operation": "tap",
        "device_id": device,
        "target_id": target_id,
        "session_id": session,
    }
    if snapshot is not None:
        payload["source"] = "snapshot_manifest"
        payload["snapshot"] = str(snapshot)
    return payload


def _session_error(
    *,
    session: str,
    snapshot: Path | None,
) -> tuple[str, str] | None:
    if snapshot is not None and session != DEFAULT_LATEST_SNAPSHOT_SESSION_ID:
        return (
            "invalid_arguments",
            "--snapshot cannot be combined with a non-default --session.",
        )
    try:
        normalize_latest_snapshot_session_id(session)
    except LatestSnapshotRefError as exc:
        return (exc.code, exc.detail)
    return None


def _target_id_error(target_id: str) -> str | None:
    if (
        len(target_id) < 4
        or not target_id.startswith("e")
        or not target_id[1:].isdigit()
    ):
        return "Target id must look like e001."
    return None


def _emit_receipt(receipt: PrimitiveReceipt) -> None:
    emit_json(primitive_receipt_to_dict(receipt))
    if not receipt.ok:
        raise typer.Exit(code=1)


def _emit_tap_result(
    receipt: PrimitiveReceipt,
    *,
    dependencies: TapDependencies,
    session_id: str,
    json_output: bool,
) -> None:
    if json_output or not receipt.ok:
        _emit_receipt(receipt)
        return

    next_snap = _next_snap_from_receipt(
        receipt,
        dependencies=dependencies,
        session_id=session_id,
    )
    if next_snap is None:
        _emit_receipt(receipt)
        return

    emit_snap_table(next_snap, debug=False)


def _next_snap_from_receipt(
    receipt: PrimitiveReceipt,
    *,
    dependencies: TapDependencies,
    session_id: str,
) -> MobileSnap | None:
    if receipt.after_snapshot is None:
        return None
    snap = build_mobile_snap_from_semantic(
        receipt.after_snapshot,
        session_id=session_id,
    )
    if snap.ok:
        snap = write_latest_snap_source_for_snap(
            dependencies=dependencies,
            snap=snap,
        )
    return snap


def _screenshot_capturer(
    dependencies: TapDependencies,
) -> DriverScreenshotCapturer:
    return dependencies.screenshot_capturer or Uiautomator2ScreenshotCapturer()
