from __future__ import annotations

import json
from pathlib import Path

import pytest

import snap_tap.snapshots.artifacts as artifacts_module
from snap_tap.snapshots import RawSnapshotCapture, materialize_raw_snapshot_artifacts
from snap_tap.snapshots.manifest import SnapshotManifestError, build_snapshot_manifest

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"
XML_TEXT = (
    '<hierarchy><node class="android.widget.Button" '
    'resource-id="com.example:id/ok" package="com.example" '
    'bounds="[10,20][110,220]" visible-to-user="true" '
    'enabled="true" clickable="true" /></hierarchy>'
)


def test_materialize_raw_snapshot_artifacts_uses_unique_capture_dirs(
    tmp_path: Path,
) -> None:
    result = _raw_snapshot_capture()

    first = materialize_raw_snapshot_artifacts(result, tmp_path)
    second = materialize_raw_snapshot_artifacts(result, tmp_path)

    first_xml = Path(first.refs["xml"].path)
    second_xml = Path(second.refs["xml"].path)
    assert first.ok is True
    assert second.ok is True
    assert first_xml.parent != second_xml.parent
    assert first_xml.name == "screen.xml"
    assert Path(first.refs["screenshot"].path).name == "screen.png"
    assert Path(first.refs["manifest"].path).name == "manifest.json"
    assert Path(first.refs["manifest"].path).parent == first_xml.parent
    assert first_xml.read_text(encoding="utf-8") == XML_TEXT
    assert first.identity is not None
    assert second.identity is not None
    assert first.identity.snapshot_hash == second.identity.snapshot_hash
    assert first.elements[0].source_index == 0
    assert first.elements[0].visible is True
    assert first.normalization is not None
    assert first.normalization.element_count == 1


def test_materialize_raw_snapshot_artifacts_writes_manifest(
    tmp_path: Path,
) -> None:
    xml = (
        '<hierarchy><node class="android.widget.Button" '
        'resource-id="com.example:id/ok" package="com.example" '
        'bounds="[10,20][110,220]" visible-to-user="true" '
        'enabled="true" clickable="true" text="secret" '
        'content-desc="redacted" hint="private" /></hierarchy>'
    )

    result = materialize_raw_snapshot_artifacts(
        _raw_snapshot_capture(xml=xml),
        tmp_path,
    )

    assert result.ok is True
    assert result.identity is not None
    manifest_ref = result.refs["manifest"]
    assert manifest_ref.metadata["schema_version"] == "snapshot_manifest.v1"
    manifest_path = Path(manifest_ref.path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "snapshot_manifest.v1"
    assert manifest["snapshot"]["snapshot_id"] == result.identity.snapshot_id
    assert manifest["snapshot"]["snapshot_hash"] == result.identity.snapshot_hash
    assert manifest["snapshot"]["hash_version"] == "raw_snapshot_hash.v1"
    assert manifest["device"] == {
        "device_id": "RFCN4010FCK",
        "backend": "fake",
    }
    assert manifest["operation"]["name"] == "snapshot_capture"
    assert manifest["artifacts"]["xml"]["path"] == "screen.xml"
    assert manifest["artifacts"]["screenshot"]["path"] == "screen.png"
    assert manifest["artifacts"]["screenshot"]["format"] == "png"
    assert manifest["normalization"]["schema_version"] == "snapshot_elements.v1"
    assert manifest["normalization"]["element_count"] == 1
    assert manifest["elements"][0]["bounds"]["center_x"] == 60.0
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert "<hierarchy" not in manifest_text
    assert "image_bytes" not in manifest_text
    assert "image_base64" not in manifest_text
    assert "base64" not in manifest_text
    assert "secret" not in manifest_text
    assert "redacted" not in manifest_text
    assert "private" not in manifest_text
    assert "content-desc" not in manifest_text
    assert "hint" not in manifest_text


def test_snapshot_manifest_rejects_artifact_path_escape(tmp_path: Path) -> None:
    result = materialize_raw_snapshot_artifacts(_raw_snapshot_capture(), tmp_path)
    assert result.ok is True

    escaped = result.with_ref("xml", result.refs["screenshot"])

    with pytest.raises(SnapshotManifestError):
        build_snapshot_manifest(escaped, capture_dir=tmp_path / "elsewhere")


def test_materialize_raw_snapshot_artifacts_cleans_partial_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_screenshot(path: Path, payload: bytes) -> None:
        if path.name == "screen.png":
            raise OSError("disk full")
        path.write_bytes(payload)

    monkeypatch.setattr(artifacts_module, "_write_bytes_atomically", fail_screenshot)

    result = materialize_raw_snapshot_artifacts(_raw_snapshot_capture(), tmp_path)

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "snapshot_evidence_missing"
    assert list(tmp_path.iterdir()) == []


def test_materialize_raw_snapshot_artifacts_cleans_manifest_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_manifest(path: Path, payload: bytes) -> None:
        if path.name == "manifest.json":
            raise OSError("manifest blocked")
        path.write_bytes(payload)

    monkeypatch.setattr(artifacts_module, "_write_bytes_atomically", fail_manifest)

    result = materialize_raw_snapshot_artifacts(_raw_snapshot_capture(), tmp_path)

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "snapshot_evidence_missing"
    assert list(tmp_path.iterdir()) == []


def test_materialize_raw_snapshot_artifacts_maps_reservation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_reserve(parent: Path) -> Path:
        raise OSError(f"blocked: {parent}")

    monkeypatch.setattr(artifacts_module, "_reserve_artifact_dir", fail_reserve)

    result = materialize_raw_snapshot_artifacts(_raw_snapshot_capture(), tmp_path)

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "snapshot_evidence_missing"
    assert list(tmp_path.iterdir()) == []


def test_materialize_raw_snapshot_artifacts_cleans_when_identity_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(artifacts_module, "build_snapshot_identity", lambda result: None)

    result = materialize_raw_snapshot_artifacts(_raw_snapshot_capture(), tmp_path)

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "snapshot_evidence_missing"
    assert list(tmp_path.iterdir()) == []


def test_materialize_raw_snapshot_artifacts_cleans_when_normalization_fails(
    tmp_path: Path,
) -> None:
    result = materialize_raw_snapshot_artifacts(
        _raw_snapshot_capture(xml="<hierarchy><node /></hierarchy>"),
        tmp_path,
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "snapshot_empty"
    assert result.normalization is not None
    assert result.normalization.invalid_bounds_count == 1
    assert list(tmp_path.iterdir()) == []


def _raw_snapshot_capture(*, xml: str = XML_TEXT) -> RawSnapshotCapture:
    return RawSnapshotCapture.success(
        device_id="RFCN4010FCK",
        backend="fake",
        elapsed_ms=1.0,
        xml=xml,
        image_bytes=PNG_BYTES,
        metadata={
            "screenshot_format": "png",
            "screenshot_width": 1080,
            "screenshot_height": 2400,
        },
    )
