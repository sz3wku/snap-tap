from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from snap_tap.evidence.models import (
    DEFAULT_REDACTION_CLASS,
    EVIDENCE_ARTIFACT_SCHEMA_VERSION,
    EvidenceArtifactRef,
    EvidenceWriteError,
)
from snap_tap.evidence.snapshot_proof_refs import build_snapshot_proof_refs
from snap_tap.primitives.models import (
    PRIMITIVE_RECEIPT_SCHEMA_VERSION,
    PrimitiveReceipt,
)
from snap_tap.primitives.receipt import primitive_receipt_to_dict

PRIMITIVE_RECEIPT_ARTIFACT_KIND = PRIMITIVE_RECEIPT_SCHEMA_VERSION
PRIMITIVE_RECEIPT_ARTIFACT_OWNER = "src/snap_tap/primitives"
DEFAULT_PRIMITIVE_RECEIPT_DIR = Path("runs") / "manual" / "primitive_receipts"

_ALLOWED_RECEIPT_STATUSES = frozenset({"completed", "blocked", "failed", "partial"})
_RECEIPT_ID_RE = re.compile(
    r"^primitive_receipt:"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}$"
)
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "base64",
        "image_base64",
        "image_bytes",
        "lease_id",
        "lease_token",
        "model_prompt",
        "private_lease_token",
        "prompt",
        "raw_text",
        "raw_xml",
        "screenshot_base64",
        "screenshot_bytes",
        "selector",
        "selectors",
        "text",
        "xml_text",
    }
)
_ALLOWED_EVIDENCE_ROOTS = frozenset({"runs", "flows", "live", "support", "browser"})
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SAFE_REDACTION_CLASS_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SAFE_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_SENSITIVE_VALUE_MARKERS = tuple(
    marker.lower()
    for marker in (
        "<hierarchy",
        "</hierarchy",
        "<?xml",
        "<node",
        "content-desc=",
        "resource-id=",
        "bounds=",
        "data:image",
        "ivborw0kggo",
        "image_base64",
        "image bytes",
        "screenshot bytes",
        "screenshot_base64",
        "raw xml",
        "raw text",
        "operator text",
        "model prompt",
        "system prompt",
        "user prompt",
        "css selector",
        "xpath",
        "selector=",
        "selectors=",
        "lease token",
        "private token",
        "bearer ",
        "token=",
        "password=",
        "secret=",
    )
)


def write_primitive_receipt_evidence(
    receipt: PrimitiveReceipt,
    *,
    evidence_root: Path,
    relative_path: str | Path | None = None,
    created_at: str | None = None,
    redaction_class: str = DEFAULT_REDACTION_CLASS,
    run_id: str | None = None,
    flow_id: str | None = None,
    session_id: str | None = None,
) -> EvidenceArtifactRef:
    payload = primitive_receipt_to_dict(receipt)
    payload["snapshot_proof_refs"] = build_snapshot_proof_refs(
        receipt,
        evidence_root=evidence_root,
    )
    _validate_receipt_payload(payload)
    content = encode_primitive_receipt_payload(payload)
    rel_path = (
        primitive_receipt_relative_path(receipt.receipt_id)
        if relative_path is None
        else _validated_relative_path(relative_path)
    )
    target_path = _target_path(evidence_root=evidence_root, relative_path=rel_path)
    safe_redaction_class = _normalized_redaction_class(redaction_class)
    safe_run_id = _optional_contract_id(run_id, "run_id")
    safe_flow_id = _optional_contract_id(flow_id, "flow_id")
    safe_device_id = _optional_contract_id(receipt.device_id, "device_id")
    safe_session_id = _optional_contract_id(session_id, "session_id")
    if safe_session_id is None:
        safe_session_id = _optional_contract_id(
            receipt.request.get("session_id"),
            "session_id",
        )
    artifact_created_at = _normalized_created_at(created_at)

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        _write_bytes_atomically(target_path, content)
    except OSError as exc:
        raise EvidenceWriteError(
            code="evidence_artifact_write_failed",
            detail="Failed to write primitive receipt evidence.",
        ) from exc

    digest = hashlib.sha256(content).hexdigest()
    return EvidenceArtifactRef(
        schema_version=EVIDENCE_ARTIFACT_SCHEMA_VERSION,
        artifact_id=f"evidence_artifact:{digest}",
        kind=PRIMITIVE_RECEIPT_ARTIFACT_KIND,
        owner=PRIMITIVE_RECEIPT_ARTIFACT_OWNER,
        path=rel_path.as_posix(),
        sha256=digest,
        byte_length=len(content),
        created_at=artifact_created_at,
        redaction_class=safe_redaction_class,
        run_id=safe_run_id,
        flow_id=safe_flow_id,
        device_id=safe_device_id,
        session_id=safe_session_id,
    )


