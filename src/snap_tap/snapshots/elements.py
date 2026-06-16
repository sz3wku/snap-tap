from __future__ import annotations

import re
from collections.abc import Iterator

from lxml import etree  # type: ignore[import-untyped]

from snap_tap.snapshots.models import (
    SnapshotBounds,
    SnapshotElement,
    SnapshotNormalization,
)


SNAPSHOT_ELEMENTS_SCHEMA_VERSION = "snapshot_elements.v1"
_BOUNDS_RE = re.compile(r"^\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]$")
_WHITESPACE_RE = re.compile(r"\s+")
_SOURCE_TEXT_MAX_LENGTH = 256


class SnapshotNormalizationError(Exception):
    def __init__(
        self,
        *,
        code: str,
        detail: str,
        normalization: SnapshotNormalization,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.normalization = normalization


def normalize_snapshot_elements(
    *,
    xml: str,
    viewport_width: object = None,
    viewport_height: object = None,
) -> tuple[tuple[SnapshotElement, ...], SnapshotNormalization]:
    width = _positive_int_or_none(viewport_width)
    height = _positive_int_or_none(viewport_height)
    try:
        root = etree.fromstring(
            xml.encode("utf-8"),
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except etree.XMLSyntaxError as exc:
        normalization = _normalization(
            status="failed",
            source_node_count=0,
            element_count=0,
            invalid_bounds_count=0,
            viewport_width=width,
            viewport_height=height,
        )
        raise SnapshotNormalizationError(
            code="snapshot_parse_failed",
            detail="Snapshot XML could not be parsed for element normalization.",
            normalization=normalization,
        ) from exc

    elements: list[SnapshotElement] = []
    source_node_count = 0
    invalid_bounds_count = 0
    for node, source_index, depth in _iter_nodes(root):
        source_node_count += 1
        bounds = _parse_bounds(node.get("bounds"))
        if bounds is None:
            invalid_bounds_count += 1
            continue
        elements.append(
            SnapshotElement(
                source_index=source_index,
                depth=depth,
                bounds=bounds,
                visible=_is_visible(node, bounds, width, height),
                enabled=_bool_attr(node.get("enabled")),
                clickable=_bool_attr(node.get("clickable")),
                scrollable=_bool_attr(node.get("scrollable")),
                class_name=_optional_attr(node.get("class")),
                resource_id=_optional_attr(node.get("resource-id")),
                package=_optional_attr(node.get("package")),
                text=_normalized_source_text(node.get("text")),
                content_desc=_normalized_source_text(node.get("content-desc")),
                hint=_normalized_source_text(node.get("hint")),
            )
        )

    normalization = _normalization(
        status="completed",
        source_node_count=source_node_count,
        elements=tuple(elements),
        invalid_bounds_count=invalid_bounds_count,
        viewport_width=width,
        viewport_height=height,
    )
    if not elements:
        raise SnapshotNormalizationError(
            code="snapshot_empty",
            detail="Snapshot XML did not contain any valid bounded nodes.",
            normalization=normalization,
        )
    return tuple(elements), normalization


def _iter_nodes(root: etree._Element) -> Iterator[tuple[etree._Element, int, int]]:
    source_index = 0

    def visit(node: etree._Element, depth: int) -> Iterator[tuple[etree._Element, int, int]]:
        nonlocal source_index
        current_index = source_index
        source_index += 1
        yield node, current_index, depth
        for child in node:
            if _is_node(child):
                yield from visit(child, depth + 1)

    if _is_node(root):
        yield from visit(root, 0)
        return
    for child in root:
        if _is_node(child):
            yield from visit(child, 0)


def _is_node(value: object) -> bool:
    return isinstance(value, etree._Element) and value.tag == "node"


def _parse_bounds(value: str | None) -> SnapshotBounds | None:
    if value is None:
        return None
    match = _BOUNDS_RE.match(value.strip())
    if match is None:
        return None
    left, top, right, bottom = (int(group) for group in match.groups())
    if right < left or bottom < top:
        return None
    width = right - left
    height = bottom - top
    return SnapshotBounds(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        width=width,
        height=height,
        center_x=left + (width / 2),
        center_y=top + (height / 2),
    )


def _is_visible(
    node: etree._Element,
    bounds: SnapshotBounds,
    viewport_width: int | None,
    viewport_height: int | None,
) -> bool:
    if not _bool_attr(node.get("visible-to-user")):
        return False
    if bounds.width <= 0 or bounds.height <= 0:
        return False
    if viewport_width is None or viewport_height is None:
        return True
    return (
        bounds.right > 0
        and bounds.bottom > 0
        and bounds.left < viewport_width
        and bounds.top < viewport_height
    )


def _bool_attr(value: str | None) -> bool:
    return isinstance(value, str) and value.strip().lower() == "true"


def _optional_attr(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalized_source_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = _WHITESPACE_RE.sub(" ", value.strip())
    if not normalized:
        return None
    return normalized[:_SOURCE_TEXT_MAX_LENGTH].rstrip() or None


def _positive_int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value <= 0:
        return None
    return value


def _normalization(
    *,
    status: str,
    source_node_count: int,
    invalid_bounds_count: int,
    viewport_width: int | None,
    viewport_height: int | None,
    element_count: int | None = None,
    elements: tuple[SnapshotElement, ...] = (),
) -> SnapshotNormalization:
    resolved_element_count = element_count if element_count is not None else len(elements)
    return SnapshotNormalization(
        schema_version=SNAPSHOT_ELEMENTS_SCHEMA_VERSION,
        status=status,
        source_node_count=source_node_count,
        element_count=resolved_element_count,
        visible_count=sum(1 for element in elements if element.visible),
        enabled_count=sum(1 for element in elements if element.enabled),
        clickable_count=sum(1 for element in elements if element.clickable),
        scrollable_count=sum(1 for element in elements if element.scrollable),
        discarded_count=invalid_bounds_count,
        invalid_bounds_count=invalid_bounds_count,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )
