# Contributing

Thanks for helping make `snap-tap` safer and sharper.

`snap-tap` is Android-first today, with an iOS backend line being designed under
the same CLI and safety model. It is a standalone toolkit, not an app-specific
automation product.

## Development Setup

Requirements:

- Python 3.11, 3.12, or 3.13,
- `uv`,
- Android tooling for live Android validation,
- Apple Devices, Developer Mode, tunneld, and later WDA/XCUITest for iOS
  experiments.

Install and validate:

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

If Windows blocks global temp/cache paths, keep transient output under `temp`:

```powershell
$env:UV_CACHE_DIR = "$PWD\temp\uv-cache"
$env:TMP = "$PWD\temp\tmp"
$env:TEMP = "$PWD\temp\tmp"
$runId = [guid]::NewGuid().ToString("N")
uv run pytest --basetemp "temp\pytest-basetemp-$runId" -o cache_dir=temp\pytest-cache
```

## Safety Rules

- No phone touch without a primitive receipt.
- No stale `eNN` replay without fresh target resolution.
- No public raw screenshot bytes, raw XML payloads, typed text, selectors,
  private paths, or lease tokens in receipts.
- Multiple online devices must require an explicit device id.
- Generated artifacts belong under `temp`, `data/cache`, or `data/evidence`,
  not in commits.

## Pull Request Expectations

Keep changes small and evidence-backed.

Before opening a PR, run:

```powershell
uv lock --check
uv run pytest
uv run ruff check src tests
uv run mypy --explicit-package-bases src tests
uv build --out-dir temp\build-check
```

For live-phone changes, include:

- exact command,
- explicit device id,
- read-only proof before mutating proof,
- receipt or structured failure output,
- confirmation that private screenshots, XML, typed text, and local paths were
  not committed.

## Architecture Boundaries

Keep in `snap-tap`:

- device discovery and readiness,
- platform backend capabilities,
- snapshots, target tables, target signatures, and fresh target resolution,
- safe tap/input/navigation primitives,
- receipts and portable proof refs.

Keep out of `snap-tap`:

- app-specific schedulers, dashboards, account vaults, content stores, and
  product runtimes,
- Instagram/TikTok platform semantics,
- model-owned phone execution,
- raw coordinate-click or selector-click APIs as public authority.

## Issue Triage

Use issues for bugs, features, and live validation evidence. For security
issues, follow `SECURITY.md` and avoid public reports until a safe disclosure
path is agreed.
