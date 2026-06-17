from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Protocol

import typer

from snap_tap.backends.android.uiautomator2.app_awareness import (
    Uiautomator2AppAwarenessReader,
)
from snap_tap.backends.contracts import (
    DriverAppAwarenessReader,
    DriverXmlDumper,
    read_device_app_current,
)
from snap_tap.cli.mobile.device_discovery import (
    read_command_devices,
    resolve_requested_serial,
)
from snap_tap.cli.output import emit_json
from snap_tap.device.discovery import DeviceDiscovery
from snap_tap.snapshots import (
    DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    LatestSnapshotRefError,
    capture_raw_observation,
    complete_operator_observation,
    normalize_latest_snapshot_session_id,
)
from snap_tap.snapshots.manifest_source import (
    SnapshotManifestSourceError,
    read_snapshot_manifest_source,
)
from snap_tap.targets import (
    LatestSnapSourceError,
    MobileSnap,
    MobileSnapKind,
    MobileSnapTarget,
    build_latest_snap_source,
    build_mobile_snap,
    mobile_snap_failure,
    mobile_snap_to_dict,
    write_latest_snap_source,
)

_LABEL_WIDTH = 36


class SnapDependencies(Protocol):
    @property
    def discovery(self) -> DeviceDiscovery: ...

    @property
    def xml_dumper(self) -> DriverXmlDumper: ...

    @property
    def app_reader(self) -> DriverAppAwarenessReader | None: ...

    @property
    def latest_cache_root(self) -> Path: ...


class LatestSnapSourceDependencies(Protocol):
    @property
    def latest_cache_root(self) -> Path: ...


def register_snap_commands(
    app: typer.Typer,
    dependencies: SnapDependencies,
) -> None:
    @app.command("snap")
    def snap(
        serial: Annotated[
            str | None,
            typer.Argument(help="ADB serial to observe."),
        ] = None,
        device: Annotated[
            str | None,
            typer.Option("--device", "-d", help="ADB serial to observe."),
        ] = None,
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Emit mobile_snap.v1 JSON."),
        ] = False,
        debug: Annotated[
            bool,
            typer.Option("--debug", help="Include diagnostic fields."),
        ] = False,
        timeout_s: Annotated[
            float,
            typer.Option("--timeout-s", min=0.001, help="Operation timeout."),
        ] = 10.0,
        session: Annotated[
            str,
            typer.Option("--session", help="Latest snap source cache session id."),
        ] = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
        snapshot: Annotated[
            Path | None,
            typer.Option(
                "--snapshot",
                help="Read mobile_snap.v1 from a snapshot manifest or capture dir.",
            ),
        ] = None,
    ) -> None:
        requested_serial, serial_error = resolve_requested_serial(
            serial=serial,
            device=device,
        )
        if serial_error is not None:
            snap_result = mobile_snap_failure(
                device_id=serial or device,
                session_id=session,
                code=serial_error.code,
                detail=serial_error.detail,
            )
            if json_output:
                emit_json(mobile_snap_to_dict(snap_result, debug=debug))
            else:
                emit_snap_table(snap_result, debug=debug)
            raise typer.Exit(code=1)
        run_snap_command(
            dependencies=dependencies,
            device=requested_serial,
            json_output=json_output,
            debug=debug,
            timeout_s=timeout_s,
            session=session,
            snapshot=snapshot,
        )


def run_snap_command(
    *,
    dependencies: SnapDependencies,
    device: str | None,
    json_output: bool,
    debug: bool,
    timeout_s: float,
    session: str = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    snapshot: Path | None = None,
) -> None:
    if snapshot is not None:
        snap = _snap_from_manifest(device=device, session=session, snapshot=snapshot)
    else:
        snap = _capture_snap(
            dependencies=dependencies,
            device=device,
            timeout_s=timeout_s,
            session=session,
            include_app_current=debug,
        )
    if snap.ok and snapshot is None:
        snap = write_latest_snap_source_for_snap(
            dependencies=dependencies,
            snap=snap,
        )
    if json_output:
        emit_json(mobile_snap_to_dict(snap, debug=debug))
    else:
        emit_snap_table(snap, debug=debug)
    if not snap.ok:
        raise typer.Exit(code=1)


