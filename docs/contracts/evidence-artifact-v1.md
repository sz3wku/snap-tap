# evidence_artifact.v1

Owner: `src/snap_tap/evidence` and domain evidence writers

## Purpose

Describe one durable evidence artifact written under top-level `data/evidence`.

Artifacts can be JSON, screenshots, XML dumps, primitive receipts, replay proof,
run timelines, support manifests, or other runtime proof files.

Primitive receipt JSON artifacts may include
`snapshot_proof_refs` with before/fresh/after snapshot ref classifications.
That field classifies refs already present in the receipt; it does not copy or
retain screenshot, XML, or manifest artifacts.

## Inputs

- owning domain,
- artifact kind,
- local path under `data/evidence`,
- payload or file bytes,
- related run/flow/job/device/session ids,
- redaction classification,
- creation timestamp.

## Outputs

An artifact ref contains:

- `schema_version`: exactly `evidence_artifact.v1`,
- `artifact_id`,
- `kind`,
- `owner`,
- `path`,
- `sha256`,
- `byte_length`,
- `created_at`,
- optional `run_id`,
- optional `flow_id`,
- optional `device_id`,
- optional `session_id`,
- `redaction_class`.

## Invariants

- Artifact paths live under `data/evidence`.
- Artifacts are referenced by path and hash.
- Artifact refs record byte length so support code can verify local files
  without trusting filenames.
- Snapshot refs are support-safe only when they point under the evidence root
  and carry integrity metadata. Local/temp snapshot refs must be classified as
  volatile rather than durable.
- Runtime code writes through evidence/store interfaces, not ad hoc paths.
- Apps do not own evidence storage.
- Missing artifacts must be reported as structured evidence errors.
- Sensitive raw data must be classified before support export.

## Namespaces

Expected roots:

- `data/evidence/runs`,
- `data/evidence/flows`,
- `data/evidence/live`,
- `data/evidence/support`,
- `data/evidence/browser`.

## Failure Modes

- `evidence_artifact_missing`
- `evidence_artifact_hash_mismatch`
- `evidence_artifact_write_failed`
- `evidence_artifact_forbidden_path`
- `evidence_artifact_redaction_required`
