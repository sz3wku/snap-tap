from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from snap_tap.snapshots import (
    LatestSnapshotRefError,
    RawSnapshotCapture,
    SnapshotArtifactRef,
    SnapshotIdentity,
    build_latest_snapshot_ref,
    latest_snapshot_ref_path,
    latest_snapshot_ref_to_dict,
    read_latest_snapshot_ref,
    write_latest_snapshot_ref,
)

FORBIDDEN_SENTINELS = (
    "<hierarchy>DO_NOT_LEAK_XML</hierarchy>",
    "DO_NOT_LEAK_IMAGE_BYTES",
    "DO_NOT_LEAK_BASE64",
    "target-signature-secret",
    "resolution-secret",
    "receipt-secret",
    "selector-secret",
    "coordinate-click-secret",
    "model-prompt-secret",
)


def test_build_latest_ref_from_materialized_raw_snapshot_capture() -> None:
    latest = build_latest_snapshot_ref(_capture(), session_id="default")
    payload = latest_snapshot_ref_to_dict(latest)

    assert payload["schema_version"] == "latest_snapshot_ref.v1"
    assert payload["device_id"] == "RFCN4010FCK"
    assert payload["session_id"] == "default"
    assert payload["snapshot"] == {
        "snapshot_id": "snap_20260614T120000Z_abcdef123456",
        "snapshot_hash": "sha256:" + "a" * 64,
        "hash_version": "raw_snapshot_hash.v1",
        "checked_at": "2026-06-14T12:00:00+00:00",
        "backend": "fake",
        "operation": "snapshot_capture",
    }
    refs = cast(dict[str, dict[str, object]], payload["refs"])
    assert set(refs) == {"xml", "screenshot", "manifest"}
    assert refs["xml"]["node_count"] == 1
    assert refs["screenshot"]["format"] == "png"
    assert refs["manifest"]["metadata"] == {
        "schema_version": "snapshot_manifest.v1"
    }


def test_reject_capture_without_identity_or_required_refs() -> None:
    with pytest.raises(LatestSnapshotRefError) as missing_identity:
        build_latest_snapshot_ref(replace(_capture(), identity=None))

    without_manifest = replace(
        _capture(),
        refs={name: ref for name, ref in _capture().refs.items() if name != "manifest"},
    )
    with pytest.raises(LatestSnapshotRefError) as missing_ref:
        build_latest_snapshot_ref(without_manifest)

    assert missing_identity.value.code == "latest_snapshot_ref_invalid"
    assert missing_ref.value.code == "latest_snapshot_invalid"


def test_write_read_round_trip(tmp_path: Path) -> None:
    written = write_latest_snapshot_ref(
        build_latest_snapshot_ref(_capture(), cache_root=tmp_path),
        cache_root=tmp_path,
    )

    read_back = read_latest_snapshot_ref(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )

    assert read_back == written
    assert Path(str(written.cache["path"])).exists()


