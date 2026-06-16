from __future__ import annotations

from snap_tap.backends._shared.app_awareness import (
    DriverAppAwareness,
    DriverAppAwarenessReader,
    normalize_package,
    read_device_app_current,
    read_device_package_info,
)
from snap_tap.backends._shared.errors import (
    ERROR_SPECS,
    DriverError,
    ErrorSpec,
    UNKNOWN_ERROR_SPEC,
    error_spec,
    is_driver_recoverable,
)
from snap_tap.backends._shared.health import (
    DriverBackend,
    DriverHealth,
    check_device_health,
)
from snap_tap.backends._shared.results import (
    DriverLifecycleResult,
    DriverLifecycleRunner,
    DriverNavigation,
    DriverTap,
    DriverText,
    DriverXmlDump,
    DriverXmlDumper,
)
from snap_tap.backends._shared.screenshot import (
    DriverScreenshot,
    DriverScreenshotCapturer,
    capture_device_screenshot,
)

__all__ = [
    "DriverAppAwareness",
    "DriverAppAwarenessReader",
    "DriverBackend",
    "DriverError",
    "DriverHealth",
    "DriverLifecycleResult",
    "DriverLifecycleRunner",
    "DriverNavigation",
    "DriverScreenshot",
    "DriverScreenshotCapturer",
    "DriverTap",
    "DriverText",
    "DriverXmlDump",
    "DriverXmlDumper",
    "ERROR_SPECS",
    "ErrorSpec",
    "UNKNOWN_ERROR_SPEC",
    "capture_device_screenshot",
    "check_device_health",
    "error_spec",
    "is_driver_recoverable",
    "normalize_package",
    "read_device_app_current",
    "read_device_package_info",
]
