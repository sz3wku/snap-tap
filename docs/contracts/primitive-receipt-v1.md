# primitive_receipt.v1

Owner: `src/snap_tap/primitives`

## Purpose

Prove one primitive phone operation.

Every phone touch, attempted phone touch, or blocked-before-touch primitive
attempt must produce a receipt. A failed primitive is still product evidence.

P1.R5.S1 starts this contract with resolved `tap`. P1.R5.S2 extends the same
receipt shape to targeted `input` and `replace_text`. P1.R5.S3 extends it to
non-targeted `back`, `home`, `swipe`, and `wait`. P1.R5.S4 adds a stale target
guard for targeted primitives after target resolution and before driver touch.
P1.R5.S5 adds latest-source `tap eNN` CLI convenience. P1.R5.S6 adds explicit
snapshot debug/repro source override for `tap eNN`; the override is not
executable and still enters this receipt path only after fresh resolution and
stale-target guard. P1.R5.S7 adds everyday CLI aliases for
`input/replace-text eNN` and `back/home/swipe/wait`; these are thin entrypoints
into the same primitive receipt path, not separate executors. P1.R5.S8 splits
primitive execution truth from post-action observation proof and adds a central
post-action settle policy before default after-snapshot proof. The everyday
human primitive aliases may render a successful after-snapshot as the next snap
table, but this is CLI presentation on top of the receipt, not a change to the
receipt contract itself.

P1.R6.S1 persists one completed, blocked, failed, or partial
`primitive_receipt.v1` payload as canonical UTF-8 JSON under the caller's
evidence root and returns an `evidence_artifact.v1` ref. This is receipt-only
durability: it does not copy screenshot, XML, or manifest artifacts.

P1.R6.S2 adds an evidence-owned `snapshot_proof_refs` view to persisted
primitive receipt evidence. The view does not move or retain screenshot, XML,
or manifest artifacts. It labels before/fresh/after snapshot refs as
`durable`, `volatile`, `missing`, or `not_attempted` so future support and
replay code can distinguish evidence-root refs from local/temp capture refs.

## Inputs

- primitive request,
- device id,
- operation lease metadata,
- target resolution for targeted primitives,
- before/fresh snapshot metadata,
- driver operation result,
- after-snapshot result when touch was attempted/confirmed or when a wait
  primitive needs before/after proof.

## Required Public Envelope

The public payload contains:

- `schema_version`: exactly `primitive_receipt.v1`,
- `receipt_id`,
- `operation`,
- `ok`,
- `status`: `completed`, `blocked`, `failed`, or `partial`,
- `device_id`,
- `started_at`,
- `finished_at`,
- `elapsed_ms`,
- `lease`,
- `request`,
- `target_resolution`,
- `driver_result`,
- `attempted_touch`,
- `touched_phone`,
- `execution_status`,
- `proof_status`,
- `after_snapshot_required`,
- `post_action_settle_ms`,
- `before_snapshot`,
- `fresh_snapshot`,
- `after_snapshot`,
- `after_snapshot_status`,
- `blocking_reason`,
- `error`.

When the receipt is persisted through `src/snap_tap/evidence`, the JSON artifact
also contains:

- `snapshot_proof_refs`: schema version
  `primitive_snapshot_proof_refs.v1`, with `before`, `fresh`, and `after`
  entries.

`lease` contains only safe public lease facts such as device id, acquired flag,
holder kind, and expiry/timeout metadata. It must not expose private process
tokens, host-specific temp paths, or lock implementation details.

`request` contains public primitive intent and parameters. For targeted
primitives, this means operation, device id, target signature id/source snapshot
id when available, and timeout/session metadata. Text primitives include mode
and safe text metadata such as length/hash, not the raw requested text payload.
It must not contain raw XML, screenshot bytes, selectors, model prompts, raw
operator text, or platform workflow meaning.

For S3 non-targeted primitives, `request` contains only explicit safe intent:
operation, device id, timeout/lease metadata, wait seconds, or swipe
direction/distance/duration. Swipe has no public arbitrary coordinate or
selector API; coordinates are derived internally from the current snapshot
viewport.

`target_resolution` contains public `target_resolution.v1` payload or a compact
equivalent with the same safety fields. A targeted primitive may touch the phone
only when resolution is `ok=true` and `status=resolved`.

