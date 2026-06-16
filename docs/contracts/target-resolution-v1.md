# target_resolution.v1

Owner: `src/snap_tap/targets`

## Purpose

Record the read-only result of resolving a `target_signature.v1` against a
fresh `semantic_snapshot.v1`.

S3 answers whether a durable signature matches exactly one actionable target on
the current screen. It does not touch the phone, emit primitive receipts, use a
latest snapshot cache, or make platform-specific decisions.

Future P1.R5 primitives may consider phone touch only after a `target_resolution`
result is `ok=true`, `status=resolved`, and still passes the primitive-specific
preflight checks.

## Inputs

- one `target_signature.v1`,
- one fresh `semantic_snapshot.v1`.

S3 must not read raw XML directly, inspect screenshots, call the driver, read a
latest snapshot cache, call primitives, emit receipts, or infer platform/app
workflow meaning.

## Outputs

The public payload contains:

- `schema_version`: exactly `target_resolution.v1`,
- `ok`,
- `status`: `resolved` or `blocked`,
- `signature_id`,
- `source_snapshot_id`,
- `resolved_snapshot_id`,
- `device_id`,
- `resolved_target`: present only for a successful unique actionable match,
- `match`: candidate and field-match diagnostics,
- `blocking_reason`: present only when blocked,
- `refs`: sanitized fresh snapshot refs.

`resolved_target` contains:

- `display_id`: snapshot-local handle from the fresh snapshot,
- `snapshot_id`: the fresh snapshot id,
- `semantic_index`,
- `source_index`,
- `role`,
- `bounds`,
- `enabled`,
- `clickable`,
- `scrollable`,
- `actionable`.

`match` contains:

- `identity_strength`,
- `matched_fields`,
- `candidate_count`.

`blocking_reason` contains:

- `code`,
- `detail`,
- `touched_phone`: always `false` in S3.

Allowed fresh snapshot ref names are `xml`, `screenshot`, and `manifest`.
Any other ref name is invalid input for S3.

## Matching Rules

Resolution is deterministic and conservative.

1. Validate `target_signature.v1`, including its safety requirements.
2. Validate `semantic_snapshot.v1`, its refs surface, and semantic element
   shape required for target construction.
3. Reject device mismatch.
4. Reject when `fresh_snapshot.snapshot_id == signature.source_snapshot_id`;
   the source snapshot is not a fresh current snapshot.
5. Build `snapshot_targets.v1` from the fresh semantic snapshot.
6. Match candidates by exact non-coordinate identity facts:
   - `resource_id`,
   - `label`,
   - `label_source` when label exists,
   - `class_name`,
   - `package`,
   - `role`.
7. Do not use source bounds, center coordinates, `display_id`, `semantic_index`,
   or `source_index` as identity.
8. `0` matching candidates blocks.
9. More than `1` matching candidate blocks.
10. A disabled match blocks.
11. A non-clickable match blocks.
12. Exactly one enabled and clickable match resolves.

Weak identity may resolve only when it still produces exactly one actionable
fresh target. Ambiguity always blocks.

## Invariants

- `ok=true` is required before any future primitive may consider phone touch.
- `ok=true` never means the phone was touched.
- The resolved target always belongs to `resolved_snapshot_id`, not the source
  snapshot.
- The source snapshot alone is never enough for execution.
- Source bounds and center coordinates are observation hints only.
- `display_id`, `semantic_index`, and `source_index` are not durable identity.
- `resource_id` is an identity fact, not a selector-click shortcut.
- Resolution does not read or write latest snapshot cache state.
- Resolution does not contain Instagram, TikTok, account, workflow, Scheduler,
  Teach, Dashboard, model, or platform-specific meaning.
- Resolution does not copy Android-MCP coordinate-click, selector-click, wait,
  or mutable tool API shape.

## Failure Modes

- `target_resolution_invalid_signature`
- `target_resolution_invalid_snapshot`
- `target_resolution_device_mismatch`
- `target_resolution_stale_source_snapshot`
- `target_resolution_no_match`
- `target_resolution_ambiguous`
- `target_resolution_not_clickable`
- `target_resolution_disabled`
- `target_resolution_out_of_view`

S3 may include `target_resolution_out_of_view` only when existing fresh snapshot
facts prove the target is outside the visible/actionable surface. S3 must not
add screenshot-pixel or driver inspection to determine this.

## Validation Expectations

- Tests cover a successful unique actionable match against a different fresh
  snapshot.
- Tests cover source snapshot reuse blocking as stale.
- Tests cover device mismatch blocking.
- Tests cover no match and ambiguous match blocking.
- Tests cover disabled and non-clickable match blocking.
- Tests cover malformed ref containers and malformed allowed ref values.
- Tests cover malformed fresh target fields blocking before `ok=true`.
- Tests cover unsafe target signature requirements blocking before resolution.
- Tests cover weak role-only identity resolving only when unique and actionable.
- Tests assert source bounds, center coordinates, source indexes, and display
  ids do not influence candidate matching.
- Tests assert public JSON excludes latest-cache refs, primitive receipts,
  selectors, coordinate-click commands, raw XML, screenshot bytes, base64,
  model prompts, and phone-touch results.
- Tests assert S3 does not call the driver, touch the phone, or depend on a live
  device.

## P1.R4.S4 Proof Gate

S4 does not add a new resolution schema. It stress-tests this contract before
latest-cache and primitive work.

S4 must prove:

- source bounds, center coordinates, `display_id`, `semantic_index`, and
  `source_index` do not affect identity matching,
- exact identity changes block instead of falling back to coordinates,
- duplicate identity blocks as ambiguous,
- existing stale, device mismatch, disabled, non-clickable, and malformed-input
  behavior remains fail-closed,
- live proof can capture source/fresh snapshots and resolve or block targets on
  both connected phones without touching the phone.

S4 live evidence must be metadata-only. Do not paste raw XML, screenshots,
accessibility text, base64, private labels, or mutable tool payloads into issue
evidence.
