from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from snap_tap.evidence import (
    EvidenceWriteError,
    build_snapshot_proof_refs,
    evidence_artifact_ref_to_dict,
    primitive_receipt_relative_path,
    write_primitive_receipt_evidence,
)
from snap_tap.primitives.models import PrimitiveReceipt
from snap_tap.primitives.receipt import (
    invalid_request_receipt,
    primitive_receipt_to_dict,
)
from primitives_tap_helpers import fake_tap_snapshot


def test_write_primitive_receipt_evidence_writes_canonical_json(
    tmp_path: Path,
) -> None:
    receipt = _receipt()

    ref = write_primitive_receipt_evidence(
        receipt,
        evidence_root=tmp_path,
        created_at="2026-06-15T10:00:00+00:00",
        session_id="operator",
    )

    expected_payload = primitive_receipt_to_dict(receipt)
    expected_payload["snapshot_proof_refs"] = build_snapshot_proof_refs(
        receipt,
        evidence_root=tmp_path,
    )
    expected_bytes = _canonical_bytes(expected_payload)
    expected_path = primitive_receipt_relative_path(receipt.receipt_id)
    artifact_path = tmp_path / expected_path
    assert artifact_path.read_bytes() == expected_bytes
    assert ref.kind == "primitive_receipt.v1"
    assert ref.owner == "src/snap_tap/primitives"
    assert ref.path == expected_path.as_posix()
    assert ref.sha256 == hashlib.sha256(expected_bytes).hexdigest()
    assert ref.byte_length == len(expected_bytes)
    assert ref.created_at == "2026-06-15T10:00:00+00:00"
    assert ref.device_id == "RFCN4010FCK"
    assert ref.session_id == "operator"
    assert ref.redaction_class == "receipt_safe"
    assert evidence_artifact_ref_to_dict(ref)["schema_version"] == (
        "evidence_artifact.v1"
    )
    assert ref.path.startswith("runs/manual/primitive_receipts/")


@pytest.mark.parametrize("status", ["completed", "blocked", "failed", "partial"])
def test_write_primitive_receipt_evidence_accepts_receipt_statuses(
    tmp_path: Path,
    status: str,
) -> None:
    receipt = _receipt_with_status(status)

    ref = write_primitive_receipt_evidence(
        receipt,
        evidence_root=tmp_path,
        relative_path=Path("runs") / "manual" / "receipts" / f"{status}.json",
    )

    assert ref.path == f"runs/manual/receipts/{status}.json"
    assert (tmp_path / ref.path).exists()


def test_write_primitive_receipt_evidence_rejects_absolute_relative_path(
    tmp_path: Path,
) -> None:
    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(
            _receipt(),
            evidence_root=tmp_path,
            relative_path=tmp_path / "receipt.json",
        )

    assert exc.value.code == "evidence_artifact_forbidden_path"
    assert list(tmp_path.rglob("*")) == []


def test_write_primitive_receipt_evidence_rejects_traversal_path(
    tmp_path: Path,
) -> None:
    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(
            _receipt(),
            evidence_root=tmp_path,
            relative_path=Path("receipts") / ".." / "escape.json",
        )

    assert exc.value.code == "evidence_artifact_forbidden_path"
    assert list(tmp_path.rglob("*")) == []


def test_write_primitive_receipt_evidence_rejects_unknown_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(
            _receipt(),
            evidence_root=tmp_path,
            relative_path=Path("receipts") / "receipt.json",
        )

    assert exc.value.code == "evidence_artifact_forbidden_path"
    assert list(tmp_path.rglob("*")) == []


def test_write_primitive_receipt_evidence_rejects_malformed_default_filename_id(
    tmp_path: Path,
) -> None:
    receipt = replace(_receipt(), receipt_id="primitive_receipt:not-a-uuid")

    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(receipt, evidence_root=tmp_path)

    assert exc.value.code == "evidence_artifact_forbidden_path"
    assert list(tmp_path.rglob("*")) == []


def test_write_primitive_receipt_evidence_cleans_temp_on_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_replace(source: Path, target: Path) -> None:
        raise OSError(f"blocked: {source} -> {target}")

    monkeypatch.setattr("snap_tap.evidence.primitive_receipts.os.replace", fail_replace)

    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(_receipt(), evidence_root=tmp_path)

    assert exc.value.code == "evidence_artifact_write_failed"
    assert list(tmp_path.rglob("*.tmp")) == []
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_write_primitive_receipt_evidence_is_receipt_only(
    tmp_path: Path,
) -> None:
    snapshot = fake_tap_snapshot("snap-1")
    receipt = replace(
        _receipt(),
        before_snapshot=snapshot,
        fresh_snapshot=snapshot,
        after_snapshot=snapshot,
    )

    ref = write_primitive_receipt_evidence(receipt, evidence_root=tmp_path)

    files = [path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")]
    assert sorted(files) == [
        "runs",
        "runs/manual",
        "runs/manual/primitive_receipts",
        ref.path,
    ]
    artifact_text = (tmp_path / ref.path).read_text(encoding="utf-8")
    assert "<hierarchy" not in artifact_text
    assert "image_bytes" not in artifact_text
    assert "image_base64" not in artifact_text
    assert "base64" not in artifact_text
    assert not (tmp_path / "screen.xml").exists()
    assert not (tmp_path / "screen.png").exists()
    assert not (tmp_path / "manifest.json").exists()


def _receipt() -> PrimitiveReceipt:
    return invalid_request_receipt(
        device_id="RFCN4010FCK",
        request={"operation": "tap", "device_id": "RFCN4010FCK"},
        detail="blocked in unit test",
    )


def _receipt_with_status(status: str) -> PrimitiveReceipt:
    receipt = _receipt()
    if status == "completed":
        return replace(
            receipt,
            ok=True,
            status="completed",
            execution_status="completed",
            proof_status="not_requested",
            blocking_reason=None,
            error=None,
        )
    return replace(
        receipt,
        ok=False,
        status=status,
        execution_status=status,
        proof_status="not_requested",
    )


def _canonical_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, indent=2, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")
