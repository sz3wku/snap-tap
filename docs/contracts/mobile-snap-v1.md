# mobile_snap.v1

Owner: `snap_tap` phone spine, with CLI rendering in `snap_tap.cli`.

`mobile_snap.v1` is the normal operator/agent observation surface for one
current phone screen. It turns the lower-level snapshot, semantics, and target
facts into a compact list of visible things an agent or human can reason about.

It is not a screenshot bundle, not a raw XML dump, not a target signature, not a
target resolution result, not a primitive request, and not a primitive receipt.

## Product Boundary

`snap-tap snapshot --out-dir` is the explicit heavy debug/evidence capture. It
may write `screen.xml`, `screen.png`, and `manifest.json`.

`snap-tap snap` is the everyday screen state. By default it must not persist
screenshot/XML/manifest bundles. It may use the driver to observe the current
screen, but the public value is a target list, not hashes or artifact paths.

Dashboard and future Runs may later choose to persist evidence for a specific
run or moment. That policy is outside S6.

## CLI Shape

Default:

```powershell
snap-tap snap <serial>
```

Default output is a human-readable table:

```text
<serial>  com.example.app  1080x2400
targets: 18 tap | 1 input | 3 scroll areas | 42 visible
scroll: 3 areas detected; use --debug or --json for bounds

ID     KIND    ROLE      LABEL              CENTER      STATE
e001   tap     button    Create             982,124     enabled
e002   tap     tab       Profile            972,2240    enabled
e004   input   input     Caption            540,880     enabled
```

If a row has no semantic `label` but `snap-tap snap` can infer a short
human/operator hint from text descendants, the table may render that hint with a
`~` suffix:

```text
e009   tap     button    Continue with Instagram~             360,610     enabled
~ operator label; not target identity
```

The suffix means the displayed text is an `operator_label`, not target identity.

Machine:

```powershell
snap-tap snap <serial> --json
```

Explicit debug/repro source:

```powershell
snap-tap snap --snapshot temp\snap-tap-smoke\capture-...\manifest.json --json
snap-tap snap --snapshot temp\snap-tap-smoke\capture-... --json
```

`--snapshot` accepts either a `snapshot_manifest.v1` file or a capture
directory containing `manifest.json`. This mode is offline/read-only: it
renders `mobile_snap.v1` from the manifest source, does not call device
discovery or the driver, does not read app-current state, does not write a new
artifact bundle, and does not update `latest_snap_source.v1`. The explicit
device/serial argument is
optional in this mode, but when provided it must match the manifest device.
`--snapshot` with a non-default `--session` fails as `invalid_arguments`.

Diagnostic:

```powershell
snap-tap snap <serial> --debug
snap-tap snap <serial> --json --debug
```

The JSON contract is the source of truth. The table is a renderer and must not
be parsed by downstream automation.

Default table output should keep scrollable containers as a compact signal, not
as full target rows. Scroll bounds and duplicate nested scroll containers belong
in `--debug` or `--json`, where agents and developers can inspect them without
making the default operator view noisy.

## JSON Envelope

Required top-level fields:

- `schema_version`: exactly `mobile_snap.v1`
- `ok`
- `status`
- `device_id`
- `session_id`
- `captured_at`
- `app`
- `viewport`
- `summary`
- `snapshot`
- `targets`
- `error`

`app` contains generic Android foreground package/activity data when available.
Unknown foreground state should be represented as null fields or an explicit
unknown status, not as platform semantics.

`viewport` contains width, height, and orientation when available.

`snapshot` contains only source observation identity needed for future target
signature construction and debugging. Hashes may be present in JSON/debug
metadata, but they are not primary operator UX.

## Target Shape

Each target has:

- `id`: snapshot-local display handle such as `e001`
- `kind`: `tap`, `scroll`, `input`, `text`, `image`, or `unknown`
- `role`
- `label`
- `enabled`
- `clickable`
- `scrollable`
- `actionable`
- `center`: `{ "x": number, "y": number }`
- `bounds`: `[left, top, right, bottom]`
- `package`
- `operator_label`: optional human/operator hint used only when `label` is null

Debug targets may add:

- `source_index`
- `semantic_index`
- `class_name`
- `resource_id`
- `label_source`
- `snapshot_id`
- `operator_label_source`
- `operator_label_confidence`
- `operator_label_candidates`

`operator_label` is computed only by the `mobile_snap.v1` presentation layer.
It must not alter `SemanticElement.label`, `SnapshotTarget.label`,
`TargetSignature.identity`, target resolution, latest-source replay, or
primitive receipts.

## Kind Rules

Kind classification is generic and platform-neutral:

1. `input`: visible enabled text-entry/editable target.
2. `tap`: visible enabled clickable target.
3. `scroll`: visible enabled scrollable target.
4. `text`: visible non-actionable text context.
5. `image`: visible non-actionable image context.
6. `unknown`: visible target that does not fit the previous kinds.

If an element is both clickable and scrollable, the implementation must choose a
deterministic kind and keep the raw booleans visible in JSON. Future primitives
decide what operations are allowed.

## Summary

`summary` should include:

- `element_count`
- `target_count`
- `tap_count`
- `scroll_count`
- `input_count`
- `visible_count`
- `enabled_count`
- `clickable_count`
- `scrollable_count`

## Invariants

- Read-only: no phone touch.
- Snapshot-local ids are not durable.
- No primitive receipts.
- No platform/Instagram semantics.
- No selector-click or coordinate-click command output.
- No raw XML string, screenshot bytes, base64 payload, or image data.
- Default `snap-tap snap` must not create persistent screenshot/XML/manifest
  bundles.
- Multi-device ambiguity must fail closed unless a device is explicit.

## Failure Modes

- `device_required`
- `device_offline`
- `driver_conflict`
- `driver_timeout`
- `snap_capture_failed`
- `snap_parse_failed`
- `snap_empty`
- `snap_unavailable`

Errors must be structured in JSON mode and human-readable in table mode.

## Relationship To Later Runs

The CLI may use `mobile_snap.v1` output as the visible source for
`tap/input/replace-text eNN`, but phone touch still requires target signature
construction, fresh target resolution, primitive execution, and primitive
receipts.

`latest_snap_source.v1` is the CLI bridge: successful `snap-tap snap` writes
sanitized source target facts for one device/session, and `snap-tap tap`
rebuilds `target_signature.v1` from those facts before entering the resolved
primitive path. The `eNN` id remains snapshot-local UX and is never executable
directly.

P1.R5.S6 adds explicit snapshot source override for debug/repro:

```powershell
snap-tap tap <serial> e080 --snapshot temp\snap-tap-smoke\capture-...\manifest.json --json
```

For `snap-tap tap`, the explicit manifest source replaces only the source target
lookup used to rebuild `target_signature.v1`. It does not replace the fresh
current snapshot, target resolution, stale target guard, primitive execution,
or receipt path. Device mismatch, malformed manifests, unsafe/non-tap source
targets, insufficient identity, and stale or ambiguous fresh resolution all
fail closed before touch.

The everyday text aliases use the same latest-source bridge:

```powershell
snap-tap input <serial> e004 --text "hello" --json
snap-tap replace-text <serial> e004 --text "hello" --json
```

The source `eNN` must refer to an enabled, clickable input target in the latest
successful `snap-tap snap` for the device/session. Raw text is sent only to the
driver operation; receipts expose safe text metadata such as length/hash.
