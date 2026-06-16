from __future__ import annotations

import pytest

from snap_tap.snapshots.elements import (
    SnapshotNormalizationError,
    normalize_snapshot_elements,
)


def test_normalize_snapshot_elements_uses_depth_first_source_order() -> None:
    xml = """
    <hierarchy>
      <node class="android.widget.FrameLayout" bounds="[0,0][100,100]"
            visible-to-user="true" enabled="true" clickable="false">
        <node resource-id="com.example:id/child" package="com.example"
              bounds="[10,20][30,60]" visible-to-user="true"
              enabled="false" clickable="true" text="  secret
              value  " hint="  Type   here  " />
      </node>
      <node bounds="[200,200][250,260]" visible-to-user="false"
            enabled="true" clickable="true" content-desc="redacted" />
    </hierarchy>
    """

    elements, normalization = normalize_snapshot_elements(
        xml=xml,
        viewport_width=300,
        viewport_height=300,
    )

    assert [element.source_index for element in elements] == [0, 1, 2]
    assert [element.depth for element in elements] == [0, 1, 0]
    assert [element.visible for element in elements] == [True, True, False]
    assert elements[1].clickable is True
    assert elements[1].resource_id == "com.example:id/child"
    assert elements[1].package == "com.example"
    assert elements[1].text == "secret value"
    assert elements[1].hint == "Type here"
    assert elements[2].content_desc == "redacted"
    assert normalization.schema_version == "snapshot_elements.v1"
    assert normalization.source_node_count == 3
    assert normalization.element_count == 3
    assert normalization.visible_count == 2
    assert normalization.enabled_count == 2
    assert normalization.clickable_count == 2
    assert normalization.discarded_count == 0


def test_normalize_snapshot_elements_discards_invalid_bounds() -> None:
    xml = """
    <hierarchy>
      <node bounds="[0,0][10,10]" visible-to-user="true" />
      <node visible-to-user="true" />
      <node bounds="[10,10][5,20]" visible-to-user="true" />
      <node bounds="bad" visible-to-user="true" />
    </hierarchy>
    """

    elements, normalization = normalize_snapshot_elements(xml=xml)

    assert len(elements) == 1
    assert elements[0].source_index == 0
    assert normalization.source_node_count == 4
    assert normalization.invalid_bounds_count == 3
    assert normalization.discarded_count == 3


def test_normalize_snapshot_elements_requires_viewport_intersection() -> None:
    xml = """
    <hierarchy>
      <node bounds="[100,100][200,200]" visible-to-user="true" />
      <node bounds="[1100,100][1200,200]" visible-to-user="true" />
      <node bounds="[0,0][0,20]" visible-to-user="true" />
    </hierarchy>
    """

    elements, normalization = normalize_snapshot_elements(
        xml=xml,
        viewport_width=1080,
        viewport_height=2400,
    )

    assert [element.visible for element in elements] == [True, False, False]
    assert normalization.element_count == 3
    assert normalization.visible_count == 1


def test_normalize_snapshot_elements_fails_closed_on_malformed_xml() -> None:
    with pytest.raises(SnapshotNormalizationError) as exc_info:
        normalize_snapshot_elements(xml="<hierarchy><node></hierarchy>")

    assert exc_info.value.code == "snapshot_parse_failed"
    assert exc_info.value.normalization.status == "failed"


def test_normalize_snapshot_elements_fails_closed_when_empty() -> None:
    with pytest.raises(SnapshotNormalizationError) as exc_info:
        normalize_snapshot_elements(xml="<hierarchy><node /></hierarchy>")

    assert exc_info.value.code == "snapshot_empty"
    assert exc_info.value.normalization.source_node_count == 1
    assert exc_info.value.normalization.invalid_bounds_count == 1
