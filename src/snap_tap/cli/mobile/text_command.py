from __future__ import annotations

from pathlib import Path
from typing import Annotated, Protocol

import typer

from snap_tap.cli.output import emit_json
from snap_tap.cli.mobile.text_alias_helpers import (
    blocked_text_receipt,
    normalized_text,
    safe_text_request_metadata,
    target_id_error,
)
from snap_tap.cli.mobile.primitive_text_command import (
    PrimitiveTextDependencies,
    execute_primitive_text_request,
)
from snap_tap.device.identity import normalize_serial
from snap_tap.backends.android.uiautomator2.text import TEXT_INPUT_MODE, TEXT_REPLACE_MODE, TEXT_MODES
from snap_tap.primitives import (
    PrimitiveReceipt,
    PrimitiveTextRequest,
    primitive_receipt_to_dict,
)
from snap_tap.snapshots import (
    DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    LatestSnapshotRefError,
    normalize_latest_snapshot_session_id,
)
from snap_tap.targets import (
    LatestSnapSourceError,
    TargetSignatureError,
    build_target_signature,
    latest_snap_source_target_for_input,
    read_latest_snap_source,
    snapshot_targets_from_latest_snap_source,
)


class TextAliasDependencies(PrimitiveTextDependencies, Protocol):
    @property
    def latest_cache_root(self) -> Path: ...


def register_text_commands(app: typer.Typer, dependencies: TextAliasDependencies) -> None:
    @app.command("input")
    def input_text(
        target_id: Annotated[
            str | None,
            typer.Argument(help="Snapshot-local input id from latest snap-tap snap."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial for text input."),
        ] = None,
        text: Annotated[
            str | None,
            typer.Option("--text", help="Text payload to input."),
        ] = None,
        session: Annotated[
            str,
            typer.Option("--session", help="Latest snap source cache session id."),
        ] = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
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
        run_text_command(
            dependencies=dependencies,
            target_id=target_id,
            device=device,
            text=text,
            mode=TEXT_INPUT_MODE,
            session=session,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )

    @app.command("replace-text")
    def replace_text(
        target_id: Annotated[
            str | None,
            typer.Argument(help="Snapshot-local input id from latest snap-tap snap."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial for replace text."),
        ] = None,
        text: Annotated[
            str | None,
            typer.Option("--text", help="Replacement text payload."),
        ] = None,
        session: Annotated[
            str,
            typer.Option("--session", help="Latest snap source cache session id."),
        ] = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
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
        run_text_command(
            dependencies=dependencies,
            target_id=target_id,
            device=device,
            text=text,
            mode=TEXT_REPLACE_MODE,
            session=session,
            json_output=json_output,
            timeout_s=timeout_s,
            lease_timeout_s=lease_timeout_s,
        )


def run_text_command(
    *,
    dependencies: TextAliasDependencies,
    target_id: str | None,
    device: str | None,
    text: str | None,
    mode: str,
    session: str,
    json_output: bool,
    timeout_s: float,
    lease_timeout_s: float,
) -> None:
    del json_output
    request = safe_text_request_metadata(
        mode=mode,
        device_id=device,
        target_id=target_id,
        session_id=session,
        text=text,
    )
    if mode not in TEXT_MODES:
        _emit_receipt(
            blocked_text_receipt(
                device_id=None,
                request=request,
                detail="Text primitive mode must be input or replace_text.",
                operation=TEXT_INPUT_MODE,
            )
        )
        return
    if target_id is None:
        _emit_receipt(
            blocked_text_receipt(
                device_id=None,
                request=request,
                detail="Target id is required.",
                operation=mode,
            )
        )
        return
    id_error = target_id_error(target_id)
    if id_error is not None:
        _emit_receipt(
            blocked_text_receipt(
                device_id=None,
                request=request,
                detail=id_error,
                operation=mode,
            )
        )
        return
    serial = normalize_serial(device)
    if serial is None:
        _emit_receipt(
            blocked_text_receipt(
                device_id=None,
                request=request,
                detail="Pass --device with a valid ADB serial.",
                operation=mode,
            )
        )
        return
    try:
        normalized_session = normalize_latest_snapshot_session_id(session)
    except LatestSnapshotRefError as exc:
        _emit_receipt(
            blocked_text_receipt(
                device_id=serial,
                request=request,
                code=exc.code,
                detail=exc.detail,
                operation=mode,
            )
        )
        return
    text_value = normalized_text(text)
    if text_value is None:
        _emit_receipt(
            blocked_text_receipt(
                device_id=serial,
                request=safe_text_request_metadata(
                    mode=mode,
                    device_id=serial,
                    target_id=target_id,
                    session_id=normalized_session,
                    text=text,
                ),
                detail="Text payload must be non-empty normalized text.",
                operation=mode,
            )
        )
        return
    try:
        source = read_latest_snap_source(
            device_id=serial,
            session_id=normalized_session,
            cache_root=dependencies.latest_cache_root,
        )
        latest_snap_source_target_for_input(source, target_id)
        signature = build_target_signature(
            snapshot_targets_from_latest_snap_source(source),
            target_id,
        )
    except LatestSnapSourceError as exc:
        _emit_receipt(
            blocked_text_receipt(
                device_id=serial,
                request=safe_text_request_metadata(
                    mode=mode,
                    device_id=serial,
                    target_id=target_id,
                    session_id=normalized_session,
                    text=text_value,
                ),
                code=exc.code,
                detail=exc.detail,
                operation=mode,
            )
        )
        return
    except TargetSignatureError as exc:
        _emit_receipt(
            blocked_text_receipt(
                device_id=serial,
                request=safe_text_request_metadata(
                    mode=mode,
                    device_id=serial,
                    target_id=target_id,
                    session_id=normalized_session,
                    text=text_value,
                ),
                code=exc.code,
                detail=exc.detail,
                operation=mode,
            )
        )
        return

    primitive_request = PrimitiveTextRequest(
        device_id=serial,
        signature=signature,
        text=text_value,
        mode=mode,
        timeout_s=timeout_s,
        lease_timeout_s=lease_timeout_s,
    )
    execute_primitive_text_request(
        dependencies=dependencies,
        request=primitive_request,
    )


def _emit_receipt(receipt: PrimitiveReceipt) -> None:
    emit_json(primitive_receipt_to_dict(receipt))
    if not receipt.ok:
        raise typer.Exit(code=1)
