# Targets Core

Snapshot-local display handles, target signatures, matching, ambiguity checks,
and resolution results.

This is the fail-closed bridge between semantic snapshots and phone primitives.

## Snapshot Targets Boundary

`snapshot_targets.v1` turns one `semantic_snapshot.v1` into deterministic
snapshot-local display handles such as `e001`.

These handles are bound to the source `snapshot_id`. They are not durable target
identity, not coordinates, and not permission to touch the phone.

Later layers build `target_signature.v1`, fresh resolution, stale/ambiguous
fail-closed behavior, latest-cache convenience, and CLI-friendly display on top
of this layer.

## Target Signature Boundary

`target_signature.v1` turns one snapshot-local display handle into durable
identity evidence for future fresh-snapshot resolution.

A signature records its source `snapshot_id` and identity facts. It is not
executable directly, not a selector, and not coordinates. Phone touch remains
blocked until primitives resolve the signature against a fresh snapshot and
produce receipts.

## Target Resolution Boundary

`target_resolution.v1` resolves a target signature against a fresh semantic
snapshot.

Resolution is read-only. It may return `ok=true` only for one fresh, enabled,
safe match. Non-input matches must be clickable; input matches may be
non-clickable because Android edit fields often report that shape. It does not
touch the phone, emit receipts, use latest cache, or add platform semantics.

## Proof Boundary

The proof gate is for target resolution, not a new execution layer.

It hardens the resolver with mutation coverage and first-hand read-only live
proof on connected phones. It still does not add latest cache, CLI target UX,
primitives, receipts, selectors, or platform-specific meaning.

## Operator Observation Boundary

`mobile_snap.v1` is the operator/agent display contract for current-screen
targets.

It should expose target ids, kind, role, label, center, bounds, enabled,
clickable, scrollable, and actionability in a compact shape suitable for agents
and a human CLI table. It is still read-only observation. It does not tap,
input, swipe, emit primitive receipts, infer platform meaning, or make
snapshot-local ids durable.

## Latest Snap Source Boundary

`latest_snap_source.v1` is the local CLI convenience cache behind
`snap-tap snap` -> `snap-tap tap`.

The cache stores only sanitized source target facts for one device/session and
is overwritten by each successful `snap-tap snap`. It does not store raw XML,
screenshot bytes, artifact refs, primitive receipts, target resolution results,
platform semantics, model prompts, selectors, or selector vault payloads.

`snap-tap tap`, `snap-tap input`, and `snap-tap replace-text` may read
this cache only to rebuild `target_signature.v1` for the selected source
display id. They must then use the existing primitive path: fresh snapshot,
`target_resolution.v1`, stale target guard, driver operation, and
`primitive_receipt.v1`.

Tap source targets must be enabled, clickable, `kind=tap`, and have a generic
tappable role. Text source targets must be enabled, `kind=input`, and
`role=input`.

`eNN` remains snapshot-local source UX. It is not executable, not durable
identity, not a selector, and not coordinates.
