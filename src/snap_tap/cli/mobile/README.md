# CLI

Developer/operator commands for Android device readiness, snapshots, target
tables, and safe primitives.

The installed command is `snap-tap`. It exposes the phone commands at the root
instead of requiring a product-specific `mobile` namespace.

## Everyday Loop

```powershell
snap-tap devices
snap-tap status <serial>
snap-tap snap <serial>
snap-tap tap <serial> e080
snap-tap input <serial> e004 --text "hello"
snap-tap replace-text <serial> e004 --text "hello"
snap-tap back <serial>
snap-tap home <serial>
snap-tap swipe <serial> --direction up
snap-tap wait <serial> --seconds 1
```

`devices` and `status` default to compact human-readable output. Add `--json`
when an agent, test, CI job, or support flow needs the structured payload.

`snap` is the normal read-only screen observation surface. Its default output is
a compact human table with actionable target ids. `snap --json` emits the
stable machine contract, and `snap --debug` includes diagnostic source facts.

`tap`, `input`, and `replace-text` use the latest successful snap for the
device/session as a source of target facts, then capture a fresh current
snapshot before any touch. Snapshot-local ids such as `e080` are never executed
directly.

Successful human-mode primitives use the post-action observation to print the
next snap table, keeping the common loop at
`snap -> tap -> tap -> input`. Machine-mode `--json` remains receipt-first.

`--device` remains accepted as a compatibility/debug alias, but docs and help
should teach the positional serial form above.

## Debug And Maintenance

```powershell
snap-tap init <serial>
snap-tap doctor <serial>
snap-tap dump-xml <serial>
snap-tap screenshot <serial> --out <path>
snap-tap snapshot <serial> --out-dir <dir>
snap-tap snapshot-latest <serial>
snap-tap app-current <serial>
snap-tap package-info <serial> --package <package>
```

`snapshot --out-dir` is the explicit heavy debug/evidence capture. It writes a
fresh capture directory containing XML, screenshot, and manifest artifacts.
Plain `snap` does not persist those bundles.

The `primitive-*` commands are lower-level debug/repro surfaces that accept
target signatures directly and return `primitive_receipt.v1` JSON. Everyday
automation should prefer `snap`, `tap`, `input`, `replace-text`, `back`, `home`,
`swipe`, and `wait`.

## Boundaries

- No public coordinate-click or selector-click API.
- No platform, account, workflow, or social-network semantics.
- No raw XML, screenshot bytes, base64, or typed text in public receipts.
- No phone touch without a primitive receipt.
- No replay from stale snapshot-local ids.