def test_missing_latest_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(LatestSnapshotRefError) as exc_info:
        read_latest_snapshot_ref(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    assert exc_info.value.code == "latest_snapshot_missing"


def test_corrupt_json_fails_closed(tmp_path: Path) -> None:
    path = latest_snapshot_ref_path(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(LatestSnapshotRefError) as exc_info:
        read_latest_snapshot_ref(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    assert exc_info.value.code == "latest_snapshot_invalid"


def test_unsupported_version_fails_structured(tmp_path: Path) -> None:
    latest = build_latest_snapshot_ref(_capture(), cache_root=tmp_path)
    payload = latest_snapshot_ref_to_dict(latest)
    payload["schema_version"] = "latest_snapshot_ref.v2"
    _write_payload_for("RFCN4010FCK", "default", payload, tmp_path)

    with pytest.raises(LatestSnapshotRefError) as exc_info:
        read_latest_snapshot_ref(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    assert exc_info.value.code == "latest_snapshot_unsupported_version"


def test_cache_key_mismatch_fails_closed(tmp_path: Path) -> None:
    latest = build_latest_snapshot_ref(_capture(), cache_root=tmp_path)
    payload = latest_snapshot_ref_to_dict(latest)
    cache = cast(dict[str, object], payload["cache"])
    cache["key"] = "sha256-" + "0" * 64
    _write_payload_for("RFCN4010FCK", "default", payload, tmp_path)

    with pytest.raises(LatestSnapshotRefError) as exc_info:
        read_latest_snapshot_ref(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    assert exc_info.value.code == "latest_snapshot_invalid"


def test_cache_path_mismatch_fails_closed(tmp_path: Path) -> None:
    latest = build_latest_snapshot_ref(_capture(), cache_root=tmp_path)
    payload = latest_snapshot_ref_to_dict(latest)
    cache = cast(dict[str, object], payload["cache"])
    cache["path"] = "DO_NOT_LEAK_BASE64"
    _write_payload_for("RFCN4010FCK", "default", payload, tmp_path)

    with pytest.raises(LatestSnapshotRefError) as exc_info:
        read_latest_snapshot_ref(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    assert exc_info.value.code == "latest_snapshot_invalid"


def test_non_normalized_public_text_fails_closed(tmp_path: Path) -> None:
    latest = build_latest_snapshot_ref(_capture(), cache_root=tmp_path)
    payload = latest_snapshot_ref_to_dict(latest)
    snapshot = cast(dict[str, object], payload["snapshot"])
    snapshot["snapshot_id"] = " " + str(snapshot["snapshot_id"])
    _write_payload_for("RFCN4010FCK", "default", payload, tmp_path)

    with pytest.raises(LatestSnapshotRefError) as exc_info:
        read_latest_snapshot_ref(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    assert exc_info.value.code == "latest_snapshot_invalid"


def test_device_and_session_mismatch_fail_structured(tmp_path: Path) -> None:
    payload = latest_snapshot_ref_to_dict(
        build_latest_snapshot_ref(_capture(device_id="OTHER"), cache_root=tmp_path)
    )
    _write_payload_for("RFCN4010FCK", "default", payload, tmp_path)

    with pytest.raises(LatestSnapshotRefError) as device_exc:
        read_latest_snapshot_ref(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    payload = latest_snapshot_ref_to_dict(
        build_latest_snapshot_ref(_capture(), session_id="other", cache_root=tmp_path)
    )
    _write_payload_for("RFCN4010FCK", "default", payload, tmp_path)

    with pytest.raises(LatestSnapshotRefError) as session_exc:
        read_latest_snapshot_ref(
            device_id="RFCN4010FCK",
            session_id="default",
            cache_root=tmp_path,
        )

    assert device_exc.value.code == "latest_snapshot_device_mismatch"
    assert session_exc.value.code == "latest_snapshot_session_mismatch"


def test_separate_sessions_do_not_collide(tmp_path: Path) -> None:
    default = write_latest_snapshot_ref(
        build_latest_snapshot_ref(_capture(), session_id="default", cache_root=tmp_path),
        cache_root=tmp_path,
    )
    custom = write_latest_snapshot_ref(
        build_latest_snapshot_ref(_capture(), session_id="custom", cache_root=tmp_path),
        cache_root=tmp_path,
    )

    assert default.cache["path"] != custom.cache["path"]
    assert read_latest_snapshot_ref(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    ).session_id == "default"
    assert read_latest_snapshot_ref(
        device_id="RFCN4010FCK",
        session_id="custom",
        cache_root=tmp_path,
    ).session_id == "custom"


def test_public_payload_excludes_private_surface(tmp_path: Path) -> None:
    latest = write_latest_snapshot_ref(
        build_latest_snapshot_ref(_capture(), cache_root=tmp_path),
        cache_root=tmp_path,
    )
    payload = latest_snapshot_ref_to_dict(latest)
    encoded = json.dumps(payload, sort_keys=True)

    assert set(payload) == {
        "schema_version",
        "device_id",
        "session_id",
        "updated_at",
        "snapshot",
        "refs",
        "cache",
    }
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in encoded


def _write_payload_for(
    device_id: str,
    session_id: str,
    payload: dict[str, object],
    root: Path,
) -> None:
    path = latest_snapshot_ref_path(
        device_id=device_id,
        session_id=session_id,
        cache_root=root,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _capture(device_id: str = "RFCN4010FCK") -> RawSnapshotCapture:
    return RawSnapshotCapture(
        ok=True,
        status="completed",
        device_id=device_id,
        backend="fake",
        operation="snapshot_capture",
        checked_at="2026-06-14T12:00:00+00:00",
        elapsed_ms=1.0,
        identity=SnapshotIdentity(
            snapshot_id="snap_20260614T120000Z_abcdef123456",
            snapshot_hash="sha256:" + "a" * 64,
            hash_version="raw_snapshot_hash.v1",
        ),
        refs={
            "xml": SnapshotArtifactRef(
                path="screen.xml",
                sha256="x" * 64,
                byte_length=123,
                metadata={"node_count": 1, "raw_xml": FORBIDDEN_SENTINELS[0]},
            ),
            "screenshot": SnapshotArtifactRef(
                path="screen.png",
                sha256="y" * 64,
                byte_length=456,
                metadata={
                    "format": "png",
                    "width": 1080,
                    "height": 2400,
                    "image_bytes": FORBIDDEN_SENTINELS[1],
                    "base64": FORBIDDEN_SENTINELS[2],
                },
            ),
            "manifest": SnapshotArtifactRef(
                path="manifest.json",
                sha256="z" * 64,
                byte_length=789,
                metadata={
                    "schema_version": "snapshot_manifest.v1",
                    "target_signature": FORBIDDEN_SENTINELS[3],
                    "target_resolution": FORBIDDEN_SENTINELS[4],
                    "primitive_receipt": FORBIDDEN_SENTINELS[5],
                    "selector": FORBIDDEN_SENTINELS[6],
                    "coordinate_click": FORBIDDEN_SENTINELS[7],
                    "model_prompt": FORBIDDEN_SENTINELS[8],
                },
            ),
        },
    )
