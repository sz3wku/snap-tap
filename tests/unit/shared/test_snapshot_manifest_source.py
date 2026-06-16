from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from snap_tap.snapshots import RawSnapshotCapture, materialize_raw_snapshot_artifacts
from snap_tap.snapshots.manifest_source import (
    SnapshotManifestSourceError,
    read_snapshot_manifest_source,
)
from snap_tap.targets import build_target_signature, mobile_snap_to_dict


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"
XML_TEXT = (
    '<hierarchy><node class="android.widget.Button" '
    'resource-id="com.example:id/save" package="com.example" '
    'bounds="[220,20][420,120]" visible-to-user="true" '
    'enabled="true" clickable="true" content-desc="Save" /></hierarchy>'
)


def test_manifest_source_reconstructs_sanitized_snap_and_targets(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path)

    source = read_snapshot_manifest_source(manifest)
    signature = build_target_signature(source.targets, "e001")
    encoded = json.dumps(mobile_snap_to_dict(source.snap, debug=True), sort_keys=True)

    assert source.snap.schema_version == "mobile_snap.v1"
    assert source.snap.device_id == "RFCN4010FCK"
    assert source.snap.targets[0].id == "e001"
    assert source.snap.targets[0].label is None
    assert set(source.targets.refs) == {"xml", "screenshot", "manifest"}
    assert signature.identity["resource_id"] == "com.example:id/save"
    assert signature.refs["manifest"].metadata == {
        "schema_version": "snapshot_manifest.v1",
    }
    assert "<hierarchy" not in encoded
    assert "content-desc" not in encoded
    assert "Save" not in encoded
    assert "base64" not in encoded


def test_manifest_source_accepts_capture_directory(tmp_path: Path) -> None:
    manifest = _capture_manifest(tmp_path)

    source = read_snapshot_manifest_source(manifest.parent)

    assert source.manifest_path == manifest
    assert source.capture_dir == manifest.parent


def test_manifest_source_fails_closed_on_device_mismatch(tmp_path: Path) -> None:
    manifest = _capture_manifest(tmp_path)

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(manifest, expected_device_id="OTHER")

    assert exc.value.code == "explicit_snapshot_source_device_mismatch"


def test_manifest_source_fails_closed_on_artifact_path_escape(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path)
    payload = _manifest_payload(manifest)
    payload["artifacts"]["xml"]["path"] = "../screen.xml"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(manifest)

    assert exc.value.code == "explicit_snapshot_source_invalid"


def test_manifest_source_fails_closed_on_artifact_hash_mismatch(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path)
    (manifest.parent / "screen.xml").write_text("<hierarchy />", encoding="utf-8")

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(manifest)

    assert exc.value.code == "explicit_snapshot_source_invalid"


def test_manifest_source_fails_closed_on_missing_artifact_ref(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path)
    payload = _manifest_payload(manifest)
    del payload["artifacts"]["xml"]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(manifest)

    assert exc.value.code == "explicit_snapshot_source_invalid"


def test_manifest_source_fails_closed_on_non_finite_number(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path)
    payload = _manifest_payload(manifest)
    payload["operation"]["elapsed_ms"] = float("nan")
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(manifest)

    assert exc.value.code == "explicit_snapshot_source_invalid"


def test_manifest_source_fails_closed_on_snapshot_identity_mismatch(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path)
    payload = _manifest_payload(manifest)
    payload["snapshot"]["snapshot_hash"] = "sha256:" + ("0" * 64)
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(manifest)

    assert exc.value.code == "explicit_snapshot_source_invalid"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("resource_id", "com.example:id/forged"),
        ("class_name", "android.widget.TextView"),
        ("package", "com.other"),
        ("clickable", False),
        ("enabled", False),
    ],
)
def test_manifest_source_fails_closed_on_element_fact_tamper(
    tmp_path: Path,
    field_name: str,
    value: object,
) -> None:
    manifest = _capture_manifest(tmp_path)
    payload = _manifest_payload(manifest)
    payload["elements"][0][field_name] = value
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(manifest)

    assert exc.value.code == "explicit_snapshot_source_invalid"


def test_manifest_source_fails_closed_on_element_bounds_tamper(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path)
    payload = _manifest_payload(manifest)
    payload["elements"][0]["bounds"]["center_x"] = 999.0
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(manifest)

    assert exc.value.code == "explicit_snapshot_source_invalid"


def test_manifest_source_fails_closed_on_normalization_tamper(
    tmp_path: Path,
) -> None:
    manifest = _capture_manifest(tmp_path)
    payload = _manifest_payload(manifest)
    payload["normalization"]["clickable_count"] = 0
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(manifest)

    assert exc.value.code == "explicit_snapshot_source_invalid"


def test_manifest_source_rejects_non_manifest_file_name(tmp_path: Path) -> None:
    manifest = _capture_manifest(tmp_path)
    renamed = manifest.with_name("source.json")
    renamed.write_text(manifest.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(SnapshotManifestSourceError) as exc:
        read_snapshot_manifest_source(renamed)

    assert exc.value.code == "explicit_snapshot_source_invalid"


def _capture_manifest(tmp_path: Path) -> Path:
    capture = materialize_raw_snapshot_artifacts(_raw_capture(), tmp_path)
    assert capture.ok is True
    return Path(capture.refs["manifest"].path)


def _raw_capture() -> RawSnapshotCapture:
    return RawSnapshotCapture.success(
        device_id="RFCN4010FCK",
        backend="fake",
        elapsed_ms=1.0,
        xml=XML_TEXT,
        image_bytes=PNG_BYTES,
        metadata={
            "screenshot_format": "png",
            "screenshot_width": 1080,
            "screenshot_height": 2400,
        },
    )


def _manifest_payload(manifest: Path) -> dict[str, Any]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload
