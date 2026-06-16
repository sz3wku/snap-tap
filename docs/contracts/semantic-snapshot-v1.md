# semantic_snapshot.v1

Owner: `src/snap_tap/semantics`

Boundary owner: `src/snap_tap/snapshots` owns raw snapshot capture, raw artifact
refs, snapshot identity, and `SnapshotElement` structural facts.

## Purpose

Represent one observed phone screen as durable product data with generic,
platform-neutral semantic observations.

A semantic snapshot is the bridge between raw UIAutomator output and safe
target resolution. It is not a platform action, not a model prompt, and not a
Dashboard-only shape.

P1.R3.S1 owns the generic role envelope for visible raw snapshot elements.
P1.R3.S2 owns generic labels and accessibility text extraction. S3 owns screen
metadata. Snapshot-local visible target ids are introduced in P1.R4, and
phone-touch primitives stay in P1.R5.

## Inputs

- successful `raw_snapshot_capture.v1`,
- `snapshot_identity.v1` fields from the raw capture,
- `snapshot_elements.v1` structural elements,
- optional `snapshot_manifest.v1` refs when the raw capture was materialized.

S1 role classification may use only existing `SnapshotElement` facts:
`source_index`, `bounds`, `visible`, `enabled`, `clickable`, `scrollable`, optional
`class_name`, optional `resource_id`, and optional `package`. It must not read
raw XML directly, screenshot pixels, text, `content-desc`, `hint`, OCR, target
signatures, or platform selector config.

S2 label extraction may use source accessibility/text facts captured from raw
Android node attributes: `text`, `content-desc`, and `hint`. These facts are
semantic inputs, not raw public `snapshot_elements.v1` output.

S3 screen metadata may use existing raw snapshot viewport/count/package facts
and existing semantic element summaries. It must not call the driver, inspect
the foreground app separately, infer a platform screen, or read raw XML
directly.

## Outputs

- `schema_version`: exactly `semantic_snapshot.v1`,
- `snapshot_id`,
- `device_id`,
- `captured_at`: copied from the raw capture `checked_at`,
- raw evidence refs copied from the raw snapshot capture,
- `elements`: visible semantic elements in deterministic raw element order,
- `screen_metadata`: a `semantic_screen_metadata.v1` object,
- `role_normalization` summary metadata.

When exposed through `snap-tap snapshot`, the semantic snapshot is returned
as a separate `result.semantics` envelope next to the raw `result.elements`.
It does not replace raw structural elements and does not participate in
`raw_snapshot_hash.v1`.

Each S2 semantic element contains:

- `source_index`: the raw `SnapshotElement.source_index`, not a target id,
- `role`: one of `button`, `tab`, `input`, `text`, `image`, `list_item`, or
  `unknown`,
- `bounds`,
- `enabled`,
- `clickable`,
- `scrollable`,
- `label`: primary normalized label string or `null`,
- `label_source`: one of `content_desc`, `text`, `hint`, or `none`,
- `accessibility`: whitelisted non-empty accessibility/text fields,
- optional structural source facts already allowed by `snapshot_elements.v1`:
  `class_name`, `resource_id`, `package`.

`role_normalization` contains:

- `source_schema_version`: the input element normalization schema version,
- `source_element_count`,
- `visible_element_count`,
- `semantic_element_count`,
- `role_counts`: counts keyed by the S1 role enum,
- `unknown_count`,
- `labeled_count`,
- `accessibility_field_counts`: counts keyed by `text`, `content_desc`, and
  `hint`.

S2 may output normalized labels and accessibility/text fields. It does not
output raw XML, image bytes, base64, screen ids, target ids, target signatures,
target handles, primitive refs, receipts, or model prompts.

S3 may output neutral screen-level metadata such as viewport orientation,
package summaries, and aggregate counts. It does not output `screen_id`,
screen title, screen hint, safe next actions, platform screen family, target
ids, target signatures, selectors, primitives, receipts, or model prompts.

## Role Rules

Role classification is deterministic and conservative. If a visible element
does not match a platform-neutral rule, its role is `unknown`; this is a valid
classification result, not a failure.

The classifier applies one role per element using this precedence:

1. `input`: source facts explicitly identify an editable/input control, such as
   an Android edit text class or generic resource id containing `input`,
   `edit`, or `field`.
2. `tab`: source facts explicitly identify a generic tab/navigation-tab
   control, such as a tab class or generic resource id containing `tab`.
3. `list_item`: source facts explicitly identify a generic row/item/cell in a
   list-like surface. S1 must not infer this from app package names or future
   screen semantics.
4. `button`: source facts explicitly identify a button/image-button class, or
   the visible element is enabled and clickable and no stronger S1 role matched.
5. `image`: source facts explicitly identify a generic image view and the
   element was not already classified as a button.
6. `text`: source facts explicitly identify a generic text/static label view
   and the element was not already classified as an input.
7. `unknown`: no S1 rule matched.

Role rules may inspect package names only as raw structural facts already
present on the element. They must not contain Instagram, TikTok, account,
screen, workflow, or product-action meaning. Platform-specific meaning layers
belong later in `src/platforms`.

