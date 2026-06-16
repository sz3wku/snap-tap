from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from snap_tap.backends.contracts import DriverAppAwareness
from snap_tap.backends.contracts import DriverError
from snap_tap.semantics import SemanticRole, SemanticSnapshot, build_semantic_snapshot
from snap_tap.semantics.models import SemanticViewport
from snap_tap.snapshots import RawSnapshotCapture
from snap_tap.targets.models import (
    MobileSnap,
    MobileSnapKind,
    MobileSnapTarget,
    SnapshotTarget,
)
from snap_tap.targets.snapshot import build_snapshot_targets


def build_mobile_snap(
    raw: RawSnapshotCapture,
    *,
    app_current: DriverAppAwareness | None,
    session_id: str,
) -> MobileSnap:
    if not raw.ok or raw.error is not None:
        return _failure_from_raw(raw, session_id=session_id)
    try:
        semantic = build_semantic_snapshot(raw)
        snapshot_targets = build_snapshot_targets(semantic)
    except Exception:
        return _failure(
            device_id=raw.device_id,
            session_id=session_id,
            code="snap_parse_failed",
            detail="snap-tap snap could not build target display from snapshot data.",
            captured_at=raw.checked_at,
        )

    targets = tuple(
        sorted(
            (_mobile_target(target) for target in snapshot_targets.targets),
            key=_target_sort_key,
        )
    )
    return MobileSnap(
        ok=True,
        status="completed",
        device_id=raw.device_id,
        session_id=session_id,
        captured_at=raw.checked_at,
        app=_app_to_dict(app_current),
        viewport=_viewport_to_dict(semantic.screen_metadata.viewport),
        summary=_summary(raw=raw, targets=targets),
        snapshot=_snapshot_identity_to_dict(raw),
        targets=targets,
        error=None,
    )


def build_mobile_snap_from_semantic(
    snapshot: SemanticSnapshot,
    *,
    session_id: str,
    app: Mapping[str, object] | None = None,
) -> MobileSnap:
    try:
        snapshot_targets = build_snapshot_targets(snapshot)
    except Exception:
        return _failure(
            device_id=snapshot.device_id,
            session_id=session_id,
            code="snap_parse_failed",
            detail="snap-tap snap could not build target display from semantic data.",
            captured_at=snapshot.captured_at,
        )

    targets = tuple(
        sorted(
            (_mobile_target(target) for target in snapshot_targets.targets),
            key=_target_sort_key,
        )
    )
    return MobileSnap(
        ok=True,
        status="completed",
        device_id=snapshot.device_id,
        session_id=session_id,
        captured_at=snapshot.captured_at,
        app=dict(app) if app is not None else _semantic_app(snapshot),
        viewport=_viewport_to_dict(snapshot.screen_metadata.viewport),
        summary=_summary_from_semantic(snapshot=snapshot, targets=targets),
        snapshot=_snapshot_identity_from_semantic(snapshot),
        targets=targets,
        error=None,
    )


def mobile_snap_failure(
    *,
    device_id: str | None,
    session_id: str,
    code: str,
    detail: str,
    status: str = "blocked",
) -> MobileSnap:
    return _failure(
        device_id=device_id,
        session_id=session_id,
        code=code,
        detail=detail,
        status=status,
    )


def _failure_from_raw(raw: RawSnapshotCapture, *, session_id: str) -> MobileSnap:
    error = raw.error or DriverError(
        code="snap_capture_failed",
        detail="snap-tap snap capture failed without a structured error.",
    )
    return _failure(
        device_id=raw.device_id,
        session_id=session_id,
        code=_snap_error_code(error.code),
        detail=error.detail,
        status=raw.status,
        captured_at=raw.checked_at,
    )


def _failure(
    *,
    device_id: str | None,
    session_id: str,
    code: str,
    detail: str,
    status: str = "blocked",
    captured_at: str | None = None,
) -> MobileSnap:
    return MobileSnap(
        ok=False,
        status=status,
        device_id=device_id,
        session_id=session_id,
        captured_at=captured_at or datetime.now(UTC).isoformat(),
        app=_unknown_app(),
        viewport=_unknown_viewport(),
        summary=_empty_summary(),
        snapshot=_empty_snapshot(),
        targets=(),
        error=DriverError(code=code, detail=detail),
    )


def _mobile_target(target: SnapshotTarget) -> MobileSnapTarget:
    kind = _target_kind(target)
    return MobileSnapTarget(
        id=target.display_id,
        kind=kind,
        role=target.role,
        label=target.label,
        enabled=target.enabled,
        clickable=target.clickable,
        scrollable=target.scrollable,
        actionable=kind in {
            MobileSnapKind.INPUT,
            MobileSnapKind.TAP,
            MobileSnapKind.SCROLL,
        },
        center_x=target.bounds.center_x,
        center_y=target.bounds.center_y,
        bounds=target.bounds,
        package=target.package,
        source_index=target.source_index,
        semantic_index=target.semantic_index,
        class_name=target.class_name,
        resource_id=target.resource_id,
        label_source=target.label_source,
        snapshot_id=target.snapshot_id,
    )


