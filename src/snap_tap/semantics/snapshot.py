from __future__ import annotations

from dataclasses import replace
import re

from snap_tap.semantics.models import (
    SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
    SemanticElement,
    SemanticRole,
    SemanticRoleNormalization,
    SemanticSnapshot,
    SemanticSnapshotError,
)
from snap_tap.semantics.roles import classify_semantic_role
from snap_tap.semantics.screen_metadata import (
    build_screen_metadata,
    screen_metadata_to_dict,
)
from snap_tap.snapshots import (
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotBounds,
    SnapshotElement,
)


_SOURCE_SCHEMA_VERSION = "snapshot_elements.v1"
_ACCESSIBILITY_FIELDS = ("text", "content_desc", "hint")
_LABEL_PRECEDENCE = ("content_desc", "text", "hint")
_LABEL_NONE = "none"
_LABEL_DESCENDANT_TEXT = "descendant_text"
_SOURCE_TEXT_MAX_LENGTH = 256
_WHITESPACE_RE = re.compile(r"\s+")
__all__ = [
    "SemanticSnapshotError",
    "build_semantic_snapshot",
    "semantic_snapshot_to_dict",
]


def build_semantic_snapshot(raw: RawSnapshotCapture) -> SemanticSnapshot:
    if not raw.ok or raw.identity is None or raw.device_id is None:
        raise SemanticSnapshotError(
            code="semantic_snapshot_input_invalid",
            detail="Semantic snapshot requires a successful raw snapshot identity.",
        )
    if raw.normalization is None:
        raise SemanticSnapshotError(
            code="semantic_snapshot_input_invalid",
            detail="Semantic snapshot requires raw element normalization metadata.",
        )
    if raw.normalization.schema_version != _SOURCE_SCHEMA_VERSION:
        raise SemanticSnapshotError(
            code="semantic_snapshot_unsupported_version",
            detail="Semantic snapshot received unsupported raw element schema.",
        )

    visible_elements = tuple(element for element in raw.elements if element.visible)
    elements = _semantic_elements(visible_elements)
    return SemanticSnapshot(
        schema_version=SEMANTIC_SNAPSHOT_SCHEMA_VERSION,
        snapshot_id=raw.identity.snapshot_id,
        device_id=raw.device_id,
        captured_at=raw.checked_at,
        refs=dict(raw.refs),
        elements=elements,
        screen_metadata=build_screen_metadata(raw=raw, elements=elements),
        role_normalization=_role_normalization(
            source_element_count=len(raw.elements),
            visible_element_count=sum(1 for element in raw.elements if element.visible),
            elements=elements,
        ),
    )


def semantic_snapshot_to_dict(snapshot: SemanticSnapshot) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": snapshot.schema_version,
        "snapshot_id": snapshot.snapshot_id,
        "device_id": snapshot.device_id,
        "captured_at": snapshot.captured_at,
        "refs": {
            name: _snapshot_artifact_ref_to_dict(name, ref)
            for name, ref in snapshot.refs.items()
        },
        "elements": [
            _semantic_element_to_dict(element) for element in snapshot.elements
        ],
        "screen_metadata": screen_metadata_to_dict(snapshot.screen_metadata),
        "role_normalization": _role_normalization_to_dict(
            snapshot.role_normalization
        ),
    }
    return payload


def _semantic_elements(elements: tuple[SnapshotElement, ...]) -> tuple[SemanticElement, ...]:
    semantic_elements = tuple(_semantic_element(element) for element in elements)
    return tuple(
        _with_descendant_label(
            semantic=semantic,
            source=source,
            elements=elements,
            index=index,
        )
        for index, (source, semantic) in enumerate(
            zip(elements, semantic_elements, strict=True)
        )
    )


def _semantic_element(element: SnapshotElement) -> SemanticElement:
    accessibility = _accessibility_fields(element)
    label_source, label = _primary_label(accessibility)
    return SemanticElement(
        source_index=element.source_index,
        role=classify_semantic_role(element),
        bounds=element.bounds,
        enabled=element.enabled,
        clickable=element.clickable,
        scrollable=element.scrollable,
        label=label,
        label_source=label_source,
        accessibility=accessibility,
        class_name=element.class_name,
        resource_id=element.resource_id,
        package=element.package,
    )


def _with_descendant_label(
    *,
    semantic: SemanticElement,
    source: SnapshotElement,
    elements: tuple[SnapshotElement, ...],
    index: int,
) -> SemanticElement:
    if semantic.label is not None or not source.clickable or not source.enabled:
        return semantic
    label = _single_descendant_label(source, elements=elements, index=index)
    if label is None:
        return semantic
    return replace(
        semantic,
        label=label,
        label_source=_LABEL_DESCENDANT_TEXT,
    )


