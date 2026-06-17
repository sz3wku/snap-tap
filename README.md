# snap-tap

`snap-tap` is a standalone phone screen-state and primitive-action toolkit. It
is Android-first today, with an iOS backend line being designed behind the same
CLI. It was extracted from the proven HAKAR phone spine, but it is a separate
open-source project and not the HAKAR product runtime.

The public v0 loop is a small agent/operator loop:

```powershell
snap-tap devices
snap-tap status <serial>
snap-tap apps <serial>
snap-tap snap <serial>
snap-tap app-open <serial> com.android.settings
snap-tap tap <serial> e001
snap-tap input <serial> e004 --text "hello"
snap-tap wake <serial>
snap-tap unlock <serial>
snap-tap back <serial>
snap-tap home <serial>
snap-tap swipe <serial> --direction up
snap-tap wait <serial> --seconds 1
snap-tap android-driver-init <serial>
snap-tap android-driver-purge <serial>
```

## Quick Start

Requirements:

- Python 3.11, 3.12, or 3.13,
- `uv`,
- Android platform tools or Android Studio,
- an Android phone with Developer options and USB debugging enabled.

After the repository is public, the shortest no-checkout smoke path is:

```powershell
uvx --from git+https://github.com/HAKAR-OS/snap-tap.git snap-tap --help
uvx --from git+https://github.com/HAKAR-OS/snap-tap.git snap-tap devices
```

For repeated use from a public Git checkout:

```powershell
uv tool install git+https://github.com/HAKAR-OS/snap-tap.git
snap-tap --help
```

For local development:

```powershell
uv sync
uv run snap-tap --help
```

Prepare an Android phone:

- install Android platform tools or Android Studio,
- enable Developer options and USB debugging,
- connect the phone over USB and accept the RSA trust prompt,
- check that `adb devices` shows the phone as `device`.

On Windows, run from PowerShell. The explicit init step prepares or repairs the
Android UIAutomator2 helper path for the selected phone:

```powershell
uv run snap-tap devices
uv run snap-tap android-driver-init <serial>
uv run snap-tap status <serial>
uv run snap-tap unlock <serial>
uv run snap-tap snap <serial>
```

On Linux, use the same commands after ADB and any required udev rules are ready:

```bash
uv run snap-tap devices
uv run snap-tap android-driver-init <serial>
uv run snap-tap status <serial>
uv run snap-tap unlock <serial>
uv run snap-tap snap <serial>
```

If more than one online device is visible, pass the serial explicitly. Mutating
commands should start only after a fresh `snap` has printed the target table.

First safe mutating smoke:

```powershell
uv run snap-tap home <serial>
uv run snap-tap app-open <serial> com.android.settings
uv run snap-tap back <serial>
```

Remove device-side Android helper artifacts:

```powershell
uv run snap-tap android-driver-purge <serial>
```

After purge, run `uv run snap-tap android-driver-init <serial>` or
`uv run snap-tap status <serial>` before the next snap/tap flow.

## Safety Model

- `snap` observes the current screen and prints snapshot-local handles like
  `e001`.
- A handle is not permission to touch the phone.
- Mutating commands rebuild a target signature, capture a fresh screen,
  resolve the target again, apply stale-target guards, execute through the
  process-isolated Android backend, and emit a primitive receipt.
- `app-open` is a small lifecycle primitive for opening a package or exact
  package/activity component. It does not guess social app names.
- `wake` and `unlock` are explicit Android primitives with receipts. `unlock`
  may dismiss only a non-secure keyguard; it never enters PINs, passwords, or
  patterns and fails closed as `secure_keyguard_required` when credentials are
  needed.
- `android-driver-purge` removes Android UIAutomator2 helper artifacts from the
  selected device. It is explicit, platform-specific, and never runs
  automatically before a touch primitive.
- `snap`, `tap`, `input`, `app-open`, and `android-driver-init` do not
  auto-unlock the phone.
- There is no public raw coordinate-click or selector-click API in the v0 shared
  runtime.

## Alpha Readiness

This repository is in public-alpha release hardening. The runtime already keeps
the hard parts: process isolation, fail-closed errors, leases, target
resolution, stale guards, after-action observation, and primitive receipts.

The headline CLI uses positional serials. `--device` remains accepted as a
compatibility/debug alias for scripts and support flows. `--json` is reserved
for debug, inspection, tests, CI, and support. `devices` and `status` are
human-readable by default; add `--json` for structured machine output.
Successful human-mode primitives print the next snap table from their
post-action observation, so the operator loop stays compact:
`snap -> tap -> tap -> input`.

`apps` lists launchable packages/components. `app-open` accepts a package such
as `com.android.settings` or a component such as
`com.android.settings/.Settings`.

## Platform Direction

Android remains the first release backend and uses UIAutomator2 for snapshots,
target tables, taps, text input, navigation, and receipts.

iOS is planned as a separate backend line, not implemented in v0. The
feasibility spike proved discovery and DVT screenshots through Apple Devices,
Developer Mode, DeveloperDiskImage, and `pymobiledevice3` tunneld. iOS
tap/input support is expected to require Mac/Xcode signing and a signed
WebDriverAgent/XCUITest runner. See `docs/PLATFORM_ARCHITECTURE.md`.

## Roadmap

- Android backend: current release line.
- Media transfer and media-picker helpers: planned after v0, so agents can
  stage phone media without platform-specific scripts.
- iOS backend: planned through DVT observation and WDA/XCUITest primitives
  after Mac/Xcode signing setup is available.
- Optional warm daemon: possible later performance path, not part of v0.

## Provenance

HAKAR may manually port back useful fixes after review, but `snap-tap` changes
do not automatically affect HAKAR.

## Development

```powershell
uv sync
uv run snap-tap --help
uv run snap-tap devices
uv run pytest
uv run ruff check src tests
uv run mypy --explicit-package-bases src tests
uv lock --check
uv build --out-dir temp\build-check
```

## Contributing and Security

See `CONTRIBUTING.md` for local setup, validation gates, and safety boundaries.
Report vulnerabilities privately through the process in `SECURITY.md`.

## License

MIT. See `LICENSE`.
