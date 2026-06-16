# Primitives Core

Safe phone primitives such as tap, input, back, home, swipe, and wait.

Primitives execute resolved requests and return receipts. They do not decide
what product action should happen.

## Targeted Primitives

`tap`, `input`, and `replace_text` require target facts from a previous snap,
capture a fresh current observation, resolve `target_signature.v1` against that
fresh snapshot, and acquire the per-device operation lease before touch.

If resolution blocks, the receipt proves `touched_phone=false`. If the driver is
called, the receipt records `attempted_touch=true`. If the phone was touched or
may have been touched, primitives attempt an after-snapshot after the central
post-action settle policy.

The stale target guard compares source bounds with the freshly resolved target
before calling the driver. Large drift returns a blocked
`primitive_target_stale` receipt without touching the phone.

Text primitives expose text length/hash in receipts, not raw operator text.

## Navigation Primitives

`back`, `home`, and `swipe` acquire the same per-device lease and call the
process-isolated navigation driver operation. `swipe` is direction-only:
coordinates are derived internally from the current viewport.

`wait` captures before/after snapshots around a bounded sleep and reports no
attempted phone touch.

## Boundaries

- No public coordinate-click or selector-click API.
- No platform, account, workflow, or model-owned execution policy.
- No hidden retry after a touch may have happened.
- No phone touch without a `primitive_receipt.v1`.
