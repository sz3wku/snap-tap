from __future__ import annotations

from dataclasses import dataclass

EVIDENCE_ARTIFACT_SCHEMA_VERSION = "evidence_artifact.v1"
DEFAULT_REDACTION_CLASS = "receipt_safe"


@dataclass(frozen=True)
class EvidenceArtifactRef:
    schema_version: str
    artifact_id: str
    kind: str
    owner: str
    path: str
    sha256: str
    byte_length: int
    created_at: str
    redaction_class: str
    run_id: str | None = None
    flow_id: str | None = None
    device_id: str | None = None
    session_id: str | None = None


class EvidenceWriteError(Exception):
    def __init__(self, *, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def evidence_artifact_ref_to_dict(ref: EvidenceArtifactRef) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": ref.schema_version,
        "artifact_id": ref.artifact_id,
        "kind": ref.kind,
        "owner": ref.owner,
        "path": ref.path,
        "sha256": ref.sha256,
        "byte_length": ref.byte_length,
        "created_at": ref.created_at,
        "redaction_class": ref.redaction_class,
    }
    if ref.run_id is not None:
        payload["run_id"] = ref.run_id
    if ref.flow_id is not None:
        payload["flow_id"] = ref.flow_id
    if ref.device_id is not None:
        payload["device_id"] = ref.device_id
    if ref.session_id is not None:
        payload["session_id"] = ref.session_id
    return payload
