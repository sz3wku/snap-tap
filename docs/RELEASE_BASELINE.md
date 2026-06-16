# Release Baseline

Status: Phase 0 baseline recorded without a commit by user request.

Date: 2026-06-16

## Current Local Verification

The current starter repo has passed:

```powershell
uv lock --check
uv run pytest
uv run ruff check src tests
uv run mypy --explicit-package-bases src tests
uv build --out-dir temp\build-check
```

Observed results after Phase 1 cleanup:

- `uv lock --check`: passed.
- `uv run pytest`: 420 passed.
- `uv run ruff check src tests`: passed.
- `uv run mypy --explicit-package-bases src tests`: passed.
- `uv build --out-dir temp\build-check`: sdist and wheel built.
- `snap-tap devices`: local Android devices detected.
- `snap-tap status --all`: visible Android devices reported healthy.
- Public docs/source guard: no legacy command language or private serial
  examples in public docs/source strings.

## No-Commit Exception

Phase 0 normally ends with an initial commit, but this run intentionally stops
before staging or committing. The repository remains local and private until
the release shell and license decisions are discussed.

## Next Boundary

Stop before Phase 2 (`LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, CI, package
metadata) and discuss licensing/repo shell decisions.
