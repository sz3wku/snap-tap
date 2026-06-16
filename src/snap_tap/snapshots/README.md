# Snapshots Core

Snapshot capture, storage references, hashes, and freshness rules.

Snapshot-local target IDs must never be treated as durable identifiers.

P1.R2.S1 owns `raw_snapshot_capture.v1`: a read-only composition of driver XML
and screenshot capture into explicit raw artifact refs.

P1.R2.S2 owns `snapshot_identity.v1`: raw snapshot IDs and canonical raw
snapshot hashes.

P1.R2.S3 owns `snapshot_elements.v1`: deterministic structural bounds,
visibility, enabled state, clickable state, and scrollable state for raw
snapshots.

P1.R2.S4 owns `snapshot_manifest.v1`: local capture-directory persistence
metadata for explicit `snap-tap snapshot --out-dir` captures.

P1.R4.S5 owns `latest_snapshot_ref.v1`: a small local pointer cache for the
latest explicit successful snapshot per device/session.

The latest ref is CLI convenience, not execution authority. It stores sanitized
snapshot identity and artifact refs only. It must not store raw XML, image
bytes, base64, target lists, target signatures, target resolution results,
primitive receipts, platform semantics, global evidence roots, or hidden
evidence payloads.

P1.R2.S4 does not create semantic roles/labels, target IDs, target signatures,
primitives, receipts, latest caches, global evidence roots, or a hidden
evidence store. P1.R3 semantic role normalization reads snapshot-owned
`SnapshotElement` facts and lives in `src/snap_tap/semantics`; raw snapshot capture
must not grow a second semantics implementation.

P1.R3.S2 allows the internal `SnapshotElement` model to carry normalized
Android `text`, `content-desc`, and `hint` source fields for semantics only.
Raw snapshot JSON and `snapshot_manifest.v1` still omit those fields.

P1.R4.S6 keeps a hard boundary between low-level snapshot artifacts and daily
screen observation. `snap-tap snapshot --out-dir` is the explicit heavy
debug/evidence bundle. `snap-tap snap` is a lightweight target observation
surface and must not persist screenshot/XML/manifest bundles by default.

P1.R5.S6 allows completed `snapshot_manifest.v1` captures to be read back as an
explicit debug/repro source for `snap-tap snap --snapshot` and
`snap-tap tap <serial> <eNN> --snapshot`. The manifest source is offline and read-only. It
can reconstruct sanitized structural facts and target signatures, but it is
not execution authority: tap still requires a fresh current snapshot, target
resolution, stale target guard, primitive execution, and receipt emission.
