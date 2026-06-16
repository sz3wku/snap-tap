from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from primitives_tap_helpers import fake_tap_snapshot

from snap_tap.evidence import write_primitive_receipt_evidence
from snap_tap.primitives.models import PrimitiveReceipt
from snap_tap.primitives.receipt import invalid_request_receipt
from snap_tap.snapshots import SnapshotArtifactRef


def test_receipt_evidence_marks_local_snapshot_refs_volatile(
    tmp_path: Path,
) -> None:
    snapshot = fake_tap_snapshot("snap-local")
    receipt = replace(
        _receipt(),
        status="partial",
        before_snapshot=snapshot,
        fresh_snapshot=snapshot,
        after_snapshot=snapshot,
        after_snapshot_status="completed",
        blocking_reason=None,
        error=None,
    )

    payload = _write_and_read(receipt, tmp_path)

    refs = payload["snapshot_proof_refs"]
    assert refs["schema_version"] == "primitive_snapshot_proof_refs.v1"
    for slot in ("before", "fresh", "after"):
        entry = refs[slot]
        assert entry["status"] == "volatile"
        assert entry["support_safe"] is False
        assert entry["reason"] == "snapshot_refs_not_evidence_root"
        assert entry["snapshot_id"] == "snap-local"
        assert "path" not in entry["refs"]["xml"]
        assert entry["refs"]["xml"]["sha256"] == "xml-sha"
        assert entry["refs"]["xml"]["byte_length"] == 123
        assert entry["refs"]["xml"]["metadata"] == {"node_count": 1}


