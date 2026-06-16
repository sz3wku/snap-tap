# snap-tap Roadmap

## Bootstrap

- Standalone Python package and CLI.
- Android device readiness, screenshot/XML capture, `snap` target table.
- Safe `tap`, `input`, `replace-text`, `back`, `home`, `swipe`, and `wait`.
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
  - `ios snap` through DVT screenshot once setup gates are clear,
  - `ios targets`, `tap`, and `input` through WebDriverAgent/XCUITest after a
    signed runner is installed on the dummy phone.
- Use backend capabilities to explain when a device can snap but cannot tap yet.

## Later

- Public docs polish and examples.
- Public alpha readiness plan in `docs/OPEN_SOURCE_RELEASE_PLAN.md`.
- Optional MCP wrapper over the same safe primitive path.
- Optional annotated screenshot/debug view.
- iOS WebDriverAgent setup once a Mac/signing station is available.

## Non-Goals

- HAKAR Teach, Scheduler, Dashboard, Chatter, platform semantics, accounts, or
  product evidence store.
- Raw coordinate-click, selector-click, shell, notification, or model-owned
  phone execution as the core API.