def _capture_snap(
    *,
    dependencies: SnapDependencies,
    device: str | None,
    timeout_s: float,
    session: str,
    include_app_current: bool,
) -> MobileSnap:
    session_error = _validate_session(session)
    if session_error is not None:
        return mobile_snap_failure(
            device_id=device,
            session_id=session,
            code=session_error.code,
            detail=session_error.detail,
        )
    session_id = normalize_latest_snapshot_session_id(session)
    if device is None:
        return mobile_snap_failure(
            device_id=None,
            session_id=session_id,
            code="device_required",
            detail="Pass a device serial to observe a snap-tap snap.",
        )

    visible = read_command_devices(
        dependencies.discovery,
        requested_serial=device,
    )
    if visible.error is not None:
        return mobile_snap_failure(
            device_id=device,
            session_id=session_id,
            code=visible.error.code,
            detail=visible.error.detail,
        )

    raw = capture_raw_observation(
        xml_dumper=dependencies.xml_dumper,
        devices=visible.devices,
        requested_serial=device,
        timeout_s=timeout_s,
    )
    if raw.ok:
        raw = complete_operator_observation(raw)

    app_current = None
    if include_app_current and raw.ok and raw.device_id is not None:
        app_current = read_device_app_current(
            reader=_app_reader(dependencies),
            devices=visible.devices,
            requested_serial=raw.device_id,
            timeout_s=timeout_s,
        )
    return build_mobile_snap(
        raw,
        app_current=app_current,
        session_id=session_id,
    )


def write_latest_snap_source_for_snap(
    *,
    dependencies: LatestSnapSourceDependencies,
    snap: MobileSnap,
) -> MobileSnap:
    try:
        source = build_latest_snap_source(snap, session_id=snap.session_id)
        write_latest_snap_source(
            source,
            cache_root=_latest_cache_root(dependencies),
        )
    except LatestSnapSourceError as exc:
        return mobile_snap_failure(
            device_id=snap.device_id,
            session_id=snap.session_id,
            code=exc.code,
            detail=exc.detail,
            status="failed",
        )
    return snap


def _snap_from_manifest(
    *,
    device: str | None,
    session: str,
    snapshot: Path,
) -> MobileSnap:
    if session != DEFAULT_LATEST_SNAPSHOT_SESSION_ID:
        return mobile_snap_failure(
            device_id=device,
            session_id=session,
            code="invalid_arguments",
            detail="--snapshot cannot be combined with a non-default --session.",
        )
    try:
        source = read_snapshot_manifest_source(
            snapshot,
            expected_device_id=device,
            session_id=DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
        )
    except SnapshotManifestSourceError as exc:
        return mobile_snap_failure(
            device_id=device,
            session_id=DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
            code=exc.code,
            detail=exc.detail,
        )
    return source.snap


def emit_snap_table(snap: MobileSnap, *, debug: bool) -> None:
    if not snap.ok:
        error = snap.error
        code = error.code if error is not None else "snap_unavailable"
        detail = error.detail if error is not None else "snap-tap snap unavailable."
        typer.echo(f"snap-tap snap {snap.status}: {code} - {detail}")
        return

    app_package = snap.app.get("package") or "-"
    width = snap.viewport.get("width") or "?"
    height = snap.viewport.get("height") or "?"
    typer.echo(f"{snap.device_id}  {app_package}  {width}x{height}")
    summary = snap.summary
    typer.echo(
        "targets: "
        f"{summary['tap_count']} tap | "
        f"{summary['input_count']} input | "
        f"{summary['scroll_count']} {_scroll_area_label(summary['scroll_count'])} | "
        f"{summary['visible_count']} visible"
    )
    if not debug and summary["scroll_count"]:
        typer.echo(
            f"scroll: {summary['scroll_count']} "
            f"{_area_label(summary['scroll_count'])} detected; "
            "use --debug or --json for bounds"
        )
    table_targets = _table_targets(snap.targets, debug=debug)
    typer.echo(_header(debug=debug))
    for target in table_targets:
        typer.echo(_row(target, debug=debug))
    if any(_uses_operator_label(target) for target in table_targets):
        typer.echo("~ operator label; not target identity")


