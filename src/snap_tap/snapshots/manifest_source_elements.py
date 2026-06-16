from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from snap_tap.snapshots.elements import (
    SnapshotNormalizationError,
    normalize_snapshot_elements,
)
from snap_tap.snapshots.manifest_source_common import (
    boolean,
    mapping,
    non_negative_int,
    number,
    optional_bool,
    optional_positive_int,
    optional_text,
    required_text,
    sequence,
)
from snap_tap.snapshots.manifest_source_types import (
    SnapshotManifestSourceError,
    invalid_manifest_source,
)
from snap_tap.snapshots.models import (
    SnapshotArtifactRef,
    SnapshotBounds,
    SnapshotElement,
    SnapshotNormalization,
)


def verified_manifest_elements(
    *,
    normalization_payload: object,
    elements_payload: object,
    xml_ref: SnapshotArtifactRef,
    screenshot_ref: SnapshotArtifactRef,
) -> tuple[tuple[SnapshotElement, ...], SnapshotNormalization]:
    manifest_elements = _elements(elements_payload)
    manifest_normalization = _normalization(
        normalization_payload,
        elements_payload,
    )
    xml_elements, xml_normalization = _verified_xml_elements(
        xml_ref=xml_ref,
        screenshot_ref=screenshot_ref,
    )
    if manifest_elements != xml_elements:
        raise invalid_manifest_source(
            "Snapshot manifest elements do not match verified XML artifact."
        )
    if manifest_normalization != xml_normalization:
        raise invalid_manifest_source(
            "Snapshot manifest normalization does not match verified XML artifact."
        )
    return xml_elements, xml_normalization


def _verified_xml_elements(
    *,
    xml_ref: SnapshotArtifactRef,
    screenshot_ref: SnapshotArtifactRef,
) -> tuple[tuple[SnapshotElement, ...], SnapshotNormalization]:
    try:
        xml = Path(xml_ref.path).read_text(encoding="utf-8")
    except OSError as exc:
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_missing",
            detail="Snapshot XML artifact referenced by manifest could not be read.",
        ) from exc
    screenshot_metadata = dict(screenshot_ref.metadata)
    try:
        elements, normalization = normalize_snapshot_elements(
            xml=xml,
            viewport_width=screenshot_metadata.get("width"),
            viewport_height=screenshot_metadata.get("height"),
        )
    except SnapshotNormalizationError as exc:
        raise SnapshotManifestSourceError(
            code="explicit_snapshot_source_invalid",
            detail="Snapshot XML artifact could not reconstruct manifest elements.",
        ) from exc
    return tuple(_redacted_element(element) for element in elements), normalization


def _redacted_element(element: SnapshotElement) -> SnapshotElement:
    return replace(element, text=None, content_desc=None, hint=None)


def _normalization(value: object, elements_value: object) -> SnapshotNormalization:
    payload = mapping(value, "normalization")
    elements = sequence(elements_value, "elements")
    return SnapshotNormalization(
        schema_version=required_text(
            payload.get("schema_version"),
            "normalization.schema_version",
        ),
        status=required_text(payload.get("status"), "normalization.status"),
        source_node_count=non_negative_int(
            payload.get("source_node_count"),
            "normalization.source_node_count",
        ),
        element_count=non_negative_int(
            payload.get("element_count"),
            "normalization.element_count",
        ),
        visible_count=non_negative_int(
            payload.get("visible_count"),
            "normalization.visible_count",
        ),
        enabled_count=non_negative_int(
            payload.get("enabled_count"),
            "normalization.enabled_count",
        ),
        clickable_count=non_negative_int(
            payload.get("clickable_count"),
            "normalization.clickable_count",
        ),
        discarded_count=non_negative_int(
            payload.get("discarded_count"),
            "normalization.discarded_count",
        ),
        invalid_bounds_count=non_negative_int(
            payload.get("invalid_bounds_count"),
            "normalization.invalid_bounds_count",
        ),
        viewport_width=optional_positive_int(
            payload.get("viewport_width"),
            "normalization.viewport_width",
        ),
        viewport_height=optional_positive_int(
            payload.get("viewport_height"),
            "normalization.viewport_height",
        ),
        scrollable_count=sum(
            1 for item in elements if mapping(item, "element").get("scrollable") is True
        ),
    )


def _elements(value: object) -> tuple[SnapshotElement, ...]:
    return tuple(_element(item) for item in sequence(value, "elements"))


def _element(value: object) -> SnapshotElement:
    payload = mapping(value, "element")
    allowed = {
        "source_index",
        "depth",
        "bounds",
        "visible",
        "enabled",
        "clickable",
        "scrollable",
        "class_name",
        "resource_id",
        "package",
    }
    if set(payload) - allowed:
        raise invalid_manifest_source("Snapshot manifest element contains invalid fields.")
    return SnapshotElement(
        source_index=non_negative_int(payload.get("source_index"), "element.source_index"),
        depth=non_negative_int(payload.get("depth"), "element.depth"),
        bounds=_bounds(payload.get("bounds")),
        visible=boolean(payload.get("visible"), "element.visible"),
        enabled=boolean(payload.get("enabled"), "element.enabled"),
        clickable=boolean(payload.get("clickable"), "element.clickable"),
        scrollable=optional_bool(payload.get("scrollable")),
        class_name=optional_text(payload.get("class_name"), "element.class_name"),
        resource_id=optional_text(payload.get("resource_id"), "element.resource_id"),
        package=optional_text(payload.get("package"), "element.package"),
    )


def _bounds(value: object) -> SnapshotBounds:
    payload = mapping(value, "bounds")
    return SnapshotBounds(
        left=non_negative_int(payload.get("left"), "bounds.left"),
        top=non_negative_int(payload.get("top"), "bounds.top"),
        right=non_negative_int(payload.get("right"), "bounds.right"),
        bottom=non_negative_int(payload.get("bottom"), "bounds.bottom"),
        width=non_negative_int(payload.get("width"), "bounds.width"),
        height=non_negative_int(payload.get("height"), "bounds.height"),
        center_x=number(payload.get("center_x"), "bounds.center_x"),
        center_y=number(payload.get("center_y"), "bounds.center_y"),
    )
