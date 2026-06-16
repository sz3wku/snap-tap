# primitive_result.v1

Owner: `snap_tap.cli`

`primitive_result.v1` is the high-level CLI machine envelope for everyday
mutating commands:

- `snap-tap tap <serial> eNN --json`
- `snap-tap input <serial> eNN --text "hello" --json`
- `snap-tap replace-text <serial> eNN --text "hello" --json`
- `snap-tap back <serial> --json`
- `snap-tap home <serial> --json`
- `snap-tap swipe <serial> --direction up --json`
- `snap-tap wait <serial> --seconds 1 --json`
- `snap-tap app-open <serial> com.example.app --json`

It exists so agents can keep moving after a phone action without issuing a
separate `snap`. It does not replace `primitive_receipt.v1`.

## Shape

Required fields:

- `schema_version`: exactly `primitive_result.v1`
- `ok`
- `status`
- `operation`
- `device_id`
- `receipt`: the full `primitive_receipt.v1`
- `next_snap`: `mobile_snap.v1` or null

`receipt` remains the proof of execution, touch truth, target resolution,
blocking reasons, and safe text metadata. `next_snap` is the post-action
operator/agent observation when an after-snapshot exists and can be rendered as
`mobile_snap.v1`.

## CLI Split

Everyday high-level commands return this envelope in `--json` mode. Human mode
renders only the next snap table on clean success and falls back to the receipt
on failure or missing post-action observation.

Lower-level `primitive-*` commands stay receipt-only. They are debug/repro/audit
surfaces for callers that want only `primitive_receipt.v1`.

## Invariants

- No phone touch is hidden: every result contains a receipt.
- `next_snap` is never execution authority by itself.
- If `next_snap` is present, the CLI may also update `latest_snap_source.v1` for
  the same device/session so the next `tap/input/replace-text eNN` can continue
  from the returned observation.
- Raw XML, screenshot bytes, screenshot base64, raw typed text, selectors, and
  platform workflow semantics must not appear in this envelope.
