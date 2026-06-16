# driver_backend.v1

Owner: `src/snap_tap/backends`

## Purpose

Define the host-side driver boundary used by `snap-tap` to observe and operate
a real phone through platform-specific backend lines.

The first complete driver backend is a bridge to Android UIAutomator2. Future
iOS support should use the same boundary with a separate DVT/WDA backend line.
The driver backend is not a platform action layer and does not know Instagram,
TikTok, Teach, Scheduler, or Chatter.

This contract exists to prevent a product inside the product. Driver code may
connect, observe, and perform primitive operations. It must not become a custom
Android runtime with product policy hidden inside it.

## Implementations

First implementation:

`Uiautomator2Backend`

Bridge:

```
Python host -> uiautomator2 client -> device-side service -> UIAutomator
```

Planned iOS implementation line:

```
Python host -> Apple bridge/usbmux -> tunneld/RemoteXPC -> DVT screenshot
Python host -> Apple bridge/usbmux -> tunneld/RemoteXPC -> WDA/XCUITest
```

`ios-dvt` is expected to provide `snap` only. `ios-wda` is expected to provide
target tables and primitive `tap`, `text`, and gesture operations after a signed
WebDriverAgent runner is installed.

## Inputs

Common inputs:

- `device_id`,
- operation name,
- operation parameters,
- timeout,
- optional app/package context for status only.

Supported P1 operations:

- health/status,
- XML hierarchy dump,
- screenshot capture,
- current foreground app/package read,
- package info read,
- launchable app package/component list,
- open app package/component,
- tap coordinates or resolved target geometry,
- input text,
- back,
- home,
- swipe,
- wait/sleep.

## Outputs

Driver operations return structured results:

- `ok`,
- `status`,
- `device_id`,
- `backend`,
- `operation` when the operation has a named action envelope,
- `checked_at`,
- `elapsed_ms`,
- operation metadata,
- raw output refs when relevant,
- error code and detail when failed.

Error objects keep backward-compatible fields:

```json
{
  "code": "driver_unavailable",
  "detail": "uiautomator2 health probe failed without a structured error.",
  "category": "driver",
  "recoverable": true,
  "retryable": true,
  "recovery_hint": "Reinitialize the uiautomator2 bridge and retry once."
}
```

Only `code` and `detail` are required. `category`, `recoverable`,
`retryable`, and `recovery_hint` are S5 taxonomy fields for agents and future
preflight code.

Read-only app/package awareness uses the same envelope:

```json
{
  "ok": true,
  "status": "completed",
  "device_id": "<serial>",
  "backend": "uiautomator2",
  "operation": "app_current",
  "checked_at": "2026-06-13T00:00:00+00:00",
  "elapsed_ms": 12.3,
  "metadata": {
    "package": "com.example.app",
    "activity": ".MainActivity",
    "pid": 123
  },
  "error": null
}
```

`app_current` public metadata is limited to:

- `package`,
- `activity`,
- optional `pid`.

`package_info` public metadata is limited to:

- `package`,
- `version_name`,
- optional `version_code`.

`app_current` and `package_info` are read-only inspection operations. They must
not launch, stop, clear, install, uninstall, enumerate package inventory, or
infer platform/account readiness.

Launchable app lifecycle is a separate small surface:

- `apps` lists package/activity entries that can be launched from the device,
- `app_open` opens a dotted package name or exact `package/activity` component.

`app_open` is mutating and must be represented by a primitive receipt when
exposed through the high-level CLI. It must not guess display names such as
`instagram`, infer social-platform readiness, or encode app-specific flows.

## Invariants

- No platform business logic.
- No selector vault lookup.
- No Teach flow replay logic.
- No Scheduler state.
- No model/provider call.
- No custom product runtime hidden inside the driver.
- No phone touch outside explicit primitive operation.
- Machine-readable output must stay clean.
- Child process output is untrusted; public app/package JSON must expose only
  whitelisted metadata.
