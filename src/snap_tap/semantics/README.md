# Semantics Core

Generic semantic normalization of raw Android snapshots.

This layer turns structural snapshot facts into platform-neutral observations.
It should not contain product action policy.

The `semantic_snapshot.v1` envelope classifies visible elements into generic
roles such as:

- `button`
- `tab`
- `input`
- `text`
- `image`
- `list_item`
- `unknown`

Role classification is deterministic and conservative. It may use normalized
structural facts such as class name, resource id, package, clickable,
scrollable, enabled, visible, and bounds. It does not inspect screenshot pixels
or platform selector configs.

Labels and accessibility fields may be derived from normalized Android
`content-desc`, `text`, and `hint` values. Raw snapshot JSON and manifests still
omit those source fields.

Screen metadata stays neutral: viewport orientation, package summaries, and
aggregate counts. It does not add product-specific screen ids, safe next
actions, durable target ids, primitive execution, receipts, or mutable tool
assumptions.
