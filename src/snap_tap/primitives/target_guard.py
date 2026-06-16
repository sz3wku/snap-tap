from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite

from snap_tap.semantics import SemanticSnapshot
from snap_tap.snapshots import SnapshotBounds
from snap_tap.targets import TargetResolution, TargetSignature

PRIMITIVE_TARGET_STALE_CODE = "primitive_target_stale"

_CENTER_DRIFT_FLOOR_PX = 64.0
_CENTER_DRIFT_VIEWPORT_RATIO = 0.10
_SIZE_DRIFT_RATIO = 0.35


@dataclass(frozen=True)
class PrimitiveTargetStaleBlock:
    code: str
    detail: str


def stale_target_block(
    *,
    signature: TargetSignature,
    resolution: TargetResolution,
    fresh_snapshot: SemanticSnapshot,
) -> PrimitiveTargetStaleBlock | None:
    target = resolution.resolved_target
    if target is None:
        return PrimitiveTargetStaleBlock(
            code=PRIMITIVE_TARGET_STALE_CODE,
            detail="Resolved target was missing before stale target guard.",
        )

    source_bounds = signature.source_bounds
    fresh_bounds = target.bounds
    if not _valid_bounds(source_bounds) or not _valid_bounds(fresh_bounds):
        return PrimitiveTargetStaleBlock(
            code=PRIMITIVE_TARGET_STALE_CODE,
            detail="Target bounds were invalid before primitive touch.",
        )

    center_drift = hypot(
        fresh_bounds.center_x - source_bounds.center_x,
        fresh_bounds.center_y - source_bounds.center_y,
    )
    center_tolerance = _center_tolerance_px(fresh_snapshot)
    if center_drift > center_tolerance:
        return PrimitiveTargetStaleBlock(
            code=PRIMITIVE_TARGET_STALE_CODE,
            detail=(
                "Resolved target center drifted beyond primitive tolerance "
                f"({center_drift:.1f}px > {center_tolerance:.1f}px)."
            ),
        )

    width_drift = _relative_size_drift(source_bounds.width, fresh_bounds.width)
    height_drift = _relative_size_drift(source_bounds.height, fresh_bounds.height)
    if width_drift is None or height_drift is None:
        return PrimitiveTargetStaleBlock(
            code=PRIMITIVE_TARGET_STALE_CODE,
            detail="Target size was invalid before primitive touch.",
        )
    size_drift = max(width_drift, height_drift)
    if size_drift > _SIZE_DRIFT_RATIO:
        return PrimitiveTargetStaleBlock(
            code=PRIMITIVE_TARGET_STALE_CODE,
            detail=(
                "Resolved target size drifted beyond primitive tolerance "
                f"({size_drift:.3f} > {_SIZE_DRIFT_RATIO:.3f})."
            ),
        )

    return None


def _center_tolerance_px(snapshot: SemanticSnapshot) -> float:
    viewport = snapshot.screen_metadata.viewport
    if (
        _positive_number(viewport.width)
        and _positive_number(viewport.height)
        and viewport.width is not None
        and viewport.height is not None
    ):
        return max(
            _CENTER_DRIFT_FLOOR_PX,
            min(float(viewport.width), float(viewport.height))
            * _CENTER_DRIFT_VIEWPORT_RATIO,
        )
    return _CENTER_DRIFT_FLOOR_PX


def _relative_size_drift(source: int, fresh: int) -> float | None:
    if not _positive_number(source) or not _positive_number(fresh):
        return None
    return abs(float(fresh) - float(source)) / float(source)


def _valid_bounds(bounds: SnapshotBounds) -> bool:
    return (
        _positive_number(bounds.width)
        and _positive_number(bounds.height)
        and _number(bounds.center_x)
        and _number(bounds.center_y)
    )


def _positive_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    return isfinite(value) and value > 0


def _number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )
