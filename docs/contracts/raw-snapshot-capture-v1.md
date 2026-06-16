# raw_snapshot_capture.v1

Owner: `src/snap_tap/snapshots`

## Purpose

Represent one read-only phone observation as raw, recoverable artifact refs.

This is the first bridge between `driver_backend.v1` raw reads and later
`semantic_snapshot.v1`. It includes deterministic structural element facts via
`snapshot_elements.v1`, but it is not semantic normalization, not target
identity, not a primitive receipt, and not an evidence store.

## Inputs

- visible Android devices,
- explicit `device_id`,
- `driver_backend.v1` XML hierarchy dump,
- `driver_backend.v1` screenshot capture,
- explicit output directory when exposed through CLI,
- capture timeout.

## Outputs

`raw_snapshot_capture.v1` returns:

- `ok`,
- `status`,
- `device_id`,
- `backend`,
- `operation`: `snapshot_capture`,
- `snapshot_id`,
- `snapshot_hash`,
- `hash_version`,
- `checked_at`,
- `elapsed_ms`,
- raw artifact refs,
- local manifest ref when artifacts are materialized,
- normalized structural elements,
- element normalization metadata,
- metadata,
- recovery metadata when underlying driver reads attempted bounded recovery,
- structured error.

Artifact refs are keyed by artifact kind:

```json
{
  "xml": {
    "path": "temp/mobile-smoke/p1-r2-s1-main/capture-.../screen.xml",
    "sha256": "...",
    "byte_length": 12345,
    "node_count": 42
  },
  "screenshot": {
    "path": "temp/mobile-smoke/p1-r2-s1-main/capture-.../screen.png",
    "sha256": "...",
    "byte_length": 456789,
    "format": "png",
    "width": 1080,
    "height": 2400
  },
  "manifest": {
    "path": "temp/mobile-smoke/p1-r2-s1-main/capture-.../manifest.json",
    "sha256": "...",
    "byte_length": 1234,
    "metadata": {
      "schema_version": "snapshot_manifest.v1"
    }
  }
}
```

Public JSON must not include raw XML, image bytes, base64 image payloads, or
arbitrary child-process output. Structural element output must not include
`text`, `content-desc`, `hint`, or other user/content-bearing XML attributes.

`snapshot_id`, `snapshot_hash`, and `hash_version` follow
`snapshot_identity.v1`. Artifact `sha256` values identify individual raw files;
`snapshot_hash` identifies canonical raw snapshot content facts. Normalized
elements and normalization metadata are excluded from `raw_snapshot_hash.v1`.

`--out-dir` is the operator-selected parent directory. Each capture reserves a
fresh `capture-*` child directory under it and writes `screen.xml` and
`screen.png`, and `manifest.json` there. Reusing the same parent directory must
not overwrite refs from a previous capture.

`manifest.json` follows `snapshot_manifest.v1`. It is a local capture-directory
manifest, not a global evidence-store record.

## Invariants

- Snapshot capture is read-only.
- Snapshot capture requires an explicit device in S1/S2.
- Raw XML and screenshot artifacts must stay recoverable through refs.
- The snapshot layer composes driver results; it does not create a second
  driver backend.
- S2 assigns a raw snapshot `snapshot_id` and `snapshot_hash`.
- S3 normalizes structural bounds, visibility, enabled state, clickable state,
  and scrollable state through `snapshot_elements.v1`.
- S3 does not add semantic labels, target ids, target signatures, app/platform
  logic, primitives, persistence, latest caches, or hidden evidence.
- S1/S2 do not write to a hidden evidence location.
- Artifact publication is all-or-cleanup for the XML/screenshot pair.
- If element normalization fails after raw files are written, the partial
  capture directory is removed best effort, public refs are not returned, and
  the capture fails closed.
- If manifest write or manifest hash calculation fails after raw files are
  written, the whole capture directory is removed best effort, public refs are
  not returned, and the capture fails closed as `snapshot_evidence_missing`.
- Snapshot failure details must not echo raw XML, image bytes, base64 markers,
  or arbitrary provider output.

## Failure Modes

- `device_required`
- `invalid_arguments`
- `device_offline`
- `driver_conflict`
- `driver_timeout`
- `driver_unavailable`
- `snapshot_dump_failed`
- `snapshot_evidence_missing`
- `snapshot_parse_failed`
- `snapshot_empty`

Driver infrastructure failures such as offline devices, conflicts, timeouts,
and driver unavailability remain visible as driver errors. Raw XML and
screenshot artifact failures map to snapshot errors. Malformed XML maps to
`snapshot_parse_failed`; XML with no valid bounded nodes maps to
`snapshot_empty`.
