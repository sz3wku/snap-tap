# Snapshots Core

Snapshot capture, storage references, hashes, and freshness rules.

Snapshot-local target IDs must never be treated as durable identifiers.

`raw_snapshot_capture.v1` is a read-only composition of driver XML and
screenshot capture into explicit raw artifact refs.

`snapshot_identity.v1` contains raw snapshot IDs and canonical raw snapshot
hashes.

`snapshot_elements.v1` contains deterministic structural bounds, visibility,
enabled state, clickable state, and scrollable state for raw snapshots.

`snapshot_manifest.v1` contains local capture-directory persistence metadata
for explicit `snap-tap snapshot --out-dir` captures.

`latest_snapshot_ref.v1` is a small local pointer cache for the latest explicit
successful snapshot per device/session.

The latest ref is CLI convenience, not execution authority. It stores sanitized
snapshot identity and artifact refs only. It must not store raw XML, image
bytes, base64, target lists, target signatures, target resolution results,
primitive receipts, platform semantics, global evidence roots, or hidden
evidence payloads.

Snapshot capture does not create semantic roles/labels, target IDs, target
signatures, primitives, receipts, latest caches, global evidence roots, or a
hidden evidence store. Semantic role normalization reads snapshot-owned
`SnapshotElement` facts and lives in `src/snap_tap/semantics`; raw snapshot
capture must not grow a second semantics implementation.

The internal `SnapshotElement` model may carry normalized Android `text`,
`content-desc`, and `hint` source fields for semantics only.
Raw snapshot JSON and `snapshot_manifest.v1` still omit those fields.

A hard boundary stays between low-level snapshot artifacts and daily screen
observation. `snap-tap snapshot --out-dir` is the explicit heavy debug/evidence
bundle. `snap-tap snap` is a lightweight target observation surface and must not
persist screenshot/XML/manifest bundles by default.

Completed `snapshot_manifest.v1` captures may be read back as an explicit
debug/repro source for `snap-tap snap --snapshot` and
`snap-tap tap <serial> <eNN> --snapshot`. The manifest source is offline and
read-only. It can reconstruct sanitized structural facts and target signatures,
but it is not execution authority: tap still requires a fresh current snapshot,
target resolution, stale target guard, primitive execution, and receipt
emission.
