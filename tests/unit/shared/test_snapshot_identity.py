from __future__ import annotations

from dataclasses import replace

from snap_tap.snapshots import (
    OPERATOR_OBSERVATION_HASH_VERSION,
    SNAPSHOT_HASH_VERSION,
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotNormalization,
    build_operator_observation_identity,
    build_snapshot_identity,
)


def test_snapshot_identity_is_deterministic_for_same_refs() -> None:
    first = _capture(ref_path_prefix="a", checked_at="2026-06-13T20:31:51+00:00")
    second = _capture(ref_path_prefix="b", checked_at="2026-06-13T20:31:51+00:00")

    first_identity = build_snapshot_identity(first)
    second_identity = build_snapshot_identity(second)

    assert first_identity is not None
    assert second_identity is not None
    assert first_identity.snapshot_hash == second_identity.snapshot_hash
    assert first_identity.snapshot_id == second_identity.snapshot_id
    assert first_identity.hash_version == SNAPSHOT_HASH_VERSION


def test_snapshot_hash_ignores_checked_at_but_snapshot_id_uses_it() -> None:
    first = _capture(checked_at="2026-06-13T20:31:51+00:00")
    second = _capture(checked_at="2026-06-13T20:31:52+00:00")

    first_identity = build_snapshot_identity(first)
    second_identity = build_snapshot_identity(second)

    assert first_identity is not None
    assert second_identity is not None
    assert first_identity.snapshot_hash == second_identity.snapshot_hash
    assert first_identity.snapshot_id != second_identity.snapshot_id


def test_snapshot_hash_changes_when_xml_hash_changes() -> None:
    first = build_snapshot_identity(_capture())
    second = build_snapshot_identity(
        _capture(xml_sha="b" * 64),
    )

    assert first is not None
    assert second is not None
    assert first.snapshot_hash != second.snapshot_hash


def test_snapshot_hash_changes_when_screenshot_hash_changes() -> None:
    first = build_snapshot_identity(_capture())
    second = build_snapshot_identity(
        _capture(screenshot_sha="c" * 64),
    )

    assert first is not None
    assert second is not None
    assert first.snapshot_hash != second.snapshot_hash


def test_snapshot_identity_returns_none_when_required_ref_metadata_is_missing() -> None:
    capture = _capture()
    broken_screenshot = replace(
        capture.refs["screenshot"],
        metadata={"format": "png", "width": 1080},
    )
    capture = replace(
        capture,
        refs={**capture.refs, "screenshot": broken_screenshot},
    )

    assert build_snapshot_identity(capture) is None


def test_snapshot_identity_allows_zero_node_count() -> None:
    capture = _capture(node_count=0)

    identity = build_snapshot_identity(capture)

    assert identity is not None
    assert identity.snapshot_hash.startswith("sha256:")


def test_snapshot_id_format_is_stable() -> None:
    identity = build_snapshot_identity(
        _capture(checked_at="2026-06-13T20:31:51.811108+00:00")
    )

    assert identity is not None
    assert identity.snapshot_id.startswith("snap_20260613T203151811108Z_")
    assert len(identity.snapshot_id.rsplit("_", maxsplit=1)[-1]) == 12
    assert identity.snapshot_hash.startswith("sha256:")
    assert len(identity.snapshot_hash) == 71


def test_operator_observation_identity_does_not_require_screenshot_ref() -> None:
    identity = build_operator_observation_identity(_observation(xml="<hierarchy />"))

    assert identity is not None
    assert identity.hash_version == OPERATOR_OBSERVATION_HASH_VERSION
    assert identity.snapshot_hash.startswith("sha256:")
    assert identity.snapshot_id.startswith("snap_")


def test_operator_observation_hash_changes_when_xml_changes() -> None:
    first = build_operator_observation_identity(_observation(xml="<hierarchy />"))
    second = build_operator_observation_identity(
        _observation(xml="<hierarchy><node /></hierarchy>")
    )

    assert first is not None
    assert second is not None
    assert first.snapshot_hash != second.snapshot_hash


def _capture(
    *,
    checked_at: str = "2026-06-13T20:31:51+00:00",
    ref_path_prefix: str = "a",
    xml_sha: str = "0" * 64,
    screenshot_sha: str = "1" * 64,
    node_count: int = 7,
) -> RawSnapshotCapture:
    return RawSnapshotCapture(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation="snapshot_capture",
        checked_at=checked_at,
        elapsed_ms=1.0,
        refs={
            "xml": SnapshotArtifactRef(
                path=f"{ref_path_prefix}/screen.xml",
                sha256=xml_sha,
                byte_length=123,
                metadata={"node_count": node_count},
            ),
            "screenshot": SnapshotArtifactRef(
                path=f"{ref_path_prefix}/screen.png",
                sha256=screenshot_sha,
                byte_length=456,
                metadata={"format": "png", "width": 1080, "height": 2400},
            ),
        },
    )


def _observation(
    *,
    xml: str,
    checked_at: str = "2026-06-13T20:31:51+00:00",
) -> RawSnapshotCapture:
    return RawSnapshotCapture(
        ok=True,
        status="completed",
        device_id="RFCN4010FCK",
        backend="fake",
        operation="operator_observation",
        checked_at=checked_at,
        elapsed_ms=1.0,
        xml=xml,
        normalization=SnapshotNormalization(
            schema_version="snapshot_elements.v1",
            status="completed",
            source_node_count=xml.count("<node"),
            element_count=0,
            visible_count=0,
            enabled_count=0,
            clickable_count=0,
            discarded_count=0,
            invalid_bounds_count=0,
            viewport_width=1080,
            viewport_height=2400,
        ),
    )
