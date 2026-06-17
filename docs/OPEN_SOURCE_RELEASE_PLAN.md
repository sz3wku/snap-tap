# Open Source Release Plan

Status: public-alpha readiness review.

Date: 2026-06-17

## Release Intent

`snap-tap` should publish first as a small Android-first CLI for observing real
phone screens, choosing snapshot-local targets, and executing safe primitive
actions with receipts.

The v0 public loop is:

```powershell
snap-tap devices
snap-tap android-driver-init <serial>
snap-tap status <serial>
snap-tap apps <serial>
snap-tap snap <serial>
snap-tap app-open <serial> <package>
snap-tap tap <serial> <target-id>
snap-tap input <serial> <target-id> --text "hello"
snap-tap wake <serial>
snap-tap unlock <serial>
snap-tap back <serial>
snap-tap home <serial>
snap-tap swipe <serial> --direction up
snap-tap wait <serial> --seconds 1
```

`--json` is debug/inspect/machine mode. The headline operator loop remains the
plain command output: `snap -> tap -> tap -> input`.

## Current Scope

In scope for the first public alpha:

- Android device discovery and readiness.
- Android UIAutomator2 driver setup, purge, observation, tap, text input,
  navigation, wait, and app-open lifecycle primitives.
- `snap` operator observation without persistent PNG/XML bundles.
- Explicit `snapshot` and `screenshot` commands for evidence/debug artifacts.
- Snapshot-local target ids, target signatures, fresh target resolution, stale
  guards, leases, receipts, and post-action observation.
- Launchable app listing and exact package/component app open.

Out of scope for the first public alpha:

- iOS primitives. iOS remains a planned backend line that requires Mac/Xcode
  signing and WebDriverAgent/XCUITest work.
- Media transfer and media picker helpers.
- Warm daemon/runtime service.
- App-specific semantics, account workflows, content stores, schedulers, or
  dashboards.
- Public raw coordinate-click or selector-click authority.

## Required Release Gates

Local gates:

```powershell
uv lock --check
uv run pytest
uv run ruff check src tests
uv run mypy --explicit-package-bases src tests
uv build --out-dir temp\build-check
```

Install smoke:

```powershell
uvx --from git+https://github.com/HAKAR-OS/snap-tap.git snap-tap --help
uvx --from git+https://github.com/HAKAR-OS/snap-tap.git snap-tap devices
```

For wheel smoke before the repo is public, install the built wheel in a fresh
venv under `temp` and run `snap-tap --help`.

Live Android smoke:

```powershell
snap-tap devices
snap-tap android-driver-init <serial>
snap-tap status <serial>
snap-tap unlock <serial>
snap-tap snap <serial>
snap-tap app-open <serial> com.android.settings
snap-tap home <serial>
snap-tap android-driver-purge <serial>
snap-tap android-driver-init <serial>
snap-tap status <serial>
```

Target mutation smoke should use a neutral test surface or test account:

```powershell
snap-tap snap <serial>
snap-tap tap <serial> <target-id>
snap-tap input <serial> <input-id> --text "snap tap smoke"
snap-tap home <serial>
```

All live validation must use explicit serials. Artifacts must stay under
`temp`, `data/cache`, or `data/evidence`.

## Release Blockers

Do not make the repository public until:

- full local gates pass,
- install smoke passes from a clean environment,
- live Android smoke passes on at least one explicit device,
- `git status` is clean,
- `SECURITY.md` has a private reporting path,
- no public output or committed artifact contains raw XML, screenshot bytes,
  typed text, selectors, private paths, tokens, or account data.

## Public Roadmap

Keep the public roadmap short:

- Android backend: current release line.
- Media transfer and media-picker helpers: later.
- iOS backend: later through DVT observation and WDA/XCUITest primitives after
  Mac/Xcode signing setup.
- Optional warm daemon: later performance work, not v0.

Long internal planning notes should stay under `temp` or another ignored
workspace path.

## Release Decision

When the blockers are clear:

1. Make the GitHub repository public.
2. Push the clean branch.
3. Confirm CI is green.
4. Tag the first alpha, for example `v0.1.0-alpha.1`.
5. Publish release notes with the safety model, validation summary, known
   limitations, and roadmap.

Do not publish to PyPI until the public alpha support surface is stable enough
to maintain.
