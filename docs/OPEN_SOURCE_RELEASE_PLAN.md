# snap-tap Open Source Release Plan

Status: working starter repo in pre-alpha release hardening.

Date: 2026-06-16

## Release Intent

`snap-tap` is a standalone open-source phone screen-state and safe primitive
action toolkit. Android is the first release backend; iOS is being designed as a
separate backend line under the same public CLI and receipt model. It comes from
the proven HAKAR phone spine, but it is not the HAKAR product runtime and should
not become an automatic dependency path back into HAKAR without a separate
decision.

The public v0 should feel small and sharp:

```powershell
snap-tap devices
snap-tap status <serial>
snap-tap snap <serial>
snap-tap tap <serial> <target-id>
snap-tap input <serial> <target-id> --text "hello"
snap-tap back <serial>
snap-tap home <serial>
snap-tap swipe <serial> --direction up
snap-tap wait <serial> --seconds 1
```

`--device` remains accepted as a compatibility/debug alias, but the headline
human and agent loop is the clean positional serial form above.

## CLI UX Decision

The default CLI is for humans and everyday agent operation:

- concise command shape,
- readable target table,
- no raw coordinate-click or selector-click surface,
- receipts and proof kept behind the normal safe primitive path.

`--json` is not the primary UX. Treat it as debug/inspect/machine mode: the
"more is visible" path for agents, tests, CI, and support. Human mode should
remain the clean loop: `snap -> tap -> tap -> input`, with each
successful primitive rendering the next snap table from its post-action
observation.

## Current Evidence

Latest local verification from this repo:

- `uv lock --check` passed.
- `uv run ruff check src tests` passed.
- `uv run mypy --explicit-package-bases src tests` passed.
- `uv run pytest` passed with 440 tests.
- `uv build --out-dir temp\build-check` produced sdist and wheel.
- `snap-tap devices` detected two local Android devices.
- `snap-tap status <serial>` reported both visible Android devices healthy.
- Positional read-only live smoke passed on a local Android phone:
  - `snap-tap devices` and `snap-tap devices --json`,
  - `snap-tap status <serial>`, `snap-tap status <serial> --json`, and
    `snap-tap status --all`,
  - `snap-tap snap <serial>`,
  - `snap-tap app-current <serial>`,
  - `snap-tap snapshot <serial> --out-dir temp\live-readonly\snapshot`,
  - `snap-tap screenshot <serial> --out temp\live-readonly\screen.png`.
- L1 safe system primitive live smoke passed on a dummy Android phone:
  - `snap-tap home <serial> --json`,
  - `snap-tap wait <serial> --seconds 1 --json`,
  - `snap-tap back <serial> --json`,
  - `snap-tap swipe <serial> --direction up --json`,
  - final `snap-tap home <serial> --json` reset.

Known gaps:

- initial baseline commit exists locally: `0b19b34`; current CLI polish is
  uncommitted until reviewed,
- no public remote yet,
- OSS shell exists locally: `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`,
  `CHANGELOG.md`, GitHub issue templates, PR template, and GitHub Actions CI,
- `pyproject.toml` includes license, classifiers, keywords, and intended GitHub
  URLs; verify the real public remote before publishing,
- public docs/source strings are guarded against legacy command language and
  private serial examples,
- platform architecture now includes an iOS backend line, with `snap` proved in
  a temp spike and `tap/input` blocked on WDA signing/setup,
- L2 target mutation and text-input live gates have not run in this slice.

## Phase 0 - Freeze Baseline

Goal: make the current private starter repo a clean rollback point.

Tasks:

- create the initial commit when approved,
- keep generated files ignored,
- record current verification in the commit or issue notes,
- do not publish the repo yet.

Done when:

- `git status` is clean after the initial commit, or the no-commit exception is
  recorded in this plan,
- all local quality gates pass,
- no release announcement or public package exists yet.

Gate:

```powershell
uv lock --check
uv run pytest
uv run ruff check src tests
uv run mypy --explicit-package-bases src tests
uv build --out-dir temp\build-check
```

## Phase 1 - Public Surface Cleanup

Goal: make the repository read like a standalone open-source project, not a
copied HAKAR folder.

Tasks:

- rewrite public README language from "bootstrap, not public release" toward
  "alpha readiness",
- move HAKAR origin notes into a short provenance section,
- replace public examples that use private device serials with `<serial>`,
- replace legacy product command examples with `snap-tap`,
- keep HAKAR-only concepts out of the public core surface,
- extend repo guard tests to scan docs as well as source docs.

Done when:

- no accidental HAKAR command language appears in public docs,
- HAKAR is mentioned only as provenance and boundary context,
- tests and static checks pass.

## Phase 2 - OSS Repo Shell

Goal: make the repo safe and understandable when it becomes public.

Status: locally implemented; pending initial commit, real public remote
confirmation, and CI execution on GitHub.

Tasks:

- add `LICENSE`,
- add `SECURITY.md`,
- add `CONTRIBUTING.md`,
- add `CHANGELOG.md`,
- add GitHub issue templates,
- add GitHub Actions CI,
- add package metadata in `pyproject.toml`: license, URLs, classifiers,
  keywords.

Recommended license decision:

- MIT for maximum simplicity, selected locally, or
- Apache-2.0 if explicit patent language matters.

CI should run:

