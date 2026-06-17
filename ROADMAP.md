# snap-tap Roadmap

## Bootstrap

- Standalone Python package and CLI.
- Android device readiness, screenshot/XML capture, `snap` target table.
- Safe `tap`, `input`, `replace-text`, `back`, `home`, `swipe`, and `wait`.
- App listing and exact package/component `app-open`.
- Explicit Android driver init for first-run setup and repair.
- Explicit Android driver purge for removing device-side helper artifacts.
- Primitive receipts and minimal proof refs.
- Platform-neutral backend capability model for Android-first and future iOS
  backend lines.

## Platform Architecture

- Keep one public CLI over platform-specific backend lines.
- Keep Android on the UIAutomator2 driver path.
- Add iOS in layers:
  - `ios doctor` for Apple bridge, Developer Mode, DeveloperDiskImage, tunneld,
    DVT screenshot, and WDA readiness checks,
  - `ios snap` through DVT screenshot once setup gates are clear and the public
    backend is implemented,
  - `ios targets`, `tap`, and `input` through WebDriverAgent/XCUITest after a
    signed runner is installed on a paired test device.
- Use backend capabilities to explain when a device can snap but cannot tap yet.

## Later

- Optional MCP wrapper over the same safe primitive path.
- Optional annotated screenshot/debug view.
- Media transfer and media-picker helpers for staging local files onto the
  phone before app-specific workflows.
- iOS WebDriverAgent setup once a Mac/signing station is available.
- Optional warm daemon to reduce process/bridge startup cost after the v0 CLI
  contract is stable.

## Non-Goals

- App-specific schedulers, dashboards, platform semantics, accounts, or product
  evidence stores.
- Raw coordinate-click, selector-click, shell, notification, or model-owned
  phone execution as the core API.
