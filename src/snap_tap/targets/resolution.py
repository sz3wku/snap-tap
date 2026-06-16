from __future__ import annotations

from collections.abc import Mapping

from snap_tap.semantics import SemanticSnapshot
from snap_tap.snapshots import SnapshotArtifactRef
from snap_tap.targets._resolution_match import (
    ResolutionBlocked,
    matched_fields,
    target_matches,
    validate_snapshot_identity,
    validated_signature_identity,
)
from snap_tap.targets._resolution_payload import (
    target_resolution_to_dict,
    validated_resolution_refs,
)
from snap_tap.targets.models import (
    TARGET_RESOLUTION_SCHEMA_VERSION,
    SnapshotTargetsError,
    TargetResolution,
    TargetResolutionBlockingReason,
    TargetResolutionError,
    TargetResolutionMatch,
    TargetSignature,
)
from snap_tap.targets.snapshot import build_snapshot_targets

__all__ = [
    "TargetResolutionError",
    "resolve_target_signature",
    "target_resolution_to_dict",
]


def resolve_target_signature(
    signature: TargetSignature,
    fresh_snapshot: SemanticSnapshot,
) -> TargetResolution:
    try:
        identity = validated_signature_identity(signature)
    except ResolutionBlocked as blocked:
        return _blocked_resolution(
            signature=signature,
            fresh_snapshot=fresh_snapshot,
            code=blocked.code,
            detail=blocked.detail,
            matched_fields=(),
            candidate_count=0,
            refs=_maybe_validated_refs(fresh_snapshot),
        )

    try:
        refs = _validated_snapshot_refs(fresh_snapshot)
        validate_snapshot_identity(fresh_snapshot)
    except ResolutionBlocked as blocked:
        return _blocked_resolution(
            signature=signature,
            fresh_snapshot=fresh_snapshot,
            code=blocked.code,
            detail=blocked.detail,
            matched_fields=matched_fields(identity),
            candidate_count=0,
        )

    if signature.device_id != fresh_snapshot.device_id:
        return _blocked_resolution(
            signature=signature,
            fresh_snapshot=fresh_snapshot,
            code="target_resolution_device_mismatch",
            detail="Target signature device does not match fresh snapshot device.",
            matched_fields=matched_fields(identity),
            candidate_count=0,
            refs=refs,
        )

    if fresh_snapshot.snapshot_id == signature.source_snapshot_id:
        return _blocked_resolution(
            signature=signature,
            fresh_snapshot=fresh_snapshot,
            code="target_resolution_stale_source_snapshot",
            detail="Fresh target resolution requires a snapshot newer than source.",
            matched_fields=matched_fields(identity),
            candidate_count=0,
            refs=refs,
        )

    try:
        fresh_targets = build_snapshot_targets(fresh_snapshot)
    except SnapshotTargetsError as exc:
        return _blocked_resolution(
            signature=signature,
            fresh_snapshot=fresh_snapshot,
            code="target_resolution_invalid_snapshot",
            detail=exc.detail,
            matched_fields=matched_fields(identity),
            candidate_count=0,
            refs=refs,
        )

    candidates = tuple(
        target for target in fresh_targets.targets if target_matches(identity, target)
    )
    resolved_matched_fields = matched_fields(identity)
    if not candidates:
        return _blocked_resolution(
            signature=signature,
            fresh_snapshot=fresh_snapshot,
            code="target_resolution_no_match",
            detail="Target signature did not match any fresh snapshot target.",
            matched_fields=resolved_matched_fields,
            candidate_count=0,
            refs=refs,
        )
    if len(candidates) > 1:
        return _blocked_resolution(
            signature=signature,
            fresh_snapshot=fresh_snapshot,
            code="target_resolution_ambiguous",
            detail="Target signature matched multiple fresh snapshot targets.",
            matched_fields=resolved_matched_fields,
            candidate_count=len(candidates),
            refs=refs,
        )

    target = candidates[0]
    if not target.enabled:
        return _blocked_resolution(
            signature=signature,
            fresh_snapshot=fresh_snapshot,
            code="target_resolution_disabled",
            detail="Matched fresh target is disabled.",
            matched_fields=resolved_matched_fields,
            candidate_count=1,
            refs=refs,
        )
    if not target.clickable:
        return _blocked_resolution(
            signature=signature,
            fresh_snapshot=fresh_snapshot,
            code="target_resolution_not_clickable",
            detail="Matched fresh target is not clickable.",
            matched_fields=resolved_matched_fields,
            candidate_count=1,
            refs=refs,
        )

    return TargetResolution(
        schema_version=TARGET_RESOLUTION_SCHEMA_VERSION,
        ok=True,
        status="resolved",
        signature_id=signature.signature_id,
        source_snapshot_id=signature.source_snapshot_id,
        resolved_snapshot_id=fresh_snapshot.snapshot_id,
        device_id=signature.device_id,
        resolved_target=target,
        match=TargetResolutionMatch(
            identity_strength=signature.identity_strength,
            matched_fields=resolved_matched_fields,
            candidate_count=1,
        ),
        refs=refs,
    )


def _validated_snapshot_refs(
    snapshot: SemanticSnapshot,
) -> dict[str, SnapshotArtifactRef]:
    try:
        return _validated_refs(snapshot.refs)
    except TargetResolutionError as exc:
        raise ResolutionBlocked(
            code="target_resolution_invalid_snapshot",
            detail=exc.detail,
        ) from exc


def _maybe_validated_refs(
    snapshot: SemanticSnapshot,
) -> dict[str, SnapshotArtifactRef]:
    try:
        return _validated_snapshot_refs(snapshot)
    except ResolutionBlocked:
        return {}


def _blocked_resolution(
    *,
    signature: TargetSignature,
    fresh_snapshot: SemanticSnapshot,
    code: str,
    detail: str,
    matched_fields: tuple[str, ...],
    candidate_count: int,
    refs: Mapping[str, SnapshotArtifactRef] | None = None,
) -> TargetResolution:
    return TargetResolution(
        schema_version=TARGET_RESOLUTION_SCHEMA_VERSION,
        ok=False,
        status="blocked",
        signature_id=signature.signature_id,
        source_snapshot_id=signature.source_snapshot_id,
        resolved_snapshot_id=fresh_snapshot.snapshot_id,
        device_id=signature.device_id,
        match=TargetResolutionMatch(
            identity_strength=signature.identity_strength,
            matched_fields=matched_fields,
            candidate_count=candidate_count,
        ),
        refs=dict(refs or {}),
        blocking_reason=TargetResolutionBlockingReason(
            code=code,
            detail=detail,
            touched_phone=False,
        ),
    )


def _validated_refs(
    refs: Mapping[str, SnapshotArtifactRef],
) -> dict[str, SnapshotArtifactRef]:
    return validated_resolution_refs(refs)
