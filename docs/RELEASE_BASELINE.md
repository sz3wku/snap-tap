# Release Baseline

Status: committed local pre-alpha baseline.

Date: 2026-06-16

Baseline commits:

- `0b19b34 chore: initial snap-tap open-source baseline`
- `3ba8cd0 feat: polish positional mobile cli`

## Current Local Verification

The current starter repo has passed the release-facing local gates:

```powershell
uv lock --check
uv run pytest
uv run ruff check src tests
uv run mypy --explicit-package-bases src tests
uv build --out-dir temp\build-check
```

Observed results after CLI/API polish:

- `uv lock --check`: passed.
- `uv run pytest`: 440 passed.
- `uv run ruff check src tests`: passed.
- `uv run mypy --explicit-package-bases src tests`: passed.
- `uv build --out-dir temp\build-check`: sdist and wheel built.
- `snap-tap devices` and `snap-tap devices --json`: local Android devices
  detected.
- `snap-tap status <serial>`, `snap-tap status <serial> --json`, and
  `snap-tap status --all`: visible Android devices reported healthy.
- L1 safe system primitives on a dummy Android phone:
  `home`, `wait`, `back`, `swipe up`, and final `home` reset all emitted
  successful primitive receipts with completed proof.
- Public docs/source guard: no legacy command language or private serial
  examples in public docs/source strings.
- Public API guard: selected public modules expose importable `__all__` entries
  without private helper paths.

## Commit State

Phase 0 and the positional CLI polish are committed locally. Later API/UX polish
may still be uncommitted until reviewed and explicitly committed.

## Next Boundary

Before a public alpha, decide whether to run L2 target tap/text mutation gates
on a neutral dummy-phone surface.