## Label Rules

Labels are generic observations from Android accessibility/text attributes.
They are not selectors, not target identities, and not instructions to tap.

S2 derives labels using this precedence:

1. `content-desc`
2. `text`
3. `hint`
4. `none`

Each source string is normalized before export:

- trim leading and trailing whitespace,
- collapse internal whitespace to one space,
- discard empty strings,
- cap field length conservatively to avoid large payloads.

The semantic element `label` contains the first normalized non-empty value by
precedence. `label_source` records which source won. `accessibility` may expose
the normalized non-empty source fields with keys `text`, `content_desc`, and
`hint`.

S2 does not infer labels from screenshots, OCR, models, platform configs,
package names, workflow state, or coordinates. Direct Android node attributes
are sufficient for S2; descendant text aggregation is deferred unless a later
slice explicitly opens it.

## Screen Metadata Rules

Screen metadata is generic observation data for the whole semantic snapshot.

`screen_metadata.schema_version` is exactly `semantic_screen_metadata.v1`.

Viewport orientation is derived only from numeric viewport dimensions:

1. `portrait`: height > width.
2. `landscape`: width > height.
3. `square`: width == height.
4. `unknown`: dimensions are missing or invalid.

Package summaries are raw observations grouped by Android package name. They
are sorted by descending `semantic_count`, then by package name. The
`dominant_package` is present only when exactly one package has a positive
highest `semantic_count`; ties or zero-count summaries return `null`.

`actionable_count` is generic and means visible semantic elements that are both
enabled and clickable. `scrollable_count` is an observation of visible semantic
elements with a true source scrollable fact. Neither count is permission to
touch the phone.

## Invariants

- Raw `source_index` values are valid only inside this source snapshot and are
  not target ids.
- Raw XML/screenshot evidence remains recoverable.
- Normalization is deterministic for the same raw input.
- No phone touch happens while building the snapshot.
- No platform action is decided here.
- No snapshot-local display target ids are exposed by P1.R3.
- No `screen_id`, `screen_title`, screen hint, safe next actions, or platform
  screen family is exposed by P1.R3.
- S1 preserves raw element order for exported visible semantic elements.
- S1 role-only output never emits `text`, `content-desc`, `hint`, OCR text,
  raw XML, screenshot bytes, base64 payloads, target signatures, primitive
  receipts, or latest-snapshot cache refs.
- Raw `result.elements` and `snapshot_manifest.v1` do not expose `text`,
  `content-desc`, or `hint`; S2 exposes normalized values only in
  `result.semantics`.
- `unknown` is the fallback role for insufficient evidence; weak guesses must
  not be promoted to specific roles.
- Bounds and centers are observations only. They are not coordinate-click
  commands.
- Package and viewport metadata are observations only. They are not platform
  readiness, account readiness, or action permission.
- No Android-MCP mutable tool, coordinate-click, selector-click, or MCP server
  API shape is copied into this contract.

## Android-MCP Parity Reference

`temp/Android-MCP` is a quarry/parity reference for keeping the state shape
simple enough for agents and future snap-tap extraction.

Useful ideas:

- lightweight state over interactive elements,
- names from `content-desc`, `text`, descendant text, and `hint` for S2 and
  later label work,
- resource id, class name, bounds, and center coordinates,
- compact screen context for future agent-readable state,
- optional annotated screenshot as a future debug/evidence aid.

Boundaries:

- no direct coordinate-click behavior,
- no selector-click/wait tools,
- no device auto-select in public `snap-tap` commands when multiple devices are
  visible,
- no base64 screenshot output in public JSON,
- no platform-specific semantics in core.

## Failure Modes

- `semantic_snapshot_input_invalid`
- `semantic_snapshot_unsupported_version`
- `snapshot_dump_failed`
- `snapshot_empty`
- `snapshot_parse_failed`
- `snapshot_evidence_missing`
- `snapshot_foreground_unknown`

Raw snapshot failures pass through from `raw_snapshot_capture.v1`. A role of
`unknown` is not a failure. Semantic snapshot construction fails only when the
input envelope is missing required raw snapshot identity/element facts, uses an
unsupported structural element schema, or cannot preserve the public privacy
and determinism invariants above.

## Validation Expectations

- Contract and unit tests use fake `SnapshotElement` values; no live phone is
  required for S1 role classification.
- Tests cover the exact role enum, precedence, stable output order, and
  `unknown` fallback.
- Tests cover label precedence, whitespace normalization, empty string discard,
  and label length caps.
- Tests cover screen metadata viewport orientation, package summaries,
  dominant package tie handling, aggregate counts, and deterministic output.
- Tests assert raw `result.elements` and manifest output exclude `text`,
  `content-desc`, and `hint`.
- Tests assert semantic JSON excludes snapshot-local target ids, raw XML, image
  bytes, base64, target signatures, primitive receipts, latest snapshot cache
  refs, screen ids, screen hints, safe next actions, and platform-specific
  roles.
- Tests assert the same raw input produces the same semantic output.

