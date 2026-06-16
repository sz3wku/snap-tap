from __future__ import annotations

from typing import cast

import pytest

from snap_tap.snapshots import (
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotBounds,
    SnapshotElement,
    SnapshotIdentity,
    SnapshotNormalization,
)


def test_screen_metadata_counts_packages_and_dominant_package() -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    raw = _raw_capture(
        elements=[
            _element(
                source_index=0,
                class_name="android.widget.Button",
                package="com.b",
                content_desc="Save",
            ),
            _element(
                source_index=1,
                enabled=False,
                clickable=True,
                class_name="android.widget.TextView",
                package="com.a",
            ),
            _element(
                source_index=2,
                clickable=False,
                package="com.b",
                text="Secondary label",
            ),
            _element(source_index=3, visible=False, package="com.a"),
            _element(source_index=4, package=None),
        ],
        viewport_width=1080,
        viewport_height=2400,
    )

    payload = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    metadata = cast(dict[str, object], payload["screen_metadata"])

    assert metadata == {
        "schema_version": "semantic_screen_metadata.v1",
        "viewport": {
            "width": 1080,
            "height": 2400,
            "orientation": "portrait",
        },
        "packages": [
            {
                "package": "com.b",
                "element_count": 2,
                "visible_count": 2,
                "semantic_count": 2,
            },
            {
                "package": "com.a",
                "element_count": 2,
                "visible_count": 1,
                "semantic_count": 1,
            },
        ],
        "dominant_package": "com.b",
        "counts": {
            "source_element_count": 5,
            "visible_element_count": 4,
            "semantic_element_count": 4,
            "enabled_count": 3,
            "clickable_count": 3,
            "scrollable_count": 0,
            "actionable_count": 2,
            "labeled_count": 2,
            "unknown_count": 1,
        },
    }


def test_screen_metadata_returns_null_dominant_package_on_tie() -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    raw = _raw_capture(
        elements=[
            _element(source_index=0, package="com.b"),
            _element(source_index=1, package="com.a"),
        ],
        metadata={"screenshot_width": 0, "screenshot_height": "bad"},
    )

    payload = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    metadata = cast(dict[str, object], payload["screen_metadata"])

    assert metadata["viewport"] == {"orientation": "unknown"}
    assert metadata["packages"] == [
        {
            "package": "com.a",
            "element_count": 1,
            "visible_count": 1,
            "semantic_count": 1,
        },
        {
            "package": "com.b",
            "element_count": 1,
            "visible_count": 1,
            "semantic_count": 1,
        },
    ]
    assert metadata["dominant_package"] is None


def test_screen_metadata_returns_null_dominant_package_without_semantic_elements() -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    raw = _raw_capture(
        elements=[_element(source_index=0, visible=False, package="com.hidden")],
        viewport_width=1080,
        viewport_height=2400,
    )

    payload = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    metadata = cast(dict[str, object], payload["screen_metadata"])

    assert metadata["packages"] == [
        {
            "package": "com.hidden",
            "element_count": 1,
            "visible_count": 0,
            "semantic_count": 0,
        }
    ]
    assert metadata["dominant_package"] is None
    counts = cast(dict[str, object], metadata["counts"])
    assert counts["semantic_element_count"] == 0


@pytest.mark.parametrize(
    ("width", "height", "orientation"),
    [
        (600, 300, "landscape"),
        (400, 400, "square"),
    ],
)
def test_screen_metadata_derives_non_portrait_orientation(
    width: int,
    height: int,
    orientation: str,
) -> None:
    from snap_tap.semantics.snapshot import (
        build_semantic_snapshot,
        semantic_snapshot_to_dict,
    )

    raw = _raw_capture(
        elements=[_element(source_index=0)],
        viewport_width=width,
        viewport_height=height,
    )

    payload = semantic_snapshot_to_dict(build_semantic_snapshot(raw))
    metadata = cast(dict[str, object], payload["screen_metadata"])
    viewport = cast(dict[str, object], metadata["viewport"])

    assert viewport["orientation"] == orientation


def _raw_capture(
    *,
    elements: list[SnapshotElement],
    viewport_width: int | None = None,
    viewport_height: int | None = None,
    metadata: dict[str, object] | None = None,
) -> RawSnapshotCapture:
    return RawSnapshotCapture(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation="snapshot_capture",
        checked_at="2026-06-14T10:00:00+00:00",
        elapsed_ms=1.0,
        refs={
            "xml": SnapshotArtifactRef(
                path="screen.xml",
                sha256="xml-sha",
                byte_length=123,
                metadata={"node_count": len(elements)},
            ),
            "screenshot": SnapshotArtifactRef(
                path="screen.png",
                sha256="png-sha",
                byte_length=456,
                metadata={},
            ),
        },
        identity=SnapshotIdentity(
            snapshot_id="snap_test",
            snapshot_hash="sha256:raw",
            hash_version="raw_snapshot_hash.v1",
        ),
        elements=tuple(elements),
        normalization=SnapshotNormalization(
            schema_version="snapshot_elements.v1",
            status="completed",
            source_node_count=len(elements),
            element_count=len(elements),
            visible_count=sum(1 for element in elements if element.visible),
            enabled_count=sum(1 for element in elements if element.enabled),
            clickable_count=sum(1 for element in elements if element.clickable),
            discarded_count=0,
            invalid_bounds_count=0,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        ),
        metadata=metadata or {},
    )


def _element(
    *,
    source_index: int,
    visible: bool = True,
    enabled: bool = True,
    clickable: bool = True,
    class_name: str | None = None,
    package: str | None = "com.example",
    text: str | None = None,
    content_desc: str | None = None,
) -> SnapshotElement:
    return SnapshotElement(
        source_index=source_index,
        depth=0,
        bounds=SnapshotBounds(
            left=10,
            top=20,
            right=110,
            bottom=220,
            width=100,
            height=200,
            center_x=60.0,
            center_y=120.0,
        ),
        visible=visible,
        enabled=enabled,
        clickable=clickable,
        class_name=class_name,
        package=package,
        text=text,
        content_desc=content_desc,
    )
