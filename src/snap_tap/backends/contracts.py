"""Stable backend contracts shared by Android, iOS, and test fakes.

Concrete backend implementations live under platform-specific packages. This
module is the public import surface for driver result types, protocols, error
metadata, and safe selection helpers.
"""

from __future__ import annotations

from snap_tap.backends._shared.app_awareness import (
    DriverAppAwareness,
    DriverAppAwarenessReader,
    normalize_package,
    read_device_app_current,
    read_device_package_info,
)
from snap_tap.backends._shared.app_lifecycle import (
    DriverAppCatalog,
    DriverAppEntry,
    DriverAppLifecycle,
    DriverAppOpen,
    read_device_launchable_apps,
)
from snap_tap.backends._shared.errors import (
    ERROR_SPECS,
    UNKNOWN_ERROR_SPEC,
    DriverError,
    ErrorSpec,
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
    DriverTapXmlDump,
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
    "DriverAppCatalog",
    "DriverAppEntry",
    "DriverAppLifecycle",
    "DriverAppOpen",
    "DriverBackend",
    "DriverError",
    "DriverHealth",
    "DriverLifecycleResult",
    "DriverLifecycleRunner",
    "DriverNavigation",
    "DriverScreenshot",
    "DriverScreenshotCapturer",
    "DriverTap",
    "DriverTapXmlDump",
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
    "read_device_launchable_apps",
    "read_device_package_info",
]