def _target_kind(target: SnapshotTarget) -> MobileSnapKind:
    if target.enabled and target.role is SemanticRole.INPUT:
        return MobileSnapKind.INPUT
    if target.enabled and target.clickable:
        return MobileSnapKind.TAP
    if target.enabled and target.scrollable:
        return MobileSnapKind.SCROLL
    if target.role is SemanticRole.TEXT:
        return MobileSnapKind.TEXT
    if target.role is SemanticRole.IMAGE:
        return MobileSnapKind.IMAGE
    return MobileSnapKind.UNKNOWN


def _target_sort_key(target: MobileSnapTarget) -> tuple[int, int]:
    priority = {
        MobileSnapKind.INPUT: 0,
        MobileSnapKind.TAP: 1,
        MobileSnapKind.SCROLL: 2,
        MobileSnapKind.TEXT: 3,
        MobileSnapKind.IMAGE: 4,
        MobileSnapKind.UNKNOWN: 5,
    }
    return (priority[target.kind], target.source_index)


def _summary(
    *,
    raw: RawSnapshotCapture,
    targets: Sequence[MobileSnapTarget],
) -> dict[str, int]:
    element_count = raw.normalization.element_count if raw.normalization else len(targets)
    return {
        "element_count": element_count,
        "target_count": len(targets),
        "tap_count": _kind_count(targets, MobileSnapKind.TAP),
        "scroll_count": _kind_count(targets, MobileSnapKind.SCROLL),
        "input_count": _kind_count(targets, MobileSnapKind.INPUT),
        "visible_count": len(targets),
        "enabled_count": sum(1 for target in targets if target.enabled),
        "clickable_count": sum(1 for target in targets if target.clickable),
        "scrollable_count": sum(1 for target in targets if target.scrollable),
    }


def _summary_from_semantic(
    *,
    snapshot: SemanticSnapshot,
    targets: Sequence[MobileSnapTarget],
) -> dict[str, int]:
    counts = snapshot.screen_metadata.counts
    return {
        "element_count": counts.source_element_count,
        "target_count": len(targets),
        "tap_count": _kind_count(targets, MobileSnapKind.TAP),
        "scroll_count": _kind_count(targets, MobileSnapKind.SCROLL),
        "input_count": _kind_count(targets, MobileSnapKind.INPUT),
        "visible_count": len(targets),
        "enabled_count": sum(1 for target in targets if target.enabled),
        "clickable_count": sum(1 for target in targets if target.clickable),
        "scrollable_count": sum(1 for target in targets if target.scrollable),
    }


def _kind_count(
    targets: Sequence[MobileSnapTarget],
    kind: MobileSnapKind,
) -> int:
    return sum(1 for target in targets if target.kind is kind)


def _snapshot_identity_to_dict(raw: RawSnapshotCapture) -> dict[str, object]:
    if raw.identity is None:
        return _empty_snapshot()
    return {
        "snapshot_id": raw.identity.snapshot_id,
        "snapshot_hash": raw.identity.snapshot_hash,
        "hash_version": raw.identity.hash_version,
        "source_schema_version": (
            raw.normalization.schema_version if raw.normalization else None
        ),
    }


def _snapshot_identity_from_semantic(snapshot: SemanticSnapshot) -> dict[str, object]:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_hash": None,
        "hash_version": None,
        "source_schema_version": snapshot.schema_version,
    }


def _app_to_dict(app_current: DriverAppAwareness | None) -> dict[str, object]:
    if app_current is None or not app_current.ok:
        return _unknown_app()
    metadata = dict(app_current.metadata)
    package = metadata.get("package")
    activity = metadata.get("activity")
    pid = metadata.get("pid")
    return {
        "status": "current",
        "package": package if isinstance(package, str) else None,
        "activity": activity if isinstance(activity, str) else None,
        "pid": pid if isinstance(pid, int) and not isinstance(pid, bool) else None,
    }


def _semantic_app(snapshot: SemanticSnapshot) -> dict[str, object]:
    package = snapshot.screen_metadata.dominant_package
    if package is None:
        package = next(
            (element.package for element in snapshot.elements if element.package),
            None,
        )
    return {
        "status": "snapshot",
        "package": package,
        "activity": None,
        "pid": None,
    }


def _viewport_to_dict(viewport: SemanticViewport) -> dict[str, object]:
    return {
        "width": viewport.width,
        "height": viewport.height,
        "orientation": viewport.orientation.value,
    }


def _snap_error_code(code: str) -> str:
    if code in {
        "device_required",
        "device_offline",
        "driver_conflict",
        "driver_timeout",
    }:
        return code
    if code == "snapshot_parse_failed":
        return "snap_parse_failed"
    if code == "snapshot_empty":
        return "snap_empty"
    return "snap_capture_failed"


def _unknown_app() -> dict[str, object]:
    return {"status": "unknown", "package": None, "activity": None, "pid": None}


def _unknown_viewport() -> dict[str, object]:
    return {"width": None, "height": None, "orientation": "unknown"}


def _empty_snapshot() -> dict[str, object]:
    return {
        "snapshot_id": None,
        "snapshot_hash": None,
        "hash_version": None,
        "source_schema_version": None,
    }


def _empty_summary() -> dict[str, int]:
    return {
        "element_count": 0,
        "target_count": 0,
        "tap_count": 0,
        "scroll_count": 0,
        "input_count": 0,
        "visible_count": 0,
        "enabled_count": 0,
        "clickable_count": 0,
        "scrollable_count": 0,
    }