- Lifecycle maintenance commands may expose bounded diagnostics such as
  returncode and output-present flags, but not raw stdout/stderr.
- App/package reads contain no platform business logic and no account semantics.
- App open/listing contains no display-name resolver, no fuzzy social aliases,
  and no platform workflow semantics.

## Failure Modes

`snap-tap` uses `snap_tap.backends.contracts.DriverError` as the shared
structured error envelope for backend and shared phone-spine layers.
Snapshot-specific codes listed here are owned by snapshot contracts such as
`raw_snapshot_capture.v1` and `semantic_snapshot.v1`; driver backend operations
must not emit them directly.

- `device_offline`
- `driver_unavailable`
- `driver_conflict`
- `driver_timeout`
- `driver_lifecycle_failed`
- `driver_probe_failed`
- `dump_failed`
- `screenshot_failed`
- `snapshot_dump_failed`
- `snapshot_empty`
- `snapshot_parse_failed`
- `snapshot_evidence_missing`
- `snapshot_foreground_unknown`
- `latest_snapshot_ref_invalid`
- `latest_snap_source_missing`
- `latest_snap_source_invalid`
- `latest_snap_source_device_mismatch`
- `latest_snap_source_session_mismatch`
- `latest_snap_source_write_failed`
- `latest_snap_source_unsupported_version`
- `latest_snap_source_target_invalid`
- `latest_snap_source_target_missing`
- `latest_snap_source_target_not_tappable`
- `explicit_snapshot_source_missing`
- `explicit_snapshot_source_invalid`
- `explicit_snapshot_source_unsupported_version`
- `explicit_snapshot_source_device_mismatch`
- `app_unavailable`
- `permission_or_popup_blocked`
- `tap_failed`
- `input_failed`
- `navigation_failed`
- `primitive_target_stale`
- `device_required`
- `invalid_arguments`
- `unsupported_operation`

S5 taxonomy rules:

- `driver_unavailable` is the only driver-boundary error that may trigger
  automatic recovery in P1.R1.
- `device_offline`, `driver_conflict`, and `driver_timeout` fail closed without
  recovery.
- Malformed/empty child probe output maps to `driver_probe_failed` and fails
  closed without recovery.
- Operation failures such as `dump_failed`, `screenshot_failed`, and
  `app_unavailable` fail closed without hidden recovery.
- Lifecycle and argument failures such as `driver_lifecycle_failed`,
  `device_required`, `invalid_arguments`, and `unsupported_operation` fail
  closed without hidden recovery.
- Future touch/write failures must not blind-retry at the driver boundary.
- Primitive guard failures such as `primitive_target_stale` are non-retryable at
  the operation boundary; capture a fresh snapshot and resolve the target again.
- Latest snap source failures are non-retryable at the tap operation boundary;
  run `snap-tap snap` again for the requested device/session before tapping.

## Recovery

P1.R1.S5 allows a bounded internal recovery path for read/status driver
operations only.

Allowed recovery:

```
python -m uiautomator2 -s <serial> init
```

The parent process must:

- normalize serial/package before subprocess execution,
- invoke subprocesses as argument lists, never shell strings,
- time-bound recovery,
- retry the original read/status operation at most once,
- expose recovery metadata instead of hiding the recovery event.

Recovery metadata may include:

- `attempt`,
- `recovery_attempted`,
- `recovery_ok`,
- `recovery_operation`,
- `recovery_elapsed_ms`,
- `recovered_after_failure`,
- `recovery_error_code`.

Recovery is forbidden for app launch/stop, phone reboot, ADB server reset,
platform/account readiness, Scheduler/Teach policy, and any future phone-touch
or write primitive.

## Deferred Backends

`AdbFallbackBackend` may exist later for debug/fallback reads or emergency
operations.

`CustomAndroidDriverBackend` is forbidden in P1 unless a future ADR accepts
live evidence that `uiautomator2` cannot satisfy the product spine.