`driver_result` contains public driver outcome when a driver call was made.
It should include backend, elapsed time, attempted flag, confirmed action flag
when available, and structured failure when unavailable. It must not copy raw
stderr/stdout.

`confirmed` is the normalized driver-boundary confirmation, not raw library
return truth. If a backend is known to return `false`/`null` for successful
coordinate taps, the child probe may normalize a no-exception tap call to
`confirmed=true` and keep the raw return only as safe metadata.

Snapshot fields contain metadata and refs only. They must not contain raw XML
strings, screenshot bytes, image base64, or private file contents.

`snapshot_proof_refs` is a safe derived support view over the snapshot fields.
Each entry contains `status` and `support_safe`. Snapshot id, device id,
captured timestamp, whitelisted artifact refs, and a reason are included only
when available and safe. Artifact `path` is included only for durable refs under
the evidence root. Local/temp capture refs remain `volatile` with
`support_safe=false`. A proof that was expected but unavailable is `missing`.
A proof that was not attempted or not applicable is `not_attempted`.

`execution_status` is the primitive's driver/action outcome. It is separate
from `proof_status`, which describes whether post-action observation was
collected. A confirmed driver action remains execution-completed even if
after-snapshot proof is unavailable.

`post_action_settle_ms` records the central delay applied before after-snapshot
proof. Callers should not have to pass this for normal use; bounded overrides
are debug/repro policy, not everyday UX.

For high-level CLI mode, the same `after_snapshot` may be converted back into
`mobile_snap.v1` and written as the next latest source for the same
device/session. Human mode renders that observation as the next snap table.
Machine mode wraps the receipt and observation in `primitive_result.v1`. That
presentation/update behavior belongs to the CLI surface, not to
`primitive_receipt.v1` itself.

## Status Rules

- `completed`: the primitive execution completed and required proof policy
  succeeded or was not required.
- `blocked`: pre-touch guard blocked; `attempted_touch=false` and
  `touched_phone=false`.
- `failed`: driver failed before confirmed touch, or a false-success result was
  detected. If the child process timed out after the tap was launched, the
  receipt must conservatively report that the phone may have been touched.
- `partial`: execution completed or may have touched the phone, but required or
  default post-action proof was unavailable.

`ok=true` is allowed only for a clean `completed` primitive. Receipts for
`blocked`, `failed`, and `partial` are still valid evidence objects. If
after-snapshot proof fails after a confirmed driver action and proof was not
required by the caller/policy, the receipt may still represent completed
execution while exposing proof as unavailable.

## Invariants

- No phone touch without a receipt.
- Targeted touches require `target_resolution.v1 ok=true`.
- A blocked-before-touch receipt must prove `touched_phone=false`.
- If the driver was called, `attempted_touch=true`.
- If the phone was touched or may have been touched, the receipt says so.
- Timeout after the child driver process starts is ambiguous and must not report
  `touched_phone=false` unless the backend can prove no touch occurred.
- If after-snapshot fails after attempted or confirmed touch, the receipt must
  preserve execution truth and expose proof truth separately. Proof failure must
  not claim the phone was not touched.
- `ok=true` from a driver/process is not enough; normalized backend
  confirmation is required. Raw backend return values are diagnostic metadata
  unless that backend contract explicitly defines them as no-touch proof.
- Source snapshot handles such as `eNN` are never execution permission.
- Bounds/center are internal resolved-target coordinates, not a public
  coordinate-click API.
- Receipts are machine-readable and support-bundle friendly.
- Receipts do not include Instagram/TikTok/account/platform semantics.
- Durable receipt evidence is one canonical JSON artifact plus a ref containing
  kind, owner, relative path, sha256, byte length, creation time, redaction
  class, and optional device/session/run/flow metadata.
- `snapshot_proof_refs` must not make local/temp snapshot paths appear durable.
- S2 snapshot proof refs are classification only; durable snapshot retention
  and support bundle packaging belong to later evidence slices.

## S8 Runtime Reliability Boundary

Post-action observation should be reliable enough for runtime use without
turning proof collection into a brittle execution gate.

It must:

- keep fresh target resolution mandatory for targeted primitives before touch;
- let deterministic system navigation (`home`, `back`) execute without a
  successful pre-action screenshot;
- apply a central default settle before after-snapshot proof for mutating
  primitives;
- keep the default settle in core policy, not in operator muscle memory;
- separate `execution_status` from `proof_status`;
- never hide a failed proof path, and never hide a possible or confirmed phone
  touch;
