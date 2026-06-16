# dependency_boundary.v1

Owner: snap-tap shared package and backend boundaries

Status: accepted extraction contract

## Purpose

Define the small dependency set `snap-tap` may rely on before public alpha.

Dependencies are product architecture. A package can be installed in `.venv`
without becoming legal in every module. Shared runtime code may only import
shared dependencies. Optional groups become legal only inside their owner phase.

## Core Dependencies

These are allowed for the Android-first shared runtime and CLI. iOS runtime
dependencies remain deferred until the iOS backend line is implemented behind
doctor/setup checks.

| Package | Owner | Purpose |
|---|---|---|
| `uiautomator2` | `src/snap_tap/backends/android/uiautomator2` | Host bridge to Android UIAutomator. |
| `adbutils` | `src/snap_tap/device` | ADB discovery, serials, connect, and fallback utilities. |
| `pydantic` | deferred/contracts | Optional typed envelopes if future contracts need them. |
| `pydantic-settings` | deferred/config | Optional configuration if future runtime settings need it. |
| `typer` | `src/snap_tap/cli` | CLI command surface for operators and agents. |
| `rich` | deferred CLI polish | Optional richer CLI rendering if plain Typer output is not enough. |
| `pillow` | `src/snap_tap/evidence` | Screenshots, image evidence, annotations, support artifacts. |
| `lxml` | `src/snap_tap/snapshots` | Android XML dump parsing and normalization. |
| `httpx` | deferred integrations | Optional client calls for future wrappers, not shared phone execution. |
| `aiosqlite` | deferred storage | Optional local storage if future support flows need it. |
| `pymobiledevice3` | deferred iOS backend | Optional Apple bridge, tunneld, DVT, and WDA client path. |

## Optional Groups

### `api`

Allowed only if a separate API-facing wrapper opens.

| Package | Owner | Purpose |
|---|---|---|
| `fastapi` | API wrapper | Optional local HTTP API around the safe primitive path. |
| `uvicorn[standard]` | API runtime | ASGI server for local development/runtime. |

### `browser`

Not part of core. Browser/scraper packages are out of scope for `snap-tap`.

| Package | Owner | Purpose |
|---|---|---|
| `rebrowser-playwright` | out of scope | Browser/scraper producer automation. Not mobile execution. |

### `dev`

Allowed for tests, validation, and local development.

| Package | Purpose |
|---|---|
| `pytest` | Test runner. |
| `pytest-asyncio` | Async tests for API/runtime loops. |
| `pytest-cov` | Coverage checks when useful. |
| `ruff` | Lint and formatting. |
| `mypy` | Type checking for contracts and boundaries. |

## Forbidden For The Foundation

Do not add these without a new ADR or phase-specific contract:

- `fastmcp` in the shared runtime,
- `Django`,
- `gevent`,
- `Qt`,
- `pyinstaller`,
- `selenium`,
- `opencv-python`,
- `numpy`,
- `sqlalchemy`,
- provider SDKs such as `openai`, `google-genai`, or `ollama`.

Notes:

- Onimator validates the `uiautomator2` / `adbutils` direction, but its heavy
  packaged stack is a warning, not a template.
- `fastmcp` may return later for a separate MCP/snap-tap plugin, not the shared
  phone spine.
- Provider SDKs may return later only in optional wrappers, not in the shared
  package.

## Invariants

1. `snap_tap.primitives` remains the only phone-touch layer.
2. Browser dependencies must not be imported from mobile/shared execution.
3. API dependencies must not create a second scheduler, runtime, or evidence
   truth.
4. Storage starts with SQLite and `aiosqlite`; an ORM requires a later decision.
5. Adding a dependency is an architecture change when it affects runtime,
   storage, phone control, public API, or operator UX.