def encode_primitive_receipt_payload(payload: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def primitive_receipt_relative_path(receipt_id: str) -> Path:
    match = _RECEIPT_ID_RE.fullmatch(receipt_id)
    if match is None:
        raise EvidenceWriteError(
            code="evidence_artifact_forbidden_path",
            detail="Malformed primitive receipt id cannot be used as filename.",
        )
    receipt_uuid = receipt_id.removeprefix("primitive_receipt:")
    return DEFAULT_PRIMITIVE_RECEIPT_DIR / f"{receipt_uuid}.json"


def _validate_receipt_payload(payload: Mapping[str, object]) -> None:
    if payload.get("schema_version") != PRIMITIVE_RECEIPT_SCHEMA_VERSION:
        raise EvidenceWriteError(
            code="evidence_artifact_write_failed",
            detail="Primitive receipt evidence requires primitive_receipt.v1 payload.",
        )
    if payload.get("status") not in _ALLOWED_RECEIPT_STATUSES:
        raise EvidenceWriteError(
            code="evidence_artifact_write_failed",
            detail="Primitive receipt evidence has unsupported status.",
        )
    _reject_forbidden_payload_keys(payload)


def _reject_forbidden_payload_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key in _FORBIDDEN_PAYLOAD_KEYS:
                raise EvidenceWriteError(
                    code="evidence_artifact_redaction_required",
                    detail="Primitive receipt evidence contains forbidden raw fields.",
                )
            _reject_forbidden_payload_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_payload_keys(child)
    elif isinstance(value, str):
        _reject_forbidden_string_value(value)


def _reject_forbidden_string_value(value: str) -> None:
    normalized = value.lower()
    if any(marker in normalized for marker in _SENSITIVE_VALUE_MARKERS):
        raise EvidenceWriteError(
            code="evidence_artifact_redaction_required",
            detail="Primitive receipt evidence contains forbidden raw values.",
        )


def _target_path(*, evidence_root: Path, relative_path: Path) -> Path:
    root = evidence_root.expanduser().resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise EvidenceWriteError(
            code="evidence_artifact_forbidden_path",
            detail="Evidence artifact path escaped evidence root.",
        )
    return candidate


def _validated_relative_path(value: str | Path) -> Path:
    path = Path(value)
    if path.drive or path.root or path.is_absolute():
        raise EvidenceWriteError(
            code="evidence_artifact_forbidden_path",
            detail="Evidence artifact path must be relative.",
        )
    if not path.parts:
        raise EvidenceWriteError(
            code="evidence_artifact_forbidden_path",
            detail="Evidence artifact path must not be empty.",
        )
    if any(part in {"", ".", ".."} for part in path.parts):
        raise EvidenceWriteError(
            code="evidence_artifact_forbidden_path",
            detail="Evidence artifact path must not contain traversal segments.",
        )
    if path.parts[0] not in _ALLOWED_EVIDENCE_ROOTS:
        raise EvidenceWriteError(
            code="evidence_artifact_forbidden_path",
            detail="Evidence artifact path must use a known evidence namespace.",
        )
    return path


def _write_bytes_atomically(path: Path, payload: bytes) -> None:
    temp_path = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        temp_path.write_bytes(payload)
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _optional_contract_id(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise EvidenceWriteError(
            code="evidence_artifact_redaction_required",
            detail=f"{field_name} must be a safe public identifier.",
        )
    _reject_forbidden_string_value(value)
    if _SAFE_ID_RE.fullmatch(value) is None:
        raise EvidenceWriteError(
            code="evidence_artifact_redaction_required",
            detail=f"{field_name} must be a safe public identifier.",
        )
    return value


def _normalized_redaction_class(value: object) -> str:
    if not isinstance(value, str):
        raise EvidenceWriteError(
            code="evidence_artifact_redaction_required",
            detail="redaction_class must be a safe public label.",
        )
    _reject_forbidden_string_value(value)
    if _SAFE_REDACTION_CLASS_RE.fullmatch(value) is None:
        raise EvidenceWriteError(
            code="evidence_artifact_redaction_required",
            detail="redaction_class must be a safe public label.",
        )
    return value


def _normalized_created_at(value: object) -> str:
    if value is None:
        return _utc_now()
    if not isinstance(value, str):
        raise EvidenceWriteError(
            code="evidence_artifact_redaction_required",
            detail="created_at must be a safe timestamp.",
        )
    _reject_forbidden_string_value(value)
    if _SAFE_TIMESTAMP_RE.fullmatch(value) is None:
        raise EvidenceWriteError(
            code="evidence_artifact_redaction_required",
            detail="created_at must be a safe timestamp.",
        )
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
