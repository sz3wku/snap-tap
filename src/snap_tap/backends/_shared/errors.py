from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorSpec:
    category: str
    recoverable: bool
    retryable: bool
    recovery_hint: str


ERROR_SPECS: dict[str, ErrorSpec] = {
    "device_offline": ErrorSpec(
        category="device",
        recoverable=False,
        retryable=False,
        recovery_hint="Connect the device and make sure ADB reports state 'device'.",
    ),
    "driver_conflict": ErrorSpec(
        category="selection",
        recoverable=False,
        retryable=False,
        recovery_hint="Pass an explicit device serial or use --all.",
    ),
    "driver_timeout": ErrorSpec(
        category="timeout",
        recoverable=False,
        retryable=False,
        recovery_hint="Increase timeout or inspect driver health before retrying.",
    ),
    "driver_unavailable": ErrorSpec(
        category="driver",
        recoverable=True,
        retryable=True,
        recovery_hint="Reinitialize the uiautomator2 bridge and retry once.",
    ),
    "driver_lifecycle_failed": ErrorSpec(
        category="driver",
        recoverable=False,
        retryable=False,
        recovery_hint="Run mobile doctor/init explicitly and inspect the result.",
    ),
    "driver_probe_failed": ErrorSpec(
        category="driver",
        recoverable=False,
        retryable=False,
        recovery_hint="Inspect the driver probe boundary before retrying.",
    ),
    "dump_failed": ErrorSpec(
        category="operation",
        recoverable=False,
        retryable=False,
        recovery_hint="Inspect driver status and retry after the screen is stable.",
    ),
    "screenshot_failed": ErrorSpec(
        category="operation",
        recoverable=False,
        retryable=False,
        recovery_hint="Inspect driver status and retry after the screen is stable.",
    ),
    "snapshot_dump_failed": ErrorSpec(
        category="snapshot",
        recoverable=False,
        retryable=False,
        recovery_hint="Inspect driver XML output and retry after the screen is stable.",
    ),
    "snapshot_empty": ErrorSpec(
        category="snapshot",
        recoverable=False,
        retryable=False,
        recovery_hint="Capture a fresh snapshot after the screen is visible.",
    ),
    "snapshot_parse_failed": ErrorSpec(
        category="snapshot",
        recoverable=False,
        retryable=False,
        recovery_hint="Re-run snapshot capture and inspect driver XML if parsing keeps failing.",
    ),
    "snapshot_evidence_missing": ErrorSpec(
        category="snapshot",
        recoverable=False,
        retryable=False,
        recovery_hint="Re-run snapshot capture with an explicit output directory.",
    ),
    "snapshot_foreground_unknown": ErrorSpec(
        category="snapshot",
        recoverable=False,
        retryable=False,
        recovery_hint="Inspect current app/package awareness before using the snapshot.",
    ),
    "latest_snapshot_ref_invalid": ErrorSpec(
        category="snapshot",
        recoverable=False,
        retryable=False,
        recovery_hint="Fix the latest snapshot session or capture a fresh snap.",
    ),
    "latest_snap_source_missing": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Run snap-tap snap for this device/session before tapping.",
    ),
    "latest_snap_source_invalid": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Run snap-tap snap again to refresh the target source.",
    ),
    "latest_snap_source_device_mismatch": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Run snap-tap snap for the requested device before tapping.",
    ),
    "latest_snap_source_session_mismatch": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Use the matching session or run snap-tap snap again.",
    ),
    "latest_snap_source_write_failed": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Inspect local cache permissions and run snap-tap snap again.",
    ),
    "latest_snap_source_unsupported_version": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Run snap-tap snap again with the current CLI version.",
    ),
    "latest_snap_source_target_invalid": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Use a target id from the latest snap-tap snap table.",
    ),
    "latest_snap_source_target_missing": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Run snap-tap snap again and choose a visible tap target.",
    ),
    "latest_snap_source_target_not_tappable": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Choose a tap target from snap-tap snap, not input or scroll.",
    ),
    "primitive_target_not_tappable": ErrorSpec(
        category="primitive",
        recoverable=False,
        retryable=False,
        recovery_hint="Choose a clickable tap target from snap-tap snap.",
    ),
    "explicit_snapshot_source_missing": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Pass a valid snapshot manifest path or capture directory.",
    ),
    "explicit_snapshot_source_invalid": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Capture a fresh snapshot and use its manifest.json.",
    ),
    "explicit_snapshot_source_unsupported_version": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Use a snapshot_manifest.v1 manifest.",
    ),
    "explicit_snapshot_source_device_mismatch": ErrorSpec(
        category="target_source",
        recoverable=False,
        retryable=False,
        recovery_hint="Use a manifest captured from the requested device.",
    ),
    "app_unavailable": ErrorSpec(
        category="app",
        recoverable=False,
        retryable=False,
        recovery_hint="Verify the current app/package explicitly.",
    ),
    "permission_or_popup_blocked": ErrorSpec(
        category="screen_blocker",
        recoverable=False,
        retryable=False,
        recovery_hint="Resolve the visible permission or popup blocker first.",
    ),
    "tap_failed": ErrorSpec(
        category="primitive",
        recoverable=False,
        retryable=False,
        recovery_hint="Capture a fresh snapshot and resolve the target again.",
    ),
    "input_failed": ErrorSpec(
        category="primitive",
        recoverable=False,
        retryable=False,
        recovery_hint="Inspect input readiness and retry only if no write occurred.",
    ),
    "navigation_failed": ErrorSpec(
        category="primitive",
        recoverable=False,
        retryable=False,
        recovery_hint="Inspect current screen state before retrying navigation.",
    ),
    "primitive_target_stale": ErrorSpec(
        category="primitive",
        recoverable=False,
        retryable=False,
        recovery_hint="Capture a fresh snapshot and resolve the target again.",
    ),
    "primitive_app_open_foreground_mismatch": ErrorSpec(
        category="primitive",
        recoverable=False,
        retryable=False,
        recovery_hint="Inspect the post-launch snapshot and current app before retrying.",
    ),
    "primitive_app_open_foreground_unknown": ErrorSpec(
        category="primitive",
        recoverable=False,
        retryable=False,
        recovery_hint="Capture a fresh snapshot or inspect the current app before retrying.",
    ),
    "device_required": ErrorSpec(
        category="selection",
        recoverable=False,
        retryable=False,
        recovery_hint="Pass an explicit device serial for lifecycle operations.",
    ),
    "invalid_arguments": ErrorSpec(
        category="arguments",
        recoverable=False,
        retryable=False,
        recovery_hint="Fix the command arguments before retrying.",
    ),
    "unsupported_operation": ErrorSpec(
        category="arguments",
        recoverable=False,
        retryable=False,
        recovery_hint="Use a supported driver operation.",
    ),
}


UNKNOWN_ERROR_SPEC = ErrorSpec(
    category="unknown",
    recoverable=False,
    retryable=False,
    recovery_hint="Inspect the structured driver result before retrying.",
)


@dataclass(frozen=True)
class DriverError:
    code: str
    detail: str
    category: str | None = None
    recoverable: bool | None = None
    retryable: bool | None = None
    recovery_hint: str | None = None

    def __post_init__(self) -> None:
        spec = error_spec(self.code)
        if self.category is None:
            object.__setattr__(self, "category", spec.category)
        if self.recoverable is None:
            object.__setattr__(self, "recoverable", spec.recoverable)
        if self.retryable is None:
            object.__setattr__(self, "retryable", spec.retryable)
        if self.recovery_hint is None:
            object.__setattr__(self, "recovery_hint", spec.recovery_hint)


def error_spec(code: str) -> ErrorSpec:
    return ERROR_SPECS.get(code, UNKNOWN_ERROR_SPEC)


def is_driver_recoverable(code: str) -> bool:
    spec = error_spec(code)
    return spec.recoverable and spec.retryable
