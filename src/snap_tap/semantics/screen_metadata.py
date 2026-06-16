from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from snap_tap.semantics.models import (
    SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
    SemanticElement,
    SemanticPackageSummary,
    SemanticRole,
    SemanticScreenCounts,
    SemanticScreenMetadata,
    SemanticViewport,
    ViewportOrientation,
)
from snap_tap.snapshots import RawSnapshotCapture, SnapshotElement, SnapshotNormalization


def build_screen_metadata(
    *,
    raw: RawSnapshotCapture,
    elements: tuple[SemanticElement, ...],
) -> SemanticScreenMetadata:
    width = _viewport_dimension(raw, "width")
    height = _viewport_dimension(raw, "height")
    packages = _package_summaries(raw_elements=raw.elements, elements=elements)
    return SemanticScreenMetadata(
        schema_version=SEMANTIC_SCREEN_METADATA_SCHEMA_VERSION,
        viewport=SemanticViewport(
            width=width,
            height=height,
            orientation=_viewport_orientation(width=width, height=height),
        ),
        counts=SemanticScreenCounts(
            source_element_count=len(raw.elements),
            visible_element_count=sum(1 for element in raw.elements if element.visible),
            semantic_element_count=len(elements),
            enabled_count=sum(1 for element in elements if element.enabled),
            clickable_count=sum(1 for element in elements if element.clickable),
            scrollable_count=sum(1 for element in elements if element.scrollable),
            actionable_count=sum(
                1 for element in elements if element.enabled and element.clickable
            ),
            labeled_count=sum(1 for element in elements if element.label is not None),
            unknown_count=sum(
                1 for element in elements if element.role is SemanticRole.UNKNOWN
            ),
        ),
        packages=packages,
        dominant_package=_dominant_package(packages),
    )


def screen_metadata_to_dict(metadata: SemanticScreenMetadata) -> dict[str, object]:
    return {
        "schema_version": metadata.schema_version,
        "viewport": _semantic_viewport_to_dict(metadata.viewport),
        "packages": [
            _semantic_package_summary_to_dict(package)
            for package in metadata.packages
        ],
        "dominant_package": metadata.dominant_package,
        "counts": _semantic_screen_counts_to_dict(metadata.counts),
    }


def _viewport_dimension(
    raw: RawSnapshotCapture,
    axis: Literal["width", "height"],
) -> int | None:
    normalization = raw.normalization
    if normalization is not None:
        normalized = _positive_int_or_none(_normalization_viewport(normalization, axis))
        if normalized is not None:
            return normalized
    metadata_value = _positive_int_or_none(raw.metadata.get(f"screenshot_{axis}"))
    if metadata_value is not None:
        return metadata_value
    screenshot_ref = raw.refs.get("screenshot")
    if screenshot_ref is None:
        return None
    return _positive_int_or_none(screenshot_ref.metadata.get(axis))


def _normalization_viewport(
    normalization: SnapshotNormalization,
    axis: Literal["width", "height"],
) -> int | None:
    if axis == "width":
        return normalization.viewport_width
    return normalization.viewport_height


def _viewport_orientation(
    *,
    width: int | None,
    height: int | None,
) -> ViewportOrientation:
    if width is None or height is None:
        return ViewportOrientation.UNKNOWN
    if height > width:
        return ViewportOrientation.PORTRAIT
    if width > height:
        return ViewportOrientation.LANDSCAPE
    return ViewportOrientation.SQUARE


def _package_summaries(
    *,
    raw_elements: Sequence[SnapshotElement],
    elements: tuple[SemanticElement, ...],
) -> tuple[SemanticPackageSummary, ...]:
    counts: dict[str, dict[str, int]] = {}
    for element in raw_elements:
        _add_raw_package_count(counts, element)
    for semantic_element in elements:
        if semantic_element.package is None:
            continue
        bucket = counts.setdefault(
            semantic_element.package,
            {"element_count": 0, "visible_count": 0, "semantic_count": 0},
        )
        bucket["semantic_count"] += 1
    summaries = (
        SemanticPackageSummary(
            package=package,
            element_count=package_counts["element_count"],
            visible_count=package_counts["visible_count"],
            semantic_count=package_counts["semantic_count"],
        )
        for package, package_counts in counts.items()
    )
    return tuple(
        sorted(
            summaries,
            key=lambda summary: (-summary.semantic_count, summary.package),
        )
    )


def _add_raw_package_count(
    counts: dict[str, dict[str, int]],
    element: SnapshotElement,
) -> None:
    if element.package is None:
        return
    bucket = counts.setdefault(
        element.package,
        {"element_count": 0, "visible_count": 0, "semantic_count": 0},
    )
    bucket["element_count"] += 1
    if element.visible:
        bucket["visible_count"] += 1


def _dominant_package(packages: tuple[SemanticPackageSummary, ...]) -> str | None:
    if not packages:
        return None
    highest = packages[0].semantic_count
    if highest <= 0:
        return None
    dominant = [package for package in packages if package.semantic_count == highest]
    if len(dominant) != 1:
        return None
    return dominant[0].package


def _positive_int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value <= 0:
        return None
    return value


def _semantic_viewport_to_dict(viewport: SemanticViewport) -> dict[str, object]:
    payload: dict[str, object] = {}
    if viewport.width is not None:
        payload["width"] = viewport.width
    if viewport.height is not None:
        payload["height"] = viewport.height
    payload["orientation"] = viewport.orientation.value
    return payload


def _semantic_package_summary_to_dict(
    package: SemanticPackageSummary,
) -> dict[str, object]:
    return {
        "package": package.package,
        "element_count": package.element_count,
        "visible_count": package.visible_count,
        "semantic_count": package.semantic_count,
    }


def _semantic_screen_counts_to_dict(
    counts: SemanticScreenCounts,
) -> dict[str, object]:
    return {
        "source_element_count": counts.source_element_count,
        "visible_element_count": counts.visible_element_count,
        "semantic_element_count": counts.semantic_element_count,
        "enabled_count": counts.enabled_count,
        "clickable_count": counts.clickable_count,
        "scrollable_count": counts.scrollable_count,
        "actionable_count": counts.actionable_count,
        "labeled_count": counts.labeled_count,
        "unknown_count": counts.unknown_count,
    }