- avoid scattered sleeps in CLI/platform/Teach/Scheduler layers.

## S1 Lease Boundary

S1 uses a small per-device operation lease to prevent same-device concurrent
mutating primitives, including separate repo-local CLI invocations on the same
host.

The lease is not Scheduler ownership and not a future lane claim. It is a
local primitive safety guard.

It must:

- be per-device,
- be visible across local primitive processes,
- fail closed on active conflict,
- not allow caller-controlled expiry to steal an unreleased lease,
- release on success, blocked, failure, and exception paths,
- expose safe public metadata in receipts,
- be testable without a real phone.

## S1 Tap Boundary

The S1 tap primitive is explicit and debug-oriented. Everyday `tap eNN` UX is
deferred to P1.R5.S5.

S1 tap must:

1. acquire the device operation lease,
2. capture/complete a fresh snapshot for target resolution,
3. resolve `target_signature.v1` against that fresh snapshot,
4. block before touch on stale, ambiguous, disabled, non-clickable, malformed,
   or missing target resolution,
5. tap only the resolved target center through the process-isolated driver
   backend,
6. normalize backend tap confirmation at the child process boundary,
7. attempt after-snap inside the same lease when touch was attempted or
   confirmed,
8. return one receipt.

## S2 Text Boundary

S2 adds explicit debug-oriented targeted text primitives:

- `input`: focus a resolved input target and enter text.
- `replace_text`: focus a resolved input target, clear existing text through
  the driver bridge, and enter replacement text.

S2 text primitives must:

1. validate device id, target signature source, text payload, and mode before
   any subprocess call,
2. acquire the same per-device primitive lease before any possible phone touch,
3. capture a fresh snapshot and resolve `target_signature.v1`,
4. block before the driver when resolution is stale, missing, ambiguous,
   disabled, or malformed,
5. additionally block before the driver when the resolved target is not an
   input-like semantic target,
6. call only the process-isolated UIAutomator2 text driver operation,
7. use argument-list subprocess execution for serial and text payloads,
8. treat false-success or malformed driver payloads as structured failure,
9. capture an after-snapshot when text input was attempted or may have occurred,
10. return one receipt with request, resolution, driver result, fresh/after refs,
    attempted/touched truth, and structured failure when applicable.

The text payload itself is an input to the process-isolated driver operation,
not a public receipt field. Public receipts expose `text_length` and
`text_sha256` so support evidence can correlate an attempt without printing
operator text.

S2 does not add Instagram composer logic, platform semantics, model-generated
text, coordinate input public API, stale latest-cache execution, hidden retry,
durable evidence layout, or runtime events.

## S6 Explicit Snapshot Source Boundary

`snap-tap tap <serial> <eNN> --snapshot <manifest-or-capture-dir>` may read a completed
`snapshot_manifest.v1` only to rebuild source target facts and
`target_signature.v1`.

It must block before fresh snapshot capture, driver discovery, or touch when:

- the path is missing, malformed, not `snapshot_manifest.v1`, incomplete, or
  unsuccessful;
- artifact refs escape the capture directory or fail byte-length/hash checks;
- manifest device does not match the requested serial;
- `--snapshot` is combined with a non-default `--session`;
- the requested source target is missing, malformed, non-tap, or has
  insufficient identity.

A blocked-before-touch result from these failures is a receipt with
`attempted_touch=false`, `touched_phone=false`, `driver_result=null`, and
`after_snapshot_status=not_attempted`.

## S7 CLI Loop Boundary

Everyday CLI commands:

- `snap-tap tap <serial> eNN`
- `snap-tap input <serial> eNN --text ...`
- `snap-tap replace-text <serial> eNN --text ...`
- `snap-tap back <serial>`
- `snap-tap home <serial>`
- `snap-tap swipe <serial> --direction ...`
- `snap-tap wait <serial> --seconds ...`

must emit `primitive_receipt.v1` through the existing primitive code paths.

`input` and `replace-text` rebuild `target_signature.v1` from
`latest_snap_source.v1`, then use the S2 text primitive path. They must block
before fresh snapshot capture or driver work when the source cache is missing,
malformed, wrong-device/session, or the source target is missing, non-input,
disabled, or has insufficient identity. After fresh snapshot
capture, stale or ambiguous resolution still blocks before driver work. Public
receipt request metadata records text length/hash, not raw text.

