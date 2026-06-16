from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from snap_tap.evidence import (
    EvidenceWriteError,
    write_primitive_receipt_evidence,
)
from snap_tap.primitives.models import PrimitiveReceipt
from snap_tap.primitives.receipt import invalid_request_receipt


def test_write_primitive_receipt_evidence_rejects_forbidden_raw_fields(
    tmp_path: Path,
) -> None:
    receipt = replace(
        _receipt(),
        request={"operation": "input", "text": "private operator text"},
    )

    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(
            receipt,
            evidence_root=tmp_path,
            relative_path="receipt.json",
        )

    assert exc.value.code == "evidence_artifact_redaction_required"
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize(
    "value",
    [
        "<hierarchy><node text='private' /></hierarchy>",
        "iVBORw0KGgoAAAANSUhEUgAA",
        "css selector .private-input",
        "model prompt: choose the next action",
        "private token=abc123",
    ],
)
def test_write_primitive_receipt_evidence_rejects_forbidden_raw_values(
    tmp_path: Path,
    value: str,
) -> None:
    receipt = replace(
        _receipt(),
        request={"operation": "tap", "debug": value},
    )

    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(
            receipt,
            evidence_root=tmp_path,
            relative_path="runs/manual/receipt.json",
        )

    assert exc.value.code == "evidence_artifact_redaction_required"
    assert list(tmp_path.rglob("*")) == []


def test_write_primitive_receipt_evidence_rejects_raw_detail_values(
    tmp_path: Path,
) -> None:
    receipt = invalid_request_receipt(
        device_id="RFCN4010FCK",
        request={"operation": "tap"},
        detail="<hierarchy><node /></hierarchy>",
    )

    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(receipt, evidence_root=tmp_path)

    assert exc.value.code == "evidence_artifact_redaction_required"
    assert list(tmp_path.rglob("*")) == []


def test_write_primitive_receipt_evidence_rejects_unsafe_ref_metadata(
    tmp_path: Path,
) -> None:
    receipt = replace(
        _receipt(),
        request={"operation": "tap", "session_id": "../private"},
    )

    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(receipt, evidence_root=tmp_path)

    assert exc.value.code == "evidence_artifact_redaction_required"
    assert list(tmp_path.rglob("*")) == []


def test_write_primitive_receipt_evidence_rejects_unsafe_redaction_class(
    tmp_path: Path,
) -> None:
    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(
            _receipt(),
            evidence_root=tmp_path,
            redaction_class="operator text",
        )

    assert exc.value.code == "evidence_artifact_redaction_required"
    assert list(tmp_path.rglob("*")) == []


def test_write_primitive_receipt_evidence_rejects_non_string_redaction_class(
    tmp_path: Path,
) -> None:
    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(
            _receipt(),
            evidence_root=tmp_path,
            redaction_class=cast(str, None),
        )

    assert exc.value.code == "evidence_artifact_redaction_required"
    assert list(tmp_path.rglob("*")) == []


def test_write_primitive_receipt_evidence_rejects_unsafe_created_at(
    tmp_path: Path,
) -> None:
    with pytest.raises(EvidenceWriteError) as exc:
        write_primitive_receipt_evidence(
            _receipt(),
            evidence_root=tmp_path,
            created_at="token=secret",
        )

    assert exc.value.code == "evidence_artifact_redaction_required"
    assert list(tmp_path.rglob("*")) == []


def _receipt() -> PrimitiveReceipt:
    return invalid_request_receipt(
        device_id="RFCN4010FCK",
        request={"operation": "tap", "device_id": "RFCN4010FCK"},
        detail="blocked in unit test",
    )