def _header(*, debug: bool) -> str:
    columns = ["ID", "KIND", "ROLE", "LABEL", "CENTER", "BOUNDS", "STATE"]
    if debug:
        columns.extend(["SRC", "SEM", "CLASS", "RESOURCE_ID", "SNAPSHOT"])
    return _format_row(columns, debug=debug)


def _row(target: MobileSnapTarget, *, debug: bool) -> str:
    columns = [
        target.id,
        target.kind.value,
        target.role.value,
        _table_label(target),
        f"{target.center_x:g},{target.center_y:g}",
        (
            f"{target.bounds.left},{target.bounds.top},"
            f"{target.bounds.right},{target.bounds.bottom}"
        ),
        _state(target),
    ]
    if debug:
        columns.extend(
            [
                str(target.source_index),
                str(target.semantic_index),
                _clip(target.class_name or "-", 24),
                _clip(target.resource_id or "-", 32),
                _clip(target.snapshot_id or "-", 20),
            ]
        )
    return _format_row(columns, debug=debug)


def _format_row(columns: list[str], *, debug: bool) -> str:
    widths = [6, 8, 10, _LABEL_WIDTH, 12, 18, 12]
    if debug:
        widths.extend([6, 6, 24, 32, 20])
    return "  ".join(value.ljust(width)[:width] for value, width in zip(columns, widths))


def _table_label(target: MobileSnapTarget) -> str:
    if target.label is not None:
        return _clip(target.label, _LABEL_WIDTH)
    if target.operator_label is not None:
        return _clip_operator_label(target.operator_label, _LABEL_WIDTH)
    return "-"


def _clip_operator_label(label: str, width: int) -> str:
    value = f"{label}~"
    if len(value) <= width:
        return value
    if width <= 2:
        return value[:width]
    return value[: width - 2] + ".~"


def _uses_operator_label(target: MobileSnapTarget) -> bool:
    return target.label is None and target.operator_label is not None


def _state(target: MobileSnapTarget) -> str:
    if not target.enabled:
        return "disabled"
    if target.kind.value == "scroll":
        return "scrollable"
    if target.clickable or target.kind.value == "input":
        return "enabled"
    return "visible"


def _table_targets(
    targets: Sequence[MobileSnapTarget],
    *,
    debug: bool,
) -> tuple[MobileSnapTarget, ...]:
    if debug:
        return tuple(targets)
    return tuple(
        target
        for target in targets
        if target.kind in {MobileSnapKind.INPUT, MobileSnapKind.TAP}
    )


def _scroll_area_label(count: int) -> str:
    return "scroll area" if count == 1 else "scroll areas"


def _area_label(count: int) -> str:
    return "area" if count == 1 else "areas"


def _clip(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "."


def _app_reader(dependencies: SnapDependencies) -> DriverAppAwarenessReader:
    return dependencies.app_reader or Uiautomator2AppAwarenessReader()


def _validate_session(
    session: str,
) -> LatestSnapshotRefError | None:
    try:
        normalize_latest_snapshot_session_id(session)
    except LatestSnapshotRefError as exc:
        return exc
    return None


def _latest_cache_root(dependencies: LatestSnapSourceDependencies) -> Path:
    return dependencies.latest_cache_root
