from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace

from snap_tap.snapshots.elements import (
    SnapshotNormalizationError,
    normalize_snapshot_elements,
)
from snap_tap.snapshots.identity import (
    build_operator_observation_identity,
    build_snapshot_identity,
)
from snap_tap.snapshots.models import (
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotElement,
    SnapshotNormalization,
)


def complete_operator_observation(result: RawSnapshotCapture) -> RawSnapshotCapture:
    if result.xml is None:
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code="snapshot_dump_failed",
            detail="Operator observation completed without XML content.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
        )

    try:
        elements, normalization = normalize_snapshot_elements(
            xml=result.xml,
            viewport_width=result.metadata.get("viewport_width"),
            viewport_height=result.metadata.get("viewport_height"),
        )
        normalization = _with_inferred_viewport(
            normalization,
            elements=elements,
        )
    except SnapshotNormalizationError as exc:
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code=exc.code,
            detail=exc.detail,
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
            normalization=exc.normalization,
        )

    observed = result.with_elements(
        elements=elements,
        normalization=normalization,
    )
    identity = build_operator_observation_identity(observed)
    if identity is None:
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code="snapshot_evidence_missing",
            detail="Failed to build operator observation identity.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
        )
    return observed.with_identity(identity).without_payloads()


def complete_raw_snapshot_observation(result: RawSnapshotCapture) -> RawSnapshotCapture:
    if result.xml is None or result.image_bytes is None:
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code="snapshot_evidence_missing",
            detail="Snapshot capture completed without raw observation payloads.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
        )

    xml = result.xml
    xml_bytes = xml.encode("utf-8")
    screenshot_bytes = result.image_bytes
    observed = result.with_refs(
        {
            "xml": SnapshotArtifactRef(
                path="",
                sha256=_sha256(xml_bytes),
                byte_length=len(xml_bytes),
                metadata={"node_count": xml.count("<node")},
            ),
            "screenshot": SnapshotArtifactRef(
                path="",
                sha256=_sha256(screenshot_bytes),
                byte_length=len(screenshot_bytes),
                metadata=_screenshot_ref_metadata(result.metadata),
            ),
        }
    )
    identity = build_snapshot_identity(observed)
    if identity is None:
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code="snapshot_evidence_missing",
            detail="Failed to build raw snapshot identity.",
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
        )
    try:
        elements, normalization = normalize_snapshot_elements(
            xml=xml,
            viewport_width=result.metadata.get("screenshot_width"),
            viewport_height=result.metadata.get("screenshot_height"),
        )
    except SnapshotNormalizationError as exc:
        return RawSnapshotCapture.failure(
            backend=result.backend,
            code=exc.code,
            detail=exc.detail,
            device_id=result.device_id,
            elapsed_ms=result.elapsed_ms,
            metadata=result.metadata,
            normalization=exc.normalization,
        )
    return observed.with_identity(identity).with_elements(
        elements=elements,
        normalization=normalization,
    )


def _with_inferred_viewport(
    normalization: SnapshotNormalization,
    *,
    elements: tuple[SnapshotElement, ...],
) -> SnapshotNormalization:
    if (
        normalization.viewport_width is not None
        and normalization.viewport_height is not None
    ):
        return normalization
    max_right = max((element.bounds.right for element in elements), default=0)
    max_bottom = max((element.bounds.bottom for element in elements), default=0)
    width = normalization.viewport_width or (max_right if max_right > 0 else None)
    height = normalization.viewport_height or (max_bottom if max_bottom > 0 else None)
    if (
        width == normalization.viewport_width
        and height == normalization.viewport_height
    ):
        return normalization
    return replace(normalization, viewport_width=width, viewport_height=height)


def _screenshot_ref_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    public: dict[str, object] = {}
    image_format = metadata.get("screenshot_format")
    if isinstance(image_format, str):
        public["format"] = image_format
    width = metadata.get("screenshot_width")
    if isinstance(width, int) and not isinstance(width, bool):
        public["width"] = width
    height = metadata.get("screenshot_height")
    if isinstance(height, int) and not isinstance(height, bool):
        public["height"] = height
    return public


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