def test_receipt_evidence_marks_evidence_root_snapshot_refs_durable(
    tmp_path: Path,
) -> None:
    snapshot = replace(
        fake_tap_snapshot("snap-durable"),
        refs={
            "xml": SnapshotArtifactRef(
                path=str(tmp_path / "runs" / "r1" / "screen.xml"),
                sha256="xml-sha",
                byte_length=123,
                metadata={"node_count": 7, "private": "ignored"},
            ),
            "screenshot": SnapshotArtifactRef(
                path=str(tmp_path / "runs" / "r1" / "screen.png"),
                sha256="png-sha",
                byte_length=456,
                metadata={"format": "png", "width": 1080, "height": 2400},
            ),
            "manifest": SnapshotArtifactRef(
                path="runs/r1/manifest.json",
                sha256="manifest-sha",
                byte_length=789,
                metadata={"schema_version": "snapshot_manifest.v1"},
            ),
        },
    )
    receipt = replace(
        _receipt(),
        before_snapshot=snapshot,
        fresh_snapshot=snapshot,
        after_snapshot=snapshot,
        after_snapshot_status="completed",
        blocking_reason=None,
        error=None,
    )

    payload = _write_and_read(receipt, tmp_path)

    entry = payload["snapshot_proof_refs"]["after"]
    assert entry["status"] == "durable"
    assert entry["support_safe"] is True
    assert entry["refs"]["xml"]["path"] == "runs/r1/screen.xml"
    assert entry["refs"]["screenshot"]["path"] == "runs/r1/screen.png"
    assert entry["refs"]["screenshot"]["metadata"] == {
        "format": "png",
        "height": 2400,
        "width": 1080,
    }
    assert entry["refs"]["manifest"]["path"] == "runs/r1/manifest.json"
    assert entry["refs"]["manifest"]["metadata"] == {
        "schema_version": "snapshot_manifest.v1"
    }
    files = [path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")]
    assert sorted(files) == [
        "runs",
        "runs/manual",
        "runs/manual/primitive_receipts",
        payload["_artifact_path"],
    ]


def test_receipt_evidence_rejects_absolute_ref_outside_known_namespace(
    tmp_path: Path,
) -> None:
    snapshot = replace(
        fake_tap_snapshot("snap-unsafe-namespace"),
        refs={
            "xml": SnapshotArtifactRef(
                path=str(tmp_path / "private" / "screen.xml"),
                sha256="xml-sha",
                byte_length=123,
                metadata={"node_count": 7},
            ),
        },
    )
    receipt = replace(
        _receipt(),
        after_snapshot=snapshot,
        after_snapshot_status="completed",
        blocking_reason=None,
        error=None,
    )

    payload = _write_and_read(receipt, tmp_path)

    entry = payload["snapshot_proof_refs"]["after"]
    assert entry["status"] == "volatile"
    assert entry["support_safe"] is False
    assert entry["reason"] == "snapshot_refs_not_evidence_root"
    assert "path" not in entry["refs"]["xml"]


def test_receipt_evidence_hides_path_without_integrity(
    tmp_path: Path,
) -> None:
    snapshot = replace(
        fake_tap_snapshot("snap-no-integrity"),
        refs={
            "xml": SnapshotArtifactRef(
                path=str(tmp_path / "runs" / "r1" / "screen.xml"),
                sha256="",
                byte_length=123,
                metadata={"node_count": 7},
            ),
            "screenshot": SnapshotArtifactRef(
                path=str(tmp_path / "runs" / "r1" / "screen.png"),
                sha256="png-sha",
                byte_length=-1,
                metadata={"format": "png", "width": 1080, "height": 2400},
            ),
        },
    )
    receipt = replace(
        _receipt(),
        after_snapshot=snapshot,
        after_snapshot_status="completed",
        blocking_reason=None,
        error=None,
    )

    payload = _write_and_read(receipt, tmp_path)

    entry = payload["snapshot_proof_refs"]["after"]
    assert entry["status"] == "volatile"
    assert entry["support_safe"] is False
    assert "path" not in entry["refs"]["xml"]
    assert "path" not in entry["refs"]["screenshot"]


def test_receipt_evidence_marks_not_attempted_states_explicitly(
    tmp_path: Path,
) -> None:
    payload = _write_and_read(_receipt(), tmp_path)

    refs = payload["snapshot_proof_refs"]
    assert refs["before"] == {
        "status": "not_attempted",
        "support_safe": False,
        "reason": "before_snapshot_not_attempted",
    }
    assert refs["fresh"] == {
        "status": "not_attempted",
        "support_safe": False,
        "reason": "fresh_snapshot_not_attempted",
    }
    assert refs["after"] == {
        "status": "not_attempted",
        "support_safe": False,
        "reason": "after_snapshot_not_attempted",
    }


def test_receipt_evidence_marks_expected_missing_snapshot_refs(
    tmp_path: Path,
) -> None:
    receipt = replace(
        _receipt(),
        operation="wait",
        status="partial",
        execution_status="completed",
        proof_status="failed",
        after_snapshot_required=True,
        after_snapshot_status="failed",
        blocking_reason=None,
    )

    payload = _write_and_read(receipt, tmp_path)

    refs = payload["snapshot_proof_refs"]
    assert refs["before"] == {
        "status": "missing",
        "support_safe": False,
        "reason": "before_snapshot_missing",
    }
    assert refs["fresh"] == {
        "status": "not_attempted",
        "support_safe": False,
        "reason": "fresh_snapshot_not_attempted",
    }
    assert refs["after"] == {
        "status": "missing",
        "support_safe": False,
        "reason": "after_snapshot_missing",
    }


def test_after_proof_failure_keeps_execution_truth_separate(
    tmp_path: Path,
) -> None:
    receipt = replace(
        _receipt(),
        status="partial",
        attempted_touch=True,
        touched_phone=True,
        execution_status="completed",
        proof_status="failed",
        after_snapshot_required=True,
        after_snapshot_status="failed",
        blocking_reason=None,
    )

    payload = _write_and_read(receipt, tmp_path)

    assert payload["attempted_touch"] is True
    assert payload["touched_phone"] is True
    assert payload["execution_status"] == "completed"
    assert payload["proof_status"] == "failed"
    assert payload["snapshot_proof_refs"]["after"]["status"] == "missing"


def _write_and_read(receipt: PrimitiveReceipt, tmp_path: Path) -> dict[str, Any]:
    ref = write_primitive_receipt_evidence(receipt, evidence_root=tmp_path)
    artifact = tmp_path / ref.path
    payload = cast(dict[str, Any], json.loads(artifact.read_text(encoding="utf-8")))
    payload["_artifact_path"] = ref.path
    return payload


def _receipt() -> PrimitiveReceipt:
    return invalid_request_receipt(
        device_id="RFCN4010FCK",
        request={"operation": "tap", "device_id": "RFCN4010FCK"},
        detail="blocked in unit test",
    )
