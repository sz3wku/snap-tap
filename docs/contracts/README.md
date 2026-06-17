# Contracts

These contracts describe the portable snap/tap spine: driver, snapshots,
semantics, targets, primitives, receipts, and minimal evidence refs. Android is
the first complete backend; iOS is being shaped as a separate backend line under
the same public contracts.

Everyday high-level primitive commands expose `primitive_result.v1` in JSON
mode: one `primitive_receipt.v1` plus the next `mobile_snap.v1` when available.
This includes the small `app-open` lifecycle primitive. Lower-level
`primitive-*` commands remain receipt-only.

This repository owns the portable phone boundary only. App-specific
schedulers, dashboards, platform semantics, accounts, and content workflows
belong outside these contracts.
