from __future__ import annotations

from pathlib import Path
from typing import Annotated, Protocol

import typer

from snap_tap.cli.output import emit_json
from snap_tap.cli.snapshot_output import raw_snapshot_capture_to_dict
from snap_tap.cli.mobile.device_discovery import (
    read_visible_devices,
    resolve_requested_serial,
)
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.backends.contracts import DriverScreenshotCapturer
from snap_tap.backends.android.uiautomator2.screenshot import Uiautomator2ScreenshotCapturer
from snap_tap.backends.contracts import DriverXmlDumper
from snap_tap.snapshots import (
    DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    LatestSnapshotRefError,
    RawSnapshotCapture,
    build_latest_snapshot_ref,
    capture_raw_snapshot,
    latest_snapshot_error_to_dict,
    latest_snapshot_ref_to_dict,
    materialize_raw_snapshot_artifacts,
    normalize_latest_snapshot_session_id,
    read_latest_snapshot_ref,
    write_latest_snapshot_ref,
)


class SnapshotDependencies(Protocol):
    @property
    def discovery(self) -> DeviceDiscovery: ...

    @property
    def xml_dumper(self) -> DriverXmlDumper: ...

    @property
    def screenshot_capturer(self) -> DriverScreenshotCapturer | None: ...

    @property
    def latest_cache_root(self) -> Path: ...


def register_snapshot_commands(
    app: typer.Typer,
    dependencies: SnapshotDependencies,
) -> None:
    @app.command("snapshot")
    def snapshot(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to capture."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to capture."),
        ] = None,
        out_dir: Annotated[
            Path | None,
            typer.Option("--out-dir", help="Explicit artifact output directory."),
        ] = None,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 10.0,
        session: Annotated[
            str,
            typer.Option("--session", help="Latest snapshot cache session id."),
        ] = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    ) -> None:
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            capturer = _screenshot_capturer(dependencies)
            backend = _combined_backend(
                dependencies.xml_dumper.backend_name,
                capturer.backend_name,
            )
            _emit_snapshot_result(
                RawSnapshotCapture.failure(
                    backend=backend,
                    code=serial_error.code,
                    detail=serial_error.detail,
                    device_id=serial or device,
                    elapsed_ms=0.0,
                    status="blocked",
                )
            )
            return
        run_snapshot_command(
            dependencies=dependencies,
            device=requested_serial,
            out_dir=out_dir,
            timeout_s=timeout_s,
            session=session,
        )

    @app.command("snapshot-latest")
    def snapshot_latest(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to read."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to read."),
        ] = None,
        session: Annotated[
            str,
            typer.Option("--session", help="Latest snapshot cache session id."),
        ] = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    ) -> None:
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            _emit_latest_failure(
                LatestSnapshotRefError(
                    code=serial_error.code,
                    detail=serial_error.detail,
                ),
                device_id=serial or device,
                session_id=session,
            )
            return
        run_snapshot_latest_command(
            dependencies=dependencies,
            device=requested_serial,
            session=session,
        )


def run_snapshot_command(
    *,
    dependencies: SnapshotDependencies,
    device: str | None,
    out_dir: Path | None,
    timeout_s: float,
    session: str = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
) -> None:
    capturer = _screenshot_capturer(dependencies)
    backend = _combined_backend(
        dependencies.xml_dumper.backend_name,
        capturer.backend_name,
    )
    if device is None:
        _emit_snapshot_result(
            RawSnapshotCapture.failure(
                backend=backend,
                code="device_required",
                detail="Pass a device serial to capture a snap-tap snapshot.",
                elapsed_ms=0.0,
                status="blocked",
                metadata={"timeout_s": timeout_s},
            )
        )
        return
    session_error = _validate_session(session)
    if session_error is not None:
        _emit_latest_failure(session_error, device_id=device, session_id=session)
        return
    if out_dir is None:
        _emit_snapshot_result(
            RawSnapshotCapture.failure(
                backend=backend,
                code="invalid_arguments",
                detail="Pass --out-dir to write raw snapshot artifacts.",
                device_id=device,
                elapsed_ms=0.0,
                status="blocked",
                metadata={"timeout_s": timeout_s},
            )
        )
        return

    snapshot = read_visible_devices(dependencies.discovery)
    if snapshot.error is not None:
        _emit_snapshot_result(
            RawSnapshotCapture.failure(
                backend=backend,
                code=snapshot.error.code,
                detail=snapshot.error.detail,
                device_id=device,
                elapsed_ms=0.0,
                status="blocked",
                metadata={"timeout_s": timeout_s},
            )
        )
        return

    result = capture_raw_snapshot(
        xml_dumper=dependencies.xml_dumper,
        screenshot_capturer=capturer,
        devices=snapshot.devices,
        requested_serial=device,
        timeout_s=timeout_s,
    )
    if result.ok:
        result = materialize_raw_snapshot_artifacts(result, out_dir)
    if result.ok:
        try:
            latest_ref = build_latest_snapshot_ref(
                result,
                session_id=session,
                cache_root=_latest_cache_root(dependencies),
            )
            write_latest_snapshot_ref(
                latest_ref,
                cache_root=_latest_cache_root(dependencies),
            )
        except LatestSnapshotRefError as exc:
            _emit_latest_failure(exc, device_id=device, session_id=session)
            return
    _emit_snapshot_result(result)


def run_snapshot_latest_command(
    *,
    dependencies: SnapshotDependencies,
    device: str | None,
    session: str = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
) -> None:
    if device is None:
        _emit_latest_failure(
            LatestSnapshotRefError(
                code="device_required",
                detail="Pass a device serial to read the latest snap-tap snapshot ref.",
            ),
            device_id=device,
            session_id=session,
        )
        return
    try:
        ref = read_latest_snapshot_ref(
            device_id=device,
            session_id=session,
            cache_root=_latest_cache_root(dependencies),
        )
    except LatestSnapshotRefError as exc:
        _emit_latest_failure(exc, device_id=device, session_id=session)
        return
    emit_json({"ok": True, "result": latest_snapshot_ref_to_dict(ref)})


def _emit_snapshot_result(result: RawSnapshotCapture) -> None:
    emit_json({"ok": result.ok, "result": raw_snapshot_capture_to_dict(result)})
    if not result.ok:
        raise typer.Exit(code=1)


def _emit_latest_failure(
    error: LatestSnapshotRefError,
    *,
    device_id: str | None,
    session_id: str | None,
) -> None:
    emit_json(
        {
            "ok": False,
            "result": {
                "ok": False,
                "status": "blocked",
                "device_id": device_id,
                "session_id": session_id,
                "error": latest_snapshot_error_to_dict(error),
            },
        }
    )
    raise typer.Exit(code=1)


def _validate_session(
    session: str,
) -> LatestSnapshotRefError | None:
    try:
        normalize_latest_snapshot_session_id(session)
    except LatestSnapshotRefError as exc:
        return exc
    return None


def _screenshot_capturer(
    dependencies: SnapshotDependencies,
) -> DriverScreenshotCapturer:
    return dependencies.screenshot_capturer or Uiautomator2ScreenshotCapturer()


def _latest_cache_root(dependencies: SnapshotDependencies) -> Path:
    return dependencies.latest_cache_root


def _combined_backend(first: str, second: str) -> str:
    if first == second:
        return first
    return f"{first}+{second}"
