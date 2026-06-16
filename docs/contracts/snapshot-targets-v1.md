# snapshot_targets.v1

Owner: `src/snap_tap/targets`

## Purpose

Represent the visible targets from one `semantic_snapshot.v1` as deterministic
snapshot-local display handles.

`snapshot_targets.v1` is the first P1.R4 bridge from semantic observation to
future target identity. It is not a replay-safe identity, not a selector, not a
coordinate-click command, and not permission to touch the phone.

Display handles such as `e001` exist only inside the source `snapshot_id`.
Future slices may use them as a CLI/operator convenience, but execution must
convert the source element into `target_signature.v1` and resolve that
signature against a fresh snapshot before any primitive can touch the phone.

## Inputs

- one successful `semantic_snapshot.v1`,
- visible semantic elements in source semantic order,
- snapshot refs already present on the semantic snapshot.

S1 must not read raw XML directly, inspect screenshot pixels, call the driver,
query the foreground app, infer a platform screen, use Android-MCP mutable tool
APIs, read latest-cache state, or create target signatures.

## Outputs

The public payload contains:

- `schema_version`: exactly `snapshot_targets.v1`,
- `snapshot_id`: copied from the source semantic snapshot,
- `device_id`,
- `captured_at`,
- `source_schema_version`: exactly `semantic_snapshot.v1`,
- `refs`: source snapshot refs copied without mutation,
- `targets`: deterministic snapshot-local target records,
- `summary`: aggregate counts for target display.

Each target record contains:

- `display_id`: a snapshot-local display handle such as `e001`,
- `snapshot_id`: the source snapshot id this handle belongs to,
- `semantic_index`: zero-based index in `semantic_snapshot.elements[]`,
- `source_index`: source raw element index from the semantic element,
- `role`,
- `bounds`,
- `enabled`,
- `clickable`,
- `scrollable`,
- `actionable`: `true` only when the semantic element is enabled and clickable,
- `label`: normalized primary label or `null`,
- `label_source`,
- optional structural source facts already allowed by `semantic_snapshot.v1`:
  `class_name`, `resource_id`, and `package`.

`summary` contains:

- `target_count`,
- `actionable_count`,
- `disabled_count`,
- `non_clickable_count`,
- `scrollable_count`,
- `labeled_count`,
- `source_element_count`.

## Handle Rules

Display handles are deterministic for one semantic snapshot.

S1 uses semantic element order, not raw XML traversal order directly, because
P1.R3 already filtered semantics to visible elements while preserving source
order.

The first semantic element is `e001`, the second is `e002`, and so on. Width is
stable for normal phone UI snapshots, but callers must treat the handle as an
opaque string and must not parse it as durable identity.

## Invariants

- A display handle is valid only with the matching `snapshot_id`.
- `source_index` remains debug/source evidence, not executable identity.
- Bounds and centers are observations only. They are not tap coordinates.
- `actionable=true` is still only an observation. It is not permission to touch
  the phone.
- Empty target output must not invent fallback handles or coordinate targets.
- S1 does not build `target_signature.v1`.
- S1 does not resolve against a fresh snapshot.
- S1 does not read or write latest snapshot cache state.
- S1 does not create primitive receipts or runtime events.
- S1 does not contain Instagram, TikTok, account, workflow, Scheduler, Teach,
  Dashboard, model, or platform-specific meaning.
- S1 does not copy Android-MCP coordinate-click, selector-click, wait, or
  mutable tool API shape.

## Failure Modes

- `snapshot_targets_input_invalid`
- `snapshot_targets_unsupported_version`

An empty semantic element list is not a runtime failure. It produces an empty
target list and zero counts so future callers fail closed by having no handle to
convert into a signature.

## Validation Expectations

- Tests cover deterministic display id generation.
- Tests cover binding every handle to the source `snapshot_id`.
- Tests cover semantic order preservation and `source_index` carry-through.
- Tests cover `actionable`, disabled, non-clickable, scrollable, and labeled
  counts.
- Tests cover empty semantic snapshots without fallback handles.
- Tests assert output excludes target signatures, resolver results, latest-cache
  refs, primitive receipts, selectors, raw XML, screenshot bytes, base64, and
  model prompts.
