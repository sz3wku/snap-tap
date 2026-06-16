# semantic_screen_metadata.v1

Owner: `src/snap_tap/semantics`

Boundary owner: `src/snap_tap/snapshots` owns raw viewport, artifact, and
structural element facts.

## Purpose

Represent neutral screen-level observations for one semantic snapshot.

This contract gives later target resolution and platform semantics enough
context to reason about the current screen without turning P1.R3 into platform
screen detection.

It is not a screen id, not an action hint, not a selector, not a target
signature, and not a phone-touch contract.

## Inputs

- successful `semantic_snapshot.v1`,
- successful `raw_snapshot_capture.v1`,
- `snapshot_elements.v1` normalization metadata,
- screenshot viewport width and height when available,
- raw and semantic element package/count facts.

S3 must not call the driver, inspect the current app separately, read raw XML
directly, inspect screenshot pixels, OCR, launch/stop apps, or query packages.

## Outputs

`screen_metadata` contains:

- `schema_version`: exactly `semantic_screen_metadata.v1`,
- `viewport`:
  - optional `width`,
  - optional `height`,
  - `orientation`: `portrait`, `landscape`, `square`, or `unknown`,
- `packages`: deterministic package summaries,
- `dominant_package`: the only package with a positive highest semantic element
  count, or `null` when there is no clear single dominant package,
- `counts`: deterministic screen-level counts.

Each package summary contains:

- `package`,
- `element_count`: raw bounded elements with that package,
- `visible_count`: raw visible elements with that package,
- `semantic_count`: visible semantic elements with that package.

`counts` contains:

- `source_element_count`,
- `visible_element_count`,
- `semantic_element_count`,
- `enabled_count`,
- `clickable_count`,
- `scrollable_count`,
- `actionable_count`,
- `labeled_count`,
- `unknown_count`.

## Rules

- Orientation is derived only from numeric viewport dimensions:
  - `portrait` when height > width,
  - `landscape` when width > height,
  - `square` when width == height,
  - `unknown` when dimensions are unavailable or invalid.
- `packages` is sorted by descending `semantic_count`, then by package name.
- Elements without a package do not create package summaries.
- `dominant_package` is set only when exactly one package has a positive
  highest `semantic_count`.
- `actionable_count` means visible semantic elements that are both enabled and
  clickable.
- `scrollable_count` means visible semantic elements with a true source
  scrollable fact.
- Metadata is observation only. It must not be used as a coordinate-click,
  selector-click, or platform action instruction.

## Invariants

- No phone touch happens while building screen metadata.
- No platform-specific screen detection happens in `src/snap_tap/semantics`.
- No `screen_id`, `screen_title`, `screen_hint`, `safe_next_actions`,
  snapshot-local target id, target signature, primitive receipt, model prompt,
  raw XML, screenshot bytes, or base64 payload is emitted by this contract.
- The same raw input produces the same screen metadata output.
- Missing viewport dimensions do not fail the semantic snapshot; they produce
  `orientation: "unknown"`.
- Package names are raw observations only. They are not platform readiness,
  account readiness, or action permission.

## Android-MCP Parity Reference

`temp/Android-MCP` remains a quarry for lightweight model-facing state. S3 takes
only the idea that compact screen context helps future agents.

S3 does not copy Android-MCP mutable tools, direct coordinate clicks,
selector-click/wait tools, base64 screenshots, or MCP server API shape.

## Failure Modes

Screen metadata should not introduce a new runtime failure for otherwise valid
semantic snapshots. Invalid or missing optional facts should degrade to neutral
counts or `unknown` orientation.

Existing `semantic_snapshot.v1` failures still apply when the source raw
snapshot is invalid.
