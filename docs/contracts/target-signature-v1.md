# target_signature.v1

Owner: `src/snap_tap/targets`

## Purpose

Describe one snapshot-local target strongly enough for a future fresh-snapshot
resolver to attempt a conservative match.

`target_signature.v1` is the durable target identity envelope. It is not
executable by itself, not a selector, not a coordinate-click command, and not
permission to touch the phone.

Signatures are built from `snapshot_targets.v1` only. Later layers resolve a
signature against a fresh semantic snapshot and fail closed when the target is
missing, stale, ambiguous, disabled, or out of view.

`snapshot_targets.v1` may be reconstructed from an explicit completed
`snapshot_manifest.v1` for debug/repro. That source changes only how the
signature is built. The signature remains non-executable and future phone touch
still requires fresh resolution and a primitive receipt.

## Inputs

- one successful `snapshot_targets.v1` object,
- one snapshot-local `display_id`, such as `e001`.

Signature construction must not read raw XML directly, inspect screenshots,
call the driver, read a latest snapshot cache, resolve against the current
screen, call primitives, emit receipts, or infer platform/app workflow meaning.

## Outputs

The public payload contains:

- `schema_version`: exactly `target_signature.v1`,
- `signature_id`: deterministic id over canonical safe identity fields,
- `source_snapshot_id`: copied from `snapshot_targets.snapshot_id`,
- `device_id`,
- `captured_at`,
- `display_id`,
- `semantic_index`,
- `source_index`,
- `role`,
- `identity`: whitelisted durable identity facts,
- `source_bounds`: source observation hint only,
- `requirements`: execution requirements for future callers,
- `identity_strength`,
- `refs`: sanitized source refs copied from `snapshot_targets.v1`.

Only `xml`, `screenshot`, and `manifest` ref names may cross this public
boundary. Any other ref name is invalid input for signature construction.

`identity` may contain:

- `label`,
- `label_source`,
- `resource_id`,
- `class_name`,
- `package`,
- `role`.

`source_bounds` may contain the source target bounds and center values, but they
are observation hints only. They are never executable coordinates.

`requirements` contains:

- `requires_fresh_snapshot`: `true`,
- `requires_resolution`: `true`,
- `not_executable_directly`: `true`.

`identity_strength` is a conservative summary of the usable non-coordinate
identity evidence. It may stay simple, but it must distinguish at least
insufficient identity from usable identity.

## Signature Id Rules

`signature_id` is deterministic for the same public identity inputs.

It must not include output directory paths, capture artifact paths, elapsed
times, recovery metadata, raw XML, screenshot bytes, base64, model prompts, or
anything from outside `snapshot_targets.v1`.

It may include source snapshot identity because the signature signs the source
observation, not a future resolved target. Resolution decides whether the
signature still matches a fresh snapshot.

## Identity Rules

At least one non-coordinate identity fact is required.

Signature construction must fail closed when a target has only
bounds/center/source indexes and no usable identity facts. Bounds alone must
never become a target signature.

Useful identity facts include resource id, normalized label, class name,
package, and role. Weak identity is acceptable only as an auditable signature
input for future fail-closed resolution; it is not action permission.

## Invariants

- A signature always records its `source_snapshot_id`.
- A signature always records the original `display_id`, `semantic_index`, and
  `source_index`.
- A signature is not a snapshot-local display handle.
- A signature is not a selector.
- A signature is not coordinates.
- `resource_id` is an identity fact, not a selector-click shortcut.
- `actionable` must not become execution permission.
- Future phone touch still requires fresh resolution and primitive receipt.
- Signature construction does not read or write latest snapshot cache state.
- Signature construction does not resolve ambiguity against the current screen.
- The signature does not contain Instagram, TikTok, account, workflow,
  scheduler, dashboard, model, or platform-specific meaning.
- The signature does not copy coordinate-click, selector-click, wait, or
  mutable tool API shape.

## Failure Modes

- `target_signature_missing`
- `target_signature_invalid`
- `target_signature_duplicate_display_id`
- `target_signature_unsupported_version`
- `target_signature_insufficient_identity`

Missing means the requested `display_id` is absent from the source
`snapshot_targets.v1` list.

Duplicate display ids in the source list are invalid because a display handle
must map to exactly one source target inside one snapshot.

Insufficient identity means the source target has no usable non-coordinate
identity facts. The caller must capture a richer screen state, re-teach, or wait
for a later stronger target-selection path.

## Validation Expectations

- Tests cover deterministic signature generation for the same source target.
- Tests cover `source_snapshot_id`, `display_id`, `semantic_index`, and
  `source_index` binding.
- Tests cover identity extraction and `identity_strength`.
- Tests cover missing display id, duplicate display id, unsupported source
  schema, and insufficient identity failures.
- Tests assert bounds are exported only as `source_bounds` observation data.
- Tests assert public JSON excludes resolver results, latest-cache refs,
  primitive receipts, selectors, coordinate-click commands, raw XML, screenshot
  bytes, base64, and model prompts.
- Tests assert signature construction does not call the driver, touch the
  phone, or depend on a live device.
