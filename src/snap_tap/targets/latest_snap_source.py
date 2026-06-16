from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from snap_tap.semantics import SemanticRole
from snap_tap.snapshots import (
    DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
    SnapshotBounds,
)
from snap_tap.snapshots.latest_types import (
    normalize_latest_snapshot_device_id,
    normalize_latest_snapshot_session_id,
)
from snap_tap.targets.latest_snap_source_models import (
    LATEST_SNAP_SOURCE_SCHEMA_VERSION,
    TAPPABLE_ROLES,
    LatestSnapSource,
    LatestSnapSourceError,
    LatestSnapSourceSnapshot,
    LatestSnapSourceTarget,
)
from snap_tap.targets.latest_snap_source_payload import (
    encode_latest_snap_source,
    latest_snap_source_from_dict,
    latest_snap_source_to_dict,
    non_negative_int,
    optional_text,
    required_text,
)
from snap_tap.targets.latest_snap_source_store import (
    latest_snap_source_path,
    read_latest_snap_source,
    write_latest_snap_source,
)
from snap_tap.targets.models import (
    MOBILE_SNAP_SCHEMA_VERSION,
    MobileSnap,
    MobileSnapKind,
    MobileSnapTarget,
    SnapshotTarget,
    SnapshotTargets,
    SnapshotTargetSummary,
)


def build_latest_snap_source(
    snap: MobileSnap,
    *,
    session_id: object | None = DEFAULT_LATEST_SNAPSHOT_SESSION_ID,
) -> LatestSnapSource:
    if snap.schema_version != MOBILE_SNAP_SCHEMA_VERSION or not snap.ok:
        raise _invalid("Latest snap source requires a successful mobile_snap.v1.")
    device_id = normalize_latest_snapshot_device_id(snap.device_id)
    session = normalize_latest_snapshot_session_id(session_id)
    return LatestSnapSource(
        schema_version=LATEST_SNAP_SOURCE_SCHEMA_VERSION,
        device_id=device_id,
        session_id=session,
        updated_at=_utc_now(),
        snapshot=_snapshot_from_mobile_snap(
            snap.snapshot,
            captured_at=snap.captured_at,
        ),
        targets=tuple(_source_target(target) for target in snap.targets),
    )


def latest_snap_source_target_for_tap(
    source: LatestSnapSource,
    display_id: str,
) -> LatestSnapSourceTarget:
    _validate_tap_target_id(display_id)
    matches = [target for target in source.targets if target.display_id == display_id]
    if not matches:
        raise LatestSnapSourceError(
            code="latest_snap_source_target_missing",
            detail="Requested target id is absent from latest snap source.",
        )
    if len(matches) > 1:
        raise LatestSnapSourceError(
            code="latest_snap_source_invalid",
            detail="Latest snap source contains duplicate target ids.",
        )
    target = matches[0]
    if (
        not target.enabled
        or not target.clickable
        or target.kind is not MobileSnapKind.TAP
        or target.role not in TAPPABLE_ROLES
    ):
        raise LatestSnapSourceError(
            code="latest_snap_source_target_not_tappable",
            detail="Requested target is not a safe tap target.",
        )
    return target


def latest_snap_source_target_for_input(
    source: LatestSnapSource,
    display_id: str,
) -> LatestSnapSourceTarget:
    _validate_target_id(display_id)
    matches = [target for target in source.targets if target.display_id == display_id]
    if not matches:
        raise LatestSnapSourceError(
            code="latest_snap_source_target_missing",
            detail="Requested target id is absent from latest snap source.",
        )
    if len(matches) > 1:
        raise LatestSnapSourceError(
            code="latest_snap_source_invalid",
            detail="Latest snap source contains duplicate target ids.",
        )
    target = matches[0]
    if (
        not target.enabled
        or not target.clickable
        or target.kind is not MobileSnapKind.INPUT
        or target.role is not SemanticRole.INPUT
    ):
        raise LatestSnapSourceError(
            code="latest_snap_source_target_not_input",
            detail="Requested target is not an input-like editable target.",
        )
    return target


