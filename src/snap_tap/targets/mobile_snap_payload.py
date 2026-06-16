from __future__ import annotations

from snap_tap.backends.contracts import DriverError
from snap_tap.targets.models import (
    MobileSnap,
    MobileSnapOperatorLabelCandidate,
    MobileSnapTarget,
)


def mobile_snap_to_dict(snap: MobileSnap, *, debug: bool = False) -> dict[str, object]:
    return {
        "schema_version": snap.schema_version,
        "ok": snap.ok,
        "status": snap.status,
        "device_id": snap.device_id,
        "session_id": snap.session_id,
        "captured_at": snap.captured_at,
        "app": dict(snap.app),
        "viewport": dict(snap.viewport),
        "summary": dict(snap.summary),
        "snapshot": dict(snap.snapshot),
        "targets": [_target_to_dict(target, debug=debug) for target in snap.targets],
        "error": _error_to_dict(snap.error),
    }


def _target_to_dict(
    target: MobileSnapTarget,
    *,
    debug: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": target.id,
        "kind": target.kind.value,
        "role": target.role.value,
        "label": target.label,
        "enabled": target.enabled,
        "clickable": target.clickable,
        "scrollable": target.scrollable,
        "actionable": target.actionable,
        "center": {"x": target.center_x, "y": target.center_y},
        "bounds": [
            target.bounds.left,
            target.bounds.top,
            target.bounds.right,
            target.bounds.bottom,
        ],
        "package": target.package,
        "operator_label": target.operator_label,
    }
    if debug:
        payload.update(
            {
                "source_index": target.source_index,
                "semantic_index": target.semantic_index,
                "class_name": target.class_name,
                "resource_id": target.resource_id,
                "label_source": target.label_source,
                "snapshot_id": target.snapshot_id,
                "operator_label_source": target.operator_label_source,
                "operator_label_confidence": target.operator_label_confidence,
                "operator_label_candidates": [
                    _operator_label_candidate_to_dict(candidate)
                    for candidate in target.operator_label_candidates
                ],
            }
        )
    return payload


def _operator_label_candidate_to_dict(
    candidate: MobileSnapOperatorLabelCandidate,
) -> dict[str, object]:
    return {
        "id": candidate.id,
        "label": candidate.label,
        "label_source": candidate.label_source,
        "role": candidate.role.value,
        "source_index": candidate.source_index,
        "semantic_index": candidate.semantic_index,
        "bounds": [
            candidate.bounds.left,
            candidate.bounds.top,
            candidate.bounds.right,
            candidate.bounds.bottom,
        ],
    }


def _error_to_dict(error: DriverError | None) -> dict[str, object] | None:
    if error is None:
        return None
    return {"code": error.code, "detail": error.detail}
