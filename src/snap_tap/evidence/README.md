# Core Evidence

Low-level evidence helpers for primitive receipts and snapshots.

High-level Runs and support bundles live above this layer.

Current support:

- persist one `primitive_receipt.v1` as canonical UTF-8 JSON,
- add `primitive_snapshot_proof_refs.v1` to persisted primitive receipt JSON,
  classifying before/fresh/after snapshot refs as durable, volatile, missing,
  or not attempted,
- return an `evidence_artifact.v1` ref with hash and byte length,
- keep writes under the caller-provided evidence root,
- write receipt-only artifacts without copying screenshot/XML/manifest files.

S2 snapshot proof refs are classification only. Durable means the ref path is
under the evidence root; local/temp capture refs stay volatile and
`support_safe=false`.