- Windows and Ubuntu,
- Python 3.11, 3.12, and 3.13,
- `uv lock --check`,
- `pytest`,
- `ruff`,
- `mypy`,
- wheel/sdist build.

## Phase 3 - CLI/API Polish

Goal: make v0 simple before people learn the wrong shape.

Status: locally implemented and validated with unit/static/build gates plus
read-only live smoke.

Tasks:

- implement positional serial everyday commands:
  - `snap-tap status <serial>`,
  - `snap-tap snap <serial>`,
  - `snap-tap tap <serial> <target-id>`,
  - `snap-tap input <serial> <target-id> --text "hello"`,
  - `snap-tap back <serial>`,
  - `snap-tap home <serial>`,
  - `snap-tap swipe <serial> --direction up`,
  - `snap-tap wait <serial> --seconds 1`.
- keep `--device` as compatibility/debug alias, but do not make it the headline
  UX,
- define `--json` as debug/inspect/machine mode,
- keep `--debug` for extra diagnostics where useful,
- keep `devices` and `status` human-readable by default, with `--json` for
  structured machine output,
- keep primitive debug commands available but clearly secondary.

Done when:

- README and help output teach the same everyday loop,
- unit tests cover positional serial forms,
- old `--device` forms either remain compatible or are intentionally removed,
- `--json` output remains structured and receipt-first.

## Phase 4 - Live Gate

Goal: prove the package on real Android devices without leaking private data.
iOS live gates stay separate until the WDA-backed backend line is ready.

Primary phone: `<PRIMARY_SERIAL>`.

Secondary phone: `<SECONDARY_SERIAL>`.

Use explicit serials. Auto-select should fail closed when multiple devices are
online.

### L0 Read-Only Smoke

```powershell
snap-tap devices
snap-tap status <serial>
snap-tap snap <serial>
snap-tap snap <serial> --json
snap-tap screenshot <serial> --out temp\live-smoke\screen.png
snap-tap snapshot <serial> --out-dir temp\live-smoke\snapshot
```

Latest local L0 note: positional `devices`, `status`, `snap`, `app-current`,
`snapshot`, and `screenshot` were verified on 2026-06-16. A parallel
`screenshot`/`snapshot` attempt produced one transient `screenshot_failed`;
rerunning `screenshot` alone passed.

Done when:

- command output is readable in human mode,
- JSON/debug output is structured,
- screenshot and snapshot artifacts stay under `temp`,
- no private raw XML, screenshot bytes, typed text, or secrets are committed.

### L1 Safe System Primitive Smoke

```powershell
snap-tap home <serial> --json
snap-tap wait <serial> --seconds 1 --json
snap-tap back <serial> --json
snap-tap swipe <serial> --direction up --json
```

Done when:

- each mutating command emits a primitive receipt,
- execution truth and proof truth remain separate,
- failures are structured and fail closed.

### L2 Target Mutation Smoke

Use a neutral test surface, not a private social account. Preferred target is a
fixture/test app or a safe local text field.

Flow:

```powershell
snap-tap snap <serial>
snap-tap tap <serial> <target-id> --json
snap-tap snap <serial>
snap-tap input <serial> <input-id> --text "snap tap smoke" --json
snap-tap snap <serial>
```

Done when:

- target ids are snapshot-local only,
- mutation re-resolves against a fresh screen before touch,
- receipts exist for every phone touch,
- no raw typed text leaks into public receipts or committed artifacts.

## Phase 5 - Public Alpha

Goal: publish honestly as an alpha, not a finished automation platform.

Tasks:

- make the GitHub repository public,
- push the clean branch,
- ensure CI is green,
- tag `v0.1.0-alpha.1`,
- write release notes:
  - what it does,
  - safety model,
  - non-goals,
  - known limitations,
  - live smoke evidence summary.

Do not publish to PyPI in this phase unless we explicitly decide the support
surface is ready.

## Phase 5b - iOS Backend Line

Goal: add iOS without weakening the Android safety model.

Tasks:

- keep `snap-tap` as one CLI with platform-specific backend capabilities,
- add `ios doctor` for Apple bridge, trust, Developer Mode, DeveloperDiskImage,
  administrator tunneld, DVT screenshot, and WDA readiness,
- implement iOS `snap` through DVT screenshot after setup gates pass,
- use a signed WebDriverAgent/XCUITest runner for iOS target tables, tap, text,
  and gestures,
- keep iOS setup honest about Mac/Xcode signing requirements.

Done when:

- dummy iPhone live smoke proves DVT screenshot and WDA `list-items`,
- iOS `tap` emits the same primitive receipt class as Android,
- setup failures explain the missing gate instead of pretending the phone is
  unsupported.

## Phase 6 - HAKAR Boundary Sync

Goal: keep HAKAR product truth and snap-tap open-source truth separate.

Tasks:

- update the HAKAR extraction issue with release status,
- keep HAKAR as the product source of truth,
- do not automatically port snap-tap PRs into HAKAR,
- port back only after explicit review and live validation,
- keep HAKAR evidence policy in HAKAR and portable receipt/proof primitives in
  snap-tap.

Done when:

- HAKAR issue notes clearly state the snap-tap release state,
- no dependency flip is implied,
- future integration remains an explicit architecture decision.

## Release Rule

No public alpha until Phases 0 through 4 are done. No PyPI release until the
first public alpha feedback loop is clean enough to support.
