from __future__ import annotations

from pathlib import Path
from typing import Protocol

import typer

from snap_tap.cli.mobile.snap_command import (
    emit_snap_table,
    write_latest_snap_source_for_snap,
)
from snap_tap.cli.output import emit_json
from snap_tap.primitives import PrimitiveReceipt, primitive_receipt_to_dict
from snap_tap.targets import MobileSnap, build_mobile_snap_from_semantic


class PrimitiveResultDependencies(Protocol):
    @property
    def latest_cache_root(self) -> Path: ...


def emit_primitive_receipt(receipt: PrimitiveReceipt) -> None:
    emit_json(primitive_receipt_to_dict(receipt))
    if not receipt.ok:
        raise typer.Exit(code=1)


def emit_primitive_result(
    receipt: PrimitiveReceipt,
    *,
    dependencies: PrimitiveResultDependencies,
    session_id: str,
    json_output: bool,
) -> None:
    if json_output or not receipt.ok:
        emit_primitive_receipt(receipt)
        return

    next_snap = _next_snap_from_receipt(
        receipt,
        dependencies=dependencies,
        session_id=session_id,
    )
    if next_snap is None:
        emit_primitive_receipt(receipt)
        return

    emit_snap_table(next_snap, debug=False)


def _next_snap_from_receipt(
    receipt: PrimitiveReceipt,
    *,
    dependencies: PrimitiveResultDependencies,
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
