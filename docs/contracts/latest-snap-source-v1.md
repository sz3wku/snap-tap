# latest_snap_source.v1

Owner: `src/snap_tap/targets`

## Purpose

Remember the latest successful `snap-tap snap` source target facts for one
device/session.

`latest_snap_source.v1` is a local CLI convenience cache for everyday
`snap-tap snap` -> `snap-tap tap/input/replace-text` paths. It is not evidence
storage, not a snapshot artifact bundle, not a target signature, not a target
resolution result, and not permission to touch the phone.

## Inputs

- one successful `mobile_snap.v1`,
- one explicit device id,
- one session id, defaulting to `default`.

The cache may store only sanitized source target facts needed to rebuild
`target_signature.v1` for a selected display id.

## Storage

Recommended local cache root:

`data/cache/mobile/latest/snap-source/`

Implementations should write one JSON file per safe device/session key. Writes
should be atomic on a best-effort basis: write a temporary file in the target
directory, then replace the target file.

Every successful `snap-tap snap` overwrites the latest source for that
device/session. Failed snaps must not update it.

## Outputs

The public payload contains:

- `schema_version`: exactly `latest_snap_source.v1`,
- `device_id`,
- `session_id`,
- `updated_at`,
- `snapshot`:
  - `snapshot_id`,
  - `captured_at`,
  - `source_schema_version`,
- `targets`: sanitized source target facts:
  - `display_id`,
  - `snapshot_id`,
  - `semantic_index`,
  - `source_index`,
  - `role`,
  - `kind`,
  - `bounds`,
  - `enabled`,
  - `clickable`,
  - `scrollable`,
  - `actionable`,
  - `label`,
  - `label_source`,
  - optional `class_name`,
  - optional `resource_id`,
  - optional `package`.

No artifact refs are required for this cache. A signature rebuilt from this
cache may have empty `refs`; the primitive still captures a fresh snapshot
before resolution and touch.

## Invariants

- Snapshot-local ids such as `e080` are source display handles only.
- `snap-tap tap` must rebuild `target_signature.v1` from this cache, capture a
  fresh snapshot, resolve with `target_resolution.v1`, pass primitive stale
  guards, and emit `primitive_receipt.v1`.
- `snap-tap input` and `snap-tap replace-text` must follow the same cache ->
  signature -> fresh resolution -> stale guard -> primitive receipt path for
  source targets that are enabled, `kind=input`, and `role=input`. Text fields
  are not required to be clickable in the source accessibility tree.
- Missing, corrupt, wrong-device, or wrong-session cache data fails closed
  before snapshot capture or driver work.
- Unsafe source targets fail closed before snapshot capture or driver work.
- Safe S5 tap targets are enabled, clickable, `kind=tap`, and have a generic
  tappable role such as `button`, `tab`, or `list_item`.
- The cache does not contain raw XML, screenshot/image bytes, base64,
  `screen.png`, `screen.xml`, `manifest.json`, capture directories, primitive
  receipts, target resolution results, platform semantics, model prompts,
  selectors, or selector vault payloads.

## Failure Modes

- `latest_snap_source_missing`
- `latest_snap_source_invalid`
- `latest_snap_source_device_mismatch`
- `latest_snap_source_session_mismatch`
- `latest_snap_source_write_failed`
- `latest_snap_source_unsupported_version`
- `latest_snap_source_target_invalid`
- `latest_snap_source_target_missing`
- `latest_snap_source_target_not_tappable`
- `latest_snap_source_target_not_input`

When these failures occur through `snap-tap tap`, `snap-tap input`, or
`snap-tap replace-text`, the CLI emits a blocked `primitive_receipt.v1` with
`attempted_touch=false` and `touched_phone=false`.

## Explicit Snapshot Override

The CLI supports `snap-tap tap <serial> <eNN> --snapshot <manifest-or-capture-dir>` for
debug/repro work. That mode bypasses this latest-source cache and reads
sanitized source target facts from `snapshot_manifest.v1` instead. It must not
read, update, or fall back to `latest_snap_source.v1`.

The override changes only the source used to build `target_signature.v1`.
Execution still captures a fresh current snapshot, resolves
`target_resolution.v1`, passes the primitive stale guard, runs through
`snap_tap.primitives`, and emits `primitive_receipt.v1`.
