# latest_snapshot_ref.v1

Owner: `src/snap_tap/snapshots`

## Purpose

Remember the latest explicit successful phone snapshot for one device/session.

`latest_snapshot_ref.v1` is a CLI convenience pointer. It lets later CLI flows
recover the source snapshot reference without asking the operator to paste a
`snapshot_id` every time.

It is not a semantic snapshot, target list, target signature, target resolution,
primitive receipt, evidence store, run record, or permission to touch the phone.

## Inputs

- one successful `raw_snapshot_capture.v1` result after artifact
  materialization,
- one explicit device id,
- one session id, defaulting to `default`.

This cache must not read raw XML directly, inspect screenshot pixels, call the driver,
build target display output, build target signatures, resolve targets, call
primitives, emit receipts, infer platform/app workflow meaning, or copy
mutable tool APIs.

## Storage

Recommended local cache root:

`data/cache/mobile/latest/`

The cache is mutable local runtime state and ignored by git except for docs and
`.gitkeep` files.

Implementations should write one JSON file per safe device/session key. The key
must be deterministic and path-safe for `device_id + session_id`; do not create
arbitrary nested paths from raw user input.

Writes should be atomic on a best-effort basis: write a temporary file in the
target directory, then replace the target file.

## Outputs

The public payload contains:

- `schema_version`: exactly `latest_snapshot_ref.v1`,
- `device_id`,
- `session_id`,
- `updated_at`,
- `snapshot`: public source snapshot identity:
  - `snapshot_id`,
  - `snapshot_hash`,
  - `hash_version`,
  - `checked_at`,
  - `backend`,
  - `operation`,
- `refs`: sanitized refs for `xml`, `screenshot`, and `manifest`,
- `cache`: public cache metadata such as key, path, sha256, and byte length
  when available.

Only `xml`, `screenshot`, and `manifest` ref names may cross this public
boundary.

## Invariants

- The latest ref stores only the last successful explicit snapshot for the same
  device/session.
- Failed captures must not update the latest ref.
- A missing latest ref fails closed; it must not scan output directories to
  guess a snapshot.
- A corrupt latest ref fails closed; it must not partially trust malformed JSON.
- A device/session mismatch fails closed.
- The cache does not make a snapshot fresh for execution.
- Future phone touch still requires a target signature, fresh target
  resolution, and primitive receipt.
- `display_id`, `semantic_index`, `source_index`, bounds, and centers remain
  observations only.
- The latest ref does not contain target ids, target signatures, target
  resolution results, primitive receipts, selectors, coordinate-click commands,
  raw XML, screenshot bytes, base64 payloads, model prompts, platform semantics,
  scheduler state, product flow state, run state, or evidence payloads.

## Failure Modes

- `latest_snapshot_missing`
- `latest_snapshot_invalid`
- `latest_snapshot_device_mismatch`
- `latest_snapshot_session_mismatch`
- `latest_snapshot_write_failed`
- `latest_snapshot_ref_invalid`
- `latest_snapshot_unsupported_version`

## Validation Expectations

- Tests cover building a latest ref from a successful materialized snapshot.
- Tests cover rejecting captures without snapshot identity or required refs.
- Tests cover write/read round trip by device/session.
- Tests cover missing, corrupt, unsupported-version, device-mismatch, and
  session-mismatch failures.
- Tests cover separate refs for different sessions on the same device.
- Tests cover failed snapshot capture not updating the latest ref.
- Tests assert public JSON excludes raw XML, image bytes, base64, target lists,
  target signatures, target resolution results, primitive receipts, selectors,
  coordinate-click commands, model prompts, platform semantics, and phone-touch
  results.
- Tests assert this cache does not call the driver, touch the phone, or depend
  on a live device.