`back`, `home`, `swipe`, and `wait` are everyday aliases for the S3 navigation
primitive path. `swipe` remains direction-only with bounded distance/duration;
it does not expose arbitrary coordinates or selectors.

## S4 Stale Target Guard Boundary

S4 hardens targeted `tap`, `input`, and `replace_text` primitives.

After `target_resolution.v1` succeeds and before any driver call, targeted
primitives compare `target_signature.source_bounds` with the resolved fresh
target bounds. This comparison is a primitive preflight safety guard only. It
does not change target resolution identity matching and does not allow bounds,
centers, display ids, semantic indexes, or source indexes to become execution
identity.

The guard fails closed with `primitive_target_stale` when:

- resolved target center drift exceeds `max(64px, 10% of the smaller valid
  viewport dimension)`;
- resolved target width or height drifts by more than `35%` from the source
  signature bounds;
- required source or resolved bounds are invalid.

When the guard blocks, the receipt must preserve `target_resolution`, report
`attempted_touch=false` and `touched_phone=false`, set `driver_result=null`, and
set `after_snapshot_status=not_attempted`.

## S3 Navigation And Wait Boundary

S3 adds explicit debug-oriented non-targeted primitives:

- `back`: press Android back through the process-isolated driver bridge.
- `home`: press Android home through the process-isolated driver bridge.
- `swipe`: derive a directional viewport swipe from the current snapshot.
- `wait`: hold the same primitive lease for a bounded sleep and prove
  before/after snapshots without touching the phone.

S3/S8 `back`, `home`, and `swipe` primitives must:

1. validate device id and primitive arguments before subprocess work,
2. acquire the same per-device primitive lease,
3. capture a before snapshot for `swipe`, because viewport dimensions are
   required to derive safe internal coordinates,
4. block before the driver only for `swipe` when the before snapshot is
   unavailable,
5. for `swipe`, block before the driver when viewport width/height are missing
   or invalid,
6. call only the process-isolated UIAutomator2 navigation driver operation,
7. treat false-success, malformed output, non-JSON payloads, timeout, and
   nonzero child exits as structured failures,
8. capture an after-snapshot when touch was attempted or may have occurred,
9. return one receipt with attempted/touched truth and structured failure when
   applicable.

S3 `swipe` accepts only `up`, `down`, `left`, or `right`, a bounded
`distance_ratio`, and a bounded `duration_ms`. It does not expose arbitrary
coordinates, selectors, target signatures, or platform-specific behavior.

For UIAutomator2 `back`/`home`, raw `press(...)` return values are not public
confirmation truth. The child process normalizes a no-exception press call as
confirmed and may keep safe raw-return facts only as diagnostic metadata.

S8 explicitly exempts `back` and `home` from pre-action screenshot blocking.
They still acquire the primitive lease, execute through the process-isolated
driver bridge, apply post-action settle, attempt after-snapshot proof, and
record execution/proof truth separately.

S3 `wait` must acquire the primitive lease, capture before and after snapshots,
sleep only for a bounded duration, and report `attempted_touch=false` and
`touched_phone=false` for every receipt outcome.

## Failure Modes

- `primitive_lease_conflict`
- `primitive_invalid_request`
- `primitive_snapshot_blocked`
- `primitive_resolution_blocked`
- `primitive_target_stale`
- `primitive_viewport_blocked`
- `primitive_driver_failed`
- `primitive_driver_timeout`
- `primitive_driver_unavailable`
- `primitive_false_success`
- `primitive_after_snapshot_failed`
- `primitive_receipt_failed`
- `primitive_target_not_input`

## Validation Expectations

- Tests cover lease acquire/release and conflict.
- Tests prove conflict blocks before snapshot/driver touch.
- Tests prove target resolution blocked returns a receipt and no driver call.
- Tests prove stale targeted bounds block before driver while preserving target
  resolution evidence.
- Tests prove resolved tap success returns `completed`.
- Tests prove false-success driver payload returns `primitive_false_success`.
- Tests prove after-snapshot failure after touch returns non-clean status.
- Tests prove wait returns before/after proof with no attempted/touched phone.
- Tests prove swipe blocks on missing viewport before driver touch.
- Tests assert public receipt JSON excludes raw XML, screenshot bytes, base64,
  selectors, raw text payloads, model prompts, platform semantics, and private
  lease tokens.

