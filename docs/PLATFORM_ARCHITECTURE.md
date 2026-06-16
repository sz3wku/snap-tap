# Platform Architecture

Status: architecture direction after the 2026-06-16 iOS feasibility spike.

## Product Shape

`snap-tap` should remain one tool with one everyday CLI:

```powershell
snap-tap devices
snap-tap snap <device-id>
snap-tap tap <device-id> <target-id>
snap-tap input <device-id> <target-id> --text "hello"
```

The implementation should split below that surface:

- Android backend line: ADB transport plus UIAutomator2 driver execution.
- iOS backend line: Apple bridge/usbmux, Developer Mode, DeveloperDiskImage,
  RemoteXPC/tunneld, DVT screenshots, and later WebDriverAgent/XCUITest.

This keeps the public product simple while letting each platform have honest
setup and runtime requirements.

## Shared Package

The shared package should stay platform-neutral:

- device identity and selection,
- snapshots and proof refs,
- snapshot-local target ids such as `e001`,
- target signatures and fresh target resolution,
- primitive receipts,
- stale-target guards,
- safe human output and debug JSON output.

The shared package must not learn platform business semantics, account state,
app-specific flows, or raw coordinate/selector authority.

## Backend Capability Model

Backends advertise what they can do and what setup gates block each operation.

Current planned capability lines:

| Backend | Discover | Snap | Targets | Tap/Text | Notes |
| --- | --- | --- | --- | --- | --- |
| `uiautomator2` | yes | yes | yes | yes | Android runtime path. |
| `ios-dvt` | yes | yes | no | no | Proved screenshots through tunneld. |
| `ios-wda` | yes | yes | yes | yes | Planned iOS primitive driver after WDA setup. |

The CLI and future `doctor` commands should use this model to explain why a
device can snap but cannot tap yet.

## iOS Findings

The Windows iOS spike proved:

- Apple Devices can provide the local usbmux bridge.
- `pymobiledevice3` and `tidevice` can discover the dummy iPhone by stable UDID.
- Developer Mode and DeveloperDiskImage are required for developer services.
- On modern iOS, RemoteXPC/tunneld is required.
- On Windows, `tunneld` needs an elevated Administrator PowerShell.
- DVT screenshots work through `pymobiledevice3 developer dvt screenshot`.
- Built-in `developer accessibility list-items` did not return a usable target
  tree in this spike.
- WDA commands require a signed and installed XCUITest runner.

The immediate iOS architecture should therefore ship in layers:

1. `ios doctor`: setup checks and clear blockers.
2. `ios snap`: DVT screenshot proof when developer services are ready.
3. `ios targets/tap/input`: WDA-backed once the dummy phone has a signed runner.

## Folder Direction

Current package direction:

```text
snap_tap/
  backends/
    contracts.py
    capabilities.py
    android/
      uiautomator2/
        backend.py
        tap.py
        text.py
        navigation.py
        screenshot.py
        xml_dump.py
        probes.py
    ios/
      dvt/
        screenshot.py
        tunnel.py
      wda/
        backend.py
        tap.py
        text.py
        tree.py
  device/
  evidence/
  primitives/
  semantics/
  snapshots/
  targets/
  cli/
```

`backends/contracts.py` is the neutral result/protocol/error boundary.
`backends/android/uiautomator2` owns the concrete Android driver. The iOS
directories are intentional backend slots: DVT can provide screenshot-only
snapshots, while WDA is the future tree/tap/text implementation line.

## Doctor Direction

The future doctor should be explicit rather than magical:

```powershell
snap-tap doctor <device-id>
snap-tap ios doctor <udid>
```

For iOS it should report:

- Apple bridge/usbmux status,
- trust/pairing state,
- Developer Mode,
- DeveloperDiskImage mount,
- elevated tunneld availability,
- DVT screenshot readiness,
- WDA runner presence,
- WDA list-items/tap/type readiness.

The normal CLI should feel smooth after setup, but setup must stay honest about
Apple signing and administrator gates.
