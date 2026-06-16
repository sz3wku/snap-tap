# Contracts

These contracts describe the portable snap/tap spine: driver, snapshots,
semantics, targets, primitives, receipts, and minimal evidence refs. Android is
the first complete backend; iOS is being shaped as a separate backend line under
the same public contracts.

Everyday high-level primitive commands expose `primitive_result.v1` in JSON
mode: one `primitive_receipt.v1` plus the next `mobile_snap.v1` when available.
This includes the small `app-open` lifecycle primitive. Lower-level
`primitive-*` commands remain receipt-only.

They are derived from HAKAR's proven phone-spine contracts, but this repository
does not own HAKAR product concepts such as Teach, Scheduler, Runs, LIVE,
Dashboard, platform semantics, accounts, or content workflows.
