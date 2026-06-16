# snapshot_manifest.v1

Owner: `src/snap_tap/snapshots`

## Purpose

Describe one explicit raw snapshot capture directory as portable local evidence
metadata.

`snapshot_manifest.v1` is not a global evidence-store record, not a run record,
not a primitive receipt, and not a latest-snapshot cache. It exists so a
`snap-tap snapshot --out-dir` directory can be inspected or moved together with
its raw artifacts.

## Inputs

- `raw_snapshot_capture.v1` success output,
- `snapshot_identity.v1`,
- `snapshot_elements.v1` normalization output,
- local capture directory containing `screen.xml` and `screen.png`.

## Outputs

Each completed capture directory contains:

- `screen.xml`,
- `screen.png`,
- `manifest.json`.

The manifest has `schema_version` exactly `snapshot_manifest.v1` and records:

- snapshot identity: `snapshot_id`, `snapshot_hash`, `hash_version`,
- device id and backend,
- operation name, checked timestamp, and elapsed time,
- artifact refs for XML and screenshot,
- element normalization metadata,
- normalized structural elements,
- public metadata,
- recovery metadata when driver reads attempted bounded recovery.

Artifact paths inside the manifest are relative to the capture directory. The
CLI may return absolute paths for operator convenience, but the manifest must
remain portable.

## Privacy

Manifest/public JSON must not include:

- raw XML strings,
- image bytes,
- base64 payloads,
- `text`,
- `content-desc`,
- `hint`,
- arbitrary child-process stdout/stderr.

Structural elements may include bounds, visibility, enabled/clickable state,
and optional structural source facts already allowed by
`snapshot_elements.v1`: `class_name`, `resource_id`, and `package`.

## Invariants

- Manifest publication is all-or-cleanup with XML and screenshot artifacts.
- If manifest write or manifest hash calculation fails, the whole capture
  directory is removed best effort and the result fails as
  `snapshot_evidence_missing`.
- `snapshot_hash` remains `raw_snapshot_hash.v1`.
- `snapshot_hash` excludes artifact paths, output directory names, manifest
  path, manifest bytes, checked time, elapsed time, recovery metadata, and
  normalized elements.
- The manifest does not create semantic roles, target ids, target signatures,
  primitives, receipts, global evidence roots, support bundles, or latest
  caches.
- P1.R5.S6 may read an explicit `snapshot_manifest.v1` as a debug/repro source
  for `snap-tap snap --snapshot` and `snap-tap tap <serial> <eNN> --snapshot`. That source is
  still not executable. Mutating commands may use it only to rebuild
  `target_signature.v1`; execution must capture a fresh current snapshot,
  resolve `target_resolution.v1`, pass primitive stale guards, run through
  `snap_tap.primitives`, and emit `primitive_receipt.v1`.
- Explicit manifest readers must verify the manifest path or capture directory,
  schema/version, successful completed status, device identity, snapshot
  identity/hash, operation metadata, normalization, structural elements, and
  XML/screenshot artifact existence, byte length, and sha256.
- Explicit manifest readers must not trust manifest `elements` as source target
  facts by themselves. They must reconstruct or compare structural
  elements/normalization against the verified XML artifact and fail closed on
  mismatch before target signature construction or phone work.
- Manifest artifact refs are relative to the capture directory. Readers must
  fail closed on absolute refs, path escape, missing artifacts, byte-length
  mismatch, or sha mismatch.
- Explicit manifest replay must preserve manifest privacy. It must not expose
  raw XML, screenshot bytes, base64, `text`, `content-desc`, `hint`, platform
  semantics, model prompts, selectors, target resolution payloads, or primitive
  receipts.

## Failure Modes

- `snapshot_evidence_missing`
- `explicit_snapshot_source_missing`
- `explicit_snapshot_source_invalid`
- `explicit_snapshot_source_unsupported_version`
- `explicit_snapshot_source_device_mismatch`
