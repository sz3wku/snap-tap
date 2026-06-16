# snapshot_elements.v1

Owner: `src/snap_tap/snapshots`

## Purpose

Convert raw UIAutomator XML nodes into deterministic structural screen facts
for `raw_snapshot_capture.v1`.

This contract is not semantic labeling, not target identity, not target
resolution, and not a phone-touch primitive. It does not create `eNN` ids,
target signatures, app/platform logic, persistence, latest caches, or hidden
evidence records.

## Inputs

- `driver_backend.v1` UIAutomator XML hierarchy dump,
- optional screenshot viewport width and height from the screenshot ref.

## Outputs

`elements` is a depth-first list of valid UIAutomator `node` elements. Each
element contains:

- `source_index`: zero-based depth-first node index from the raw XML source,
- `depth`: zero-based structural node depth,
- `bounds`: `left`, `top`, `right`, `bottom`, `width`, `height`, `center_x`,
  `center_y`,
- `visible`,
- `enabled`,
- `clickable`,
- `scrollable`,
- optional structural source facts: `class_name`, `resource_id`, `package`.

The internal `SnapshotElement` model may also carry normalized Android
accessibility source fields for `src/snap_tap/semantics`. These fields are not part
of public `snapshot_elements.v1` output.

`normalization` contains:

- `schema_version`: `snapshot_elements.v1`,
- `status`,
- `source_node_count`,
- `element_count`,
- `visible_count`,
- `enabled_count`,
- `clickable_count`,
- `scrollable_count`,
- `discarded_count`,
- `invalid_bounds_count`,
- optional `viewport_width`,
- optional `viewport_height`.

## Rules

- XML is parsed with `lxml`.
- Node order is deterministic depth-first order.
- Nodes with missing, malformed, or inverted bounds are discarded and counted.
- Zero-area parseable bounds are retained as structural facts but are not
  visible.
- `visible` is true only when:
  - `visible-to-user` is `true`,
  - bounds have positive area,
  - bounds intersect the screenshot viewport when viewport width/height are
    available.
- `enabled`, `clickable`, and `scrollable` are true only when the source
  attribute is exactly true after case-insensitive normalization.
- Public JSON must not include raw XML, image bytes, base64, `text`,
  `content-desc`, or `hint`.
- `snapshot_hash` stays `raw_snapshot_hash.v1`; normalized elements do not
  affect it.

## Failure Modes

- `snapshot_parse_failed`: XML is malformed and cannot be parsed.
- `snapshot_empty`: XML contains no valid bounded nodes after discards.

If normalization fails after raw artifacts were written, the capture directory
is removed best effort and public refs are not returned. Re-run snapshot capture
for a fresh diagnostic artifact.
