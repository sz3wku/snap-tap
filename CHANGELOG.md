# Changelog

All notable changes to `snap-tap` will be documented in this file.

The format follows Keep a Changelog, and this project intends to use semantic
versioning after the first public alpha.

## Unreleased

### Added

- Open-source readiness plan.
- Platform architecture direction for one CLI over Android and iOS backend
  lines.
- Backend capability model for Android UIAutomator2, iOS DVT screenshot, and
  future iOS WDA primitives.
- iOS feasibility summary captured in platform architecture docs.
- OSS repo shell: license, security policy, contributing guide, issue
  templates, and CI workflow.
- Public API/export guards for core package surfaces.
- `android-driver-init` as the public Android helper setup command.

### Changed

- Public positioning is now Android-first phone tooling with a planned iOS
  backend line.
- `--json` is documented as debug/inspect/machine mode rather than the headline
  human loop.
- `devices` and `status` are human-readable by default, with `--json` retaining
  structured machine output.
- `app-current`, `package-info`, and `app-info` now default to table output and
  use `--json` for structured output.
- `dump-xml` public JSON no longer includes the raw XML payload.
- Text primitive receipts expose text length only, not deterministic text
  hashes.
- iOS capabilities are documented and exported as planned, not implemented in
  v0.

### Not Released

- No public alpha tag yet.
- No PyPI release yet.
- iOS tap/input remains blocked on a signed WebDriverAgent/XCUITest runner.