def snapshot_targets_from_latest_snap_source(
    source: LatestSnapSource,
) -> SnapshotTargets:
    _validate_source_target_snapshot_ids(source)
    targets = tuple(_snapshot_target(source, target) for target in source.targets)
    return SnapshotTargets(
        schema_version="snapshot_targets.v1",
        snapshot_id=source.snapshot.snapshot_id,
        device_id=source.device_id,
        captured_at=source.snapshot.captured_at,
        source_schema_version=source.snapshot.source_schema_version,
        refs={},
        targets=targets,
        summary=SnapshotTargetSummary(
            target_count=len(targets),
            actionable_count=sum(1 for target in targets if target.actionable),
            disabled_count=sum(1 for target in targets if not target.enabled),
            non_clickable_count=sum(1 for target in targets if not target.clickable),
            labeled_count=sum(1 for target in targets if target.label is not None),
            source_element_count=len(targets),
            scrollable_count=sum(1 for target in targets if target.scrollable),
        ),
    )


def _snapshot_from_mobile_snap(
    payload: Mapping[str, object],
    *,
    captured_at: str,
) -> LatestSnapSourceSnapshot:
    return LatestSnapSourceSnapshot(
        snapshot_id=required_text(payload.get("snapshot_id"), "snapshot.snapshot_id"),
        captured_at=required_text(captured_at, "captured_at"),
        source_schema_version=required_text(
            payload.get("source_schema_version"),
            "snapshot.source_schema_version",
        ),
    )


def _source_target(target: MobileSnapTarget) -> LatestSnapSourceTarget:
    return LatestSnapSourceTarget(
        display_id=required_text(target.id, "target.id"),
        snapshot_id=required_text(target.snapshot_id, "target.snapshot_id"),
        semantic_index=non_negative_int(
            target.semantic_index,
            "target.semantic_index",
        ),
        source_index=non_negative_int(target.source_index, "target.source_index"),
        role=target.role,
        kind=target.kind,
        bounds=_bounds_from_object(target.bounds),
        enabled=target.enabled,
        clickable=target.clickable,
        scrollable=target.scrollable,
        actionable=target.actionable,
        label=optional_text(target.label, "target.label"),
        label_source=required_text(target.label_source, "target.label_source"),
        class_name=optional_text(target.class_name, "target.class_name"),
        resource_id=optional_text(target.resource_id, "target.resource_id"),
        package=optional_text(target.package, "target.package"),
    )


def _snapshot_target(
    source: LatestSnapSource,
    target: LatestSnapSourceTarget,
) -> SnapshotTarget:
    return SnapshotTarget(
        display_id=target.display_id,
        snapshot_id=source.snapshot.snapshot_id,
        semantic_index=target.semantic_index,
        source_index=target.source_index,
        role=target.role,
        bounds=target.bounds,
        enabled=target.enabled,
        clickable=target.clickable,
        scrollable=target.scrollable,
        actionable=target.enabled and target.clickable,
        label=target.label,
        label_source=target.label_source,
        class_name=target.class_name,
        resource_id=target.resource_id,
        package=target.package,
    )


def _validate_source_target_snapshot_ids(source: LatestSnapSource) -> None:
    source_snapshot_id = source.snapshot.snapshot_id
    for target in source.targets:
        if target.snapshot_id != source_snapshot_id:
            raise LatestSnapSourceError(
                code="latest_snap_source_invalid",
                detail=(
                    "Latest snap source target snapshot id does not match "
                    "the source snapshot."
                ),
            )


def _validate_tap_target_id(display_id: object) -> None:
    _validate_target_id(display_id)


def _validate_target_id(display_id: object) -> None:
    if not isinstance(display_id, str):
        raise LatestSnapSourceError(
            code="latest_snap_source_target_invalid",
            detail="Target id must be text.",
        )
    if (
        len(display_id) < 4
        or not display_id.startswith("e")
        or not display_id[1:].isdigit()
    ):
        raise LatestSnapSourceError(
            code="latest_snap_source_target_invalid",
            detail="Target id must look like e001.",
        )


def _bounds_from_object(value: object) -> SnapshotBounds:
    if not isinstance(value, SnapshotBounds):
        raise _invalid("Latest snap source target bounds are invalid.")
    return value


def _invalid(detail: str) -> LatestSnapSourceError:
    return LatestSnapSourceError(code="latest_snap_source_invalid", detail=detail)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "LATEST_SNAP_SOURCE_SCHEMA_VERSION",
    "LatestSnapSource",
    "LatestSnapSourceError",
    "LatestSnapSourceSnapshot",
    "LatestSnapSourceTarget",
    "build_latest_snap_source",
    "encode_latest_snap_source",
    "latest_snap_source_from_dict",
    "latest_snap_source_path",
    "latest_snap_source_target_for_input",
    "latest_snap_source_target_for_tap",
    "latest_snap_source_to_dict",
    "read_latest_snap_source",
    "snapshot_targets_from_latest_snap_source",
    "write_latest_snap_source",
]
