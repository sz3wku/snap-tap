# snap-tap

`snap-tap` is a standalone phone screen-state and primitive-action toolkit. It
is Android-first today, with an iOS backend line being designed behind the same
CLI. It was extracted from the proven HAKAR phone spine, but it is a separate
open-source project and not the HAKAR product runtime.

The public v0 loop is a small agent/operator loop:

```powershell
snap-tap devices
snap-tap status <serial>
snap-tap snap <serial>
snap-tap tap <serial> e001
snap-tap input <serial> e004 --text "hello"
snap-tap back <serial>
snap-tap home <serial>
snap-tap swipe <serial> --direction up
snap-tap wait <serial> --seconds 1
```

## Safety Model

- `snap` observes the current screen and prints snapshot-local handles like
  `e001`.
- A handle is not permission to touch the phone.
- Mutating commands rebuild a target signature, capture a fresh screen,
  resolve the target again, apply stale-target guards, execute through the
  process-isolated Android backend, and emit a primitive receipt.
- There is no public raw coordinate-click or selector-click API in the v0 shared runtime.

## Alpha Readiness

This repository is in pre-alpha release hardening. The extracted runtime already
keeps the hard parts: process isolation, fail-closed errors, leases, target
resolution, stale guards, after-proof, and primitive receipts.

The headline CLI uses positional serials. `--device` remains accepted as a
compatibility/debug alias for scripts and support flows. `--json` is reserved
for debug, inspection, tests, CI, and support.

## Platform Direction

Android remains the first release backend and uses UIAutomator2 for snapshots,
target tables, taps, text input, navigation, and receipts.

iOS is planned as a separate backend line. The feasibility spike proved
discovery and DVT screenshots through Apple Devices, Developer Mode,
DeveloperDiskImage, and `pymobiledevice3` tunneld. iOS tap/input support is
expected to require a signed WebDriverAgent/XCUITest runner. See
`docs/PLATFORM_ARCHITECTURE.md`.

## Provenance

HAKAR may manually port back useful fixes after review, but `snap-tap` changes
do not automatically affect HAKAR.

## Development

```powershell
uv sync
uv run snap-tap --help
uv run pytest
uv run ruff check src tests
uv run mypy --explicit-package-bases src tests
```

## Contributing and Security

See `CONTRIBUTING.md` for local setup, validation gates, and safety boundaries.
Report vulnerabilities privately through the process in `SECURITY.md`.

## License

MIT. See `LICENSE`.
