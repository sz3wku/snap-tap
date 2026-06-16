from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from snap_tap.primitives.models import PrimitiveReceipt
from snap_tap.semantics import SemanticSnapshot
from snap_tap.snapshots import SnapshotArtifactRef


PRIMITIVE_SNAPSHOT_PROOF_REFS_SCHEMA_VERSION = "primitive_snapshot_proof_refs.v1"

SnapshotProofSlot = Literal["before", "fresh", "after"]
SnapshotProofStatus = Literal["durable", "volatile", "missing", "not_attempted"]

_ALLOWED_EVIDENCE_ROOTS = frozenset({"runs", "flows", "live", "support", "browser"})
_SAFE_METADATA_KEYS = frozenset(
    {"format", "height", "node_count", "schema_version", "width"}
)
_TARGETED_OPERATIONS = frozenset({"tap", "input", "replace_text"})
_PRETOUCH_NOT_ATTEMPTED_REASONS = frozenset(
    {"primitive_invalid_request", "primitive_lease_conflict"}
)


def build_snapshot_proof_refs(
    receipt: PrimitiveReceipt,
    *,
    evidence_root: Path,
) -> dict[str, object]:
    root = evidence_root.expanduser().resolve(strict=False)
    return {
        "schema_version": PRIMITIVE_SNAPSHOT_PROOF_REFS_SCHEMA_VERSION,
        "before": _snapshot_entry(
            slot="before",
            snapshot=receipt.before_snapshot,
            expected=_before_expected(receipt),
            evidence_root=root,
        ),
        "fresh": _snapshot_entry(
            slot="fresh",
            snapshot=receipt.fresh_snapshot,
            expected=_fresh_expected(receipt),
            evidence_root=root,
        ),
        "after": _snapshot_entry(
            slot="after",
            snapshot=receipt.after_snapshot,
            expected=_after_expected(receipt),
            evidence_root=root,
        ),
    }


def _snapshot_entry(
    *,
    slot: SnapshotProofSlot,
    snapshot: SemanticSnapshot | None,
    expected: bool,
    evidence_root: Path,
) -> dict[str, object]:
    if snapshot is None:
        status: SnapshotProofStatus = "missing" if expected else "not_attempted"
        return {
            "status": status,
            "support_safe": False,
            "reason": (
                f"{slot}_snapshot_missing"
                if expected
                else f"{slot}_snapshot_not_attempted"
            ),
        }

    entry: dict[str, object] = {
        "snapshot_id": snapshot.snapshot_id,
        "device_id": snapshot.device_id,
        "captured_at": snapshot.captured_at,
    }
    refs, all_refs_durable = _artifact_refs(snapshot.refs, evidence_root=evidence_root)
    if not refs:
        entry.update(
            {
                "status": "missing",
                "support_safe": False,
                "reason": "snapshot_artifact_refs_missing",
            }
        )
        return entry
    if all_refs_durable:
        entry.update({"status": "durable", "support_safe": True, "refs": refs})
        return entry
    entry.update(
        {
            "status": "volatile",
            "support_safe": False,
            "refs": refs,
            "reason": "snapshot_refs_not_evidence_root",
        }
    )
    return entry


def _artifact_refs(
    refs: Mapping[str, SnapshotArtifactRef],
    *,
    evidence_root: Path,
) -> tuple[dict[str, object], bool]:
    payload: dict[str, object] = {}
    all_refs_durable = True
    for name in ("xml", "screenshot", "manifest"):
        ref = refs.get(name)
        if ref is None:
            continue
        artifact, durable = _artifact_ref(ref, evidence_root=evidence_root)
        payload[name] = artifact
        all_refs_durable = all_refs_durable and durable
    return payload, all_refs_durable


def _artifact_ref(
    ref: SnapshotArtifactRef,
    *,
    evidence_root: Path,
) -> tuple[dict[str, object], bool]:
    path = _durable_path(ref.path, evidence_root=evidence_root)
    has_integrity = bool(ref.sha256) and ref.byte_length >= 0
    payload: dict[str, object] = {
        "sha256": ref.sha256,
        "byte_length": ref.byte_length,
    }
    if path is not None and has_integrity:
        payload["path"] = path
    metadata = _safe_metadata(ref.metadata)
    if metadata:
        payload["metadata"] = metadata
    return payload, path is not None and has_integrity


def _durable_path(raw_path: str, *, evidence_root: Path) -> str | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        resolved = path.expanduser().resolve(strict=False)
        try:
            relative = resolved.relative_to(evidence_root)
        except ValueError:
            return None
        return _allowed_relative_path(relative)
    return _allowed_relative_path(path)


def _allowed_relative_path(path: Path) -> str | None:
    if any(part in {"", ".", ".."} for part in path.parts):
        return None
    if not path.parts or path.parts[0] not in _ALLOWED_EVIDENCE_ROOTS:
        return None
    return path.as_posix()


def _safe_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in metadata.items():
        if key not in _SAFE_METADATA_KEYS:
            continue
        if key in {"height", "node_count", "width"}:
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                safe[key] = value
            continue
        if isinstance(value, str):
            safe[key] = value
    return safe


def _before_expected(receipt: PrimitiveReceipt) -> bool:
    if receipt.before_snapshot is not None:
        return True
    if _blocking_code(receipt) in _PRETOUCH_NOT_ATTEMPTED_REASONS:
        return False
    return receipt.operation in {"swipe", "wait"}


def _fresh_expected(receipt: PrimitiveReceipt) -> bool:
    if receipt.fresh_snapshot is not None:
        return True
    if receipt.operation not in _TARGETED_OPERATIONS:
        return False
    if _blocking_code(receipt) in _PRETOUCH_NOT_ATTEMPTED_REASONS:
        return False
    return True


def _after_expected(receipt: PrimitiveReceipt) -> bool:
    if receipt.after_snapshot is not None:
        return True
    if receipt.after_snapshot_status == "not_attempted":
        return False
    if receipt.after_snapshot_required:
        return True
    if receipt.attempted_touch or receipt.touched_phone:
        return True
    return receipt.proof_status not in {"not_requested", "not_attempted"}


def _blocking_code(receipt: PrimitiveReceipt) -> str | None:
    if receipt.blocking_reason is None:
        return None
    code = receipt.blocking_reason.get("code")
    if isinstance(code, str):
        return code
    return None