def _single_descendant_label(
    source: SnapshotElement,
    *,
    elements: tuple[SnapshotElement, ...],
    index: int,
) -> str | None:
    candidates: list[str] = []
    for descendant in elements[index + 1 :]:
        if descendant.depth <= source.depth:
            break
        if not _bounds_contain(source.bounds, descendant.bounds):
            continue
        label = _primary_label(_accessibility_fields(descendant))[1]
        if label is not None:
            candidates.append(label)
    unique = tuple(dict.fromkeys(candidates))
    if len(unique) != 1:
        return None
    return unique[0]


def _bounds_contain(container: SnapshotBounds, child: SnapshotBounds) -> bool:
    return (
        container.left <= child.left
        and container.top <= child.top
        and container.right >= child.right
        and container.bottom >= child.bottom
    )


def _accessibility_fields(element: SnapshotElement) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key in _ACCESSIBILITY_FIELDS:
        value = _normalized_source_text(getattr(element, key))
        if value is not None:
            fields[key] = value
    return fields


def _primary_label(accessibility: dict[str, str]) -> tuple[str, str | None]:
    for key in _LABEL_PRECEDENCE:
        value = accessibility.get(key)
        if value is not None:
            return key, value
    return _LABEL_NONE, None


def _normalized_source_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = _WHITESPACE_RE.sub(" ", value.strip())
    if not normalized:
        return None
    return normalized[:_SOURCE_TEXT_MAX_LENGTH].rstrip() or None


def _role_normalization(
    *,
    source_element_count: int,
    visible_element_count: int,
    elements: tuple[SemanticElement, ...],
) -> SemanticRoleNormalization:
    role_counts = {role.value: 0 for role in SemanticRole}
    for element in elements:
        role_counts[element.role.value] += 1
    accessibility_field_counts = {key: 0 for key in _ACCESSIBILITY_FIELDS}
    for element in elements:
        for key in element.accessibility:
            accessibility_field_counts[key] += 1
    return SemanticRoleNormalization(
        source_schema_version=_SOURCE_SCHEMA_VERSION,
        source_element_count=source_element_count,
        visible_element_count=visible_element_count,
        semantic_element_count=len(elements),
        role_counts=role_counts,
        unknown_count=role_counts[SemanticRole.UNKNOWN.value],
        labeled_count=sum(1 for element in elements if element.label is not None),
        accessibility_field_counts=accessibility_field_counts,
    )


def _semantic_element_to_dict(element: SemanticElement) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_index": element.source_index,
        "role": element.role.value,
        "bounds": _snapshot_bounds_to_dict(element.bounds),
        "enabled": element.enabled,
        "clickable": element.clickable,
        "scrollable": element.scrollable,
        "label": element.label,
        "label_source": element.label_source,
        "accessibility": dict(element.accessibility),
    }
    if element.class_name is not None:
        payload["class_name"] = element.class_name
    if element.resource_id is not None:
        payload["resource_id"] = element.resource_id
    if element.package is not None:
        payload["package"] = element.package
    return payload


def _snapshot_bounds_to_dict(bounds: SnapshotBounds) -> dict[str, object]:
    return {
        "left": bounds.left,
        "top": bounds.top,
        "right": bounds.right,
        "bottom": bounds.bottom,
        "width": bounds.width,
        "height": bounds.height,
        "center_x": bounds.center_x,
        "center_y": bounds.center_y,
    }


def _snapshot_artifact_ref_to_dict(
    name: str,
    ref: SnapshotArtifactRef,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "path": ref.path,
        "sha256": ref.sha256,
        "byte_length": ref.byte_length,
    }
    metadata = dict(ref.metadata)
    if name == "xml":
        node_count = metadata.get("node_count")
        if isinstance(node_count, int) and not isinstance(node_count, bool):
            payload["node_count"] = node_count
    elif name == "screenshot":
        image_format = metadata.get("format")
        if isinstance(image_format, str):
            payload["format"] = image_format
        for key in ("width", "height"):
            value = metadata.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                payload[key] = value
    elif name == "manifest":
        schema_version = metadata.get("schema_version")
        if isinstance(schema_version, str):
            payload["metadata"] = {"schema_version": schema_version}
    return payload


def _role_normalization_to_dict(
    normalization: SemanticRoleNormalization | None,
) -> dict[str, object] | None:
    if normalization is None:
        return None
    return {
        "source_schema_version": normalization.source_schema_version,
        "source_element_count": normalization.source_element_count,
        "visible_element_count": normalization.visible_element_count,
        "semantic_element_count": normalization.semantic_element_count,
        "role_counts": dict(normalization.role_counts),
        "unknown_count": normalization.unknown_count,
        "labeled_count": normalization.labeled_count,
        "accessibility_field_counts": dict(normalization.accessibility_field_counts),
    }
