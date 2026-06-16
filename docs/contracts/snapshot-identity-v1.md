# snapshot_identity.v1

Owner: `src/snap_tap/snapshots`

## Purpose

Give one raw phone observation a stable machine identity without adding
semantic meaning.

`snapshot_identity.v1` is not a semantic snapshot, not a target id, and not an
evidence-store record. It identifies raw snapshot content and one capture
event.

## Fields

- `snapshot_id`: observation-scoped id,
- `snapshot_hash`: canonical raw snapshot content hash,
- `hash_version`: hash contract version.

Example:

```json
{
  "snapshot_id": "snap_20260613T203151811108Z_00d4c3844320",
  "snapshot_hash": "sha256:00d4c38443203d27c045a1a1d9f3348e1b66909561529267f36644d74efc3bf6",
  "hash_version": "raw_snapshot_hash.v1"
}
```

## Hash Input

`raw_snapshot_hash.v1` includes:

- `hash_version`,
- `device_id`,
- XML artifact `sha256`, `byte_length`, `node_count`,
- screenshot artifact `sha256`, `byte_length`, `format`, `width`, `height`.

It excludes:

- artifact paths,
- `checked_at`,
- `elapsed_ms`,
- recovery metadata,
- transient driver timing metadata,
- per-capture directory names.

## Invariants

- Artifact hashes and snapshot hashes are different concepts.
- The same raw content facts produce the same `snapshot_hash`.
- Different artifact paths do not change `snapshot_hash`.
- Different capture timestamps do not change `snapshot_hash`.
- Different capture timestamps do change `snapshot_id`.
- `snapshot_id` is not a durable target id and cannot be used as an element
  handle.
- S2 identity does not normalize bounds, visibility, clickability, semantics,
  target ids, or target signatures.

## Failure Modes

Identity generation is local and pure. If required raw refs or metadata are
missing, the caller must fail closed as `snapshot_evidence_missing`.
