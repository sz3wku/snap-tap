# AGENTS

## Motto

Let Codex meet the phone as a real operator would: observe first, choose with
context, act with restraint, and leave proof behind.

`snap-tap` exists to give agents a trustworthy body at the phone boundary: eyes
through snapshots, hands through safe primitives, and memory through receipts.

## Project Boundary

`snap-tap` is a standalone open-source phone screen-state and primitive-action
toolkit. Android is the first complete backend; iOS is a separate backend line
being designed under the same CLI and safety model. It was extracted from the
HAKAR phone spine, but it is not the HAKAR product runtime.

Keep in `snap-tap`:

- Android device discovery and readiness,
- UIAutomator2 driver bridge,
- iOS discovery, doctor, DVT screenshot, tunneld, and WDA-backed primitives as
  separate backend capabilities,
- screenshots, XML/accessibility dumps, snapshots, and target tables,
- target signatures and fresh target resolution,
- tap, input, replace-text, back, home, swipe, and wait primitives,
- primitive receipts and portable proof refs.

Keep out of `snap-tap`:

- HAKAR Teach, Scheduler, Dashboard, Chatter, Runs/LIVE, account/content/vault,
- Instagram/TikTok platform semantics,
- product evidence policy,
- model-owned phone execution,
- raw coordinate-click or selector-click APIs as public authority.

## CLI Direction

The everyday UX should be clean and direct:

```powershell
snap-tap snap <serial>
snap-tap tap <serial> <target-id>
snap-tap input <serial> <target-id> --text "hello"
snap-tap home <serial>
```

`--json` is debug/inspect/machine mode. It should expose more structure when an
agent, test, or support flow needs it, but it is not the headline human loop.

## Safety Rules

- No phone touch without a primitive receipt.
- No stale `eNN` replay without fresh target resolution.
- No public raw screenshot bytes, raw XML payloads, typed text, selectors,
  private paths, or lease tokens in receipts.
- Multiple online devices should require an explicit serial.
- Generated artifacts belong under `temp`, `data/cache`, or `data/evidence`,
  not in commits.

## Validation Gates

Before release-facing work is considered done, run:

```powershell
uv lock --check
uv run pytest
uv run ruff check src tests
uv run mypy --explicit-package-bases src tests
uv build --out-dir temp\build-check
```

Live validation must use explicit serials and should start read-only before any
mutating command.
