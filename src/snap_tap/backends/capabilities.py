from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PlatformName = Literal["android", "ios"]
CapabilityName = Literal[
    "discover",
    "snap",
    "targets",
    "tap",
    "text",
    "swipe",
    "navigation",
    "app_awareness",
]


@dataclass(frozen=True)
class BackendRequirement:
    code: str
    detail: str
    blocks: tuple[CapabilityName, ...]
    operator_action: str | None = None

    def blocks_capability(self, capability: CapabilityName) -> bool:
        return capability in self.blocks


@dataclass(frozen=True)
class BackendCapabilities:
    platform: PlatformName
    backend_name: str
    supported: frozenset[CapabilityName]
    requirements: tuple[BackendRequirement, ...] = ()
    notes: tuple[str, ...] = ()

    def supports(self, capability: CapabilityName) -> bool:
        return capability in self.supported

    def blocking_requirements(
        self,
        capability: CapabilityName,
    ) -> tuple[BackendRequirement, ...]:
        return tuple(
            requirement
            for requirement in self.requirements
            if requirement.blocks_capability(capability)
        )


_ANDROID_UIAUTOMATOR2_SUPPORTED: frozenset[CapabilityName] = frozenset(
    (
        "discover",
        "snap",
        "targets",
        "tap",
        "text",
        "swipe",
        "navigation",
        "app_awareness",
    )
)

_IOS_DVT_SNAP_SUPPORTED: frozenset[CapabilityName] = frozenset(
    (
        "discover",
        "snap",
    )
)

_IOS_WDA_SUPPORTED: frozenset[CapabilityName] = frozenset(
    (
        "discover",
        "snap",
        "targets",
        "tap",
        "text",
        "swipe",
        "navigation",
    )
)

IOS_DEVELOPER_MODE = BackendRequirement(
    code="ios_developer_mode_required",
    detail="iOS Developer Mode must be enabled on the device.",
    blocks=("snap", "targets", "tap", "text", "swipe", "navigation"),
    operator_action=(
        "Enable Developer Mode on the iPhone and confirm after reboot."
    ),
)

IOS_DEVELOPER_DISK_IMAGE = BackendRequirement(
    code="ios_developer_disk_image_required",
    detail="A DeveloperDiskImage must be mounted before iOS developer services run.",
    blocks=("snap", "targets", "tap", "text", "swipe", "navigation"),
    operator_action="Run the iOS setup/doctor flow with the device unlocked.",
)

IOS_ADMIN_TUNNELD = BackendRequirement(
    code="ios_admin_tunneld_required",
    detail="RemoteXPC/tunneld is required for modern iOS developer services.",
    blocks=("snap", "targets", "tap", "text", "swipe", "navigation"),
    operator_action="Start pymobiledevice3 remote tunneld from Administrator PowerShell.",
)

IOS_WDA_RUNNER = BackendRequirement(
    code="ios_wda_runner_required",
    detail="A signed WebDriverAgent/XCUITest runner is required for iOS tap/input.",
    blocks=("targets", "tap", "text", "swipe", "navigation"),
    operator_action="Build, sign, and install WebDriverAgentRunner from Xcode.",
)


ANDROID_UIAUTOMATOR2_CAPABILITIES = BackendCapabilities(
    platform="android",
    backend_name="uiautomator2",
    supported=_ANDROID_UIAUTOMATOR2_SUPPORTED,
    notes=(
        "ADB is transport/lifecycle/fallback; UIAutomator2 owns observation "
        "and primitive action execution.",
    ),
)

IOS_DVT_SNAP_CAPABILITIES = BackendCapabilities(
    platform="ios",
    backend_name="ios-dvt",
    supported=_IOS_DVT_SNAP_SUPPORTED,
    requirements=(
        IOS_DEVELOPER_MODE,
        IOS_DEVELOPER_DISK_IMAGE,
        IOS_ADMIN_TUNNELD,
    ),
    notes=(
        "DVT screenshot proves the iOS snap path but does not provide target "
        "tables or tap/input primitives.",
    ),
)

IOS_WDA_CAPABILITIES = BackendCapabilities(
    platform="ios",
    backend_name="ios-wda",
    supported=_IOS_WDA_SUPPORTED,
    requirements=(
        IOS_DEVELOPER_MODE,
        IOS_DEVELOPER_DISK_IMAGE,
        IOS_ADMIN_TUNNELD,
        IOS_WDA_RUNNER,
    ),
    notes=(
        "WDA/XCUITest is the planned iOS target, tap, text, and gesture "
        "driver line after one-time signing/setup.",
    ),
)


def android_uiautomator2_capabilities() -> BackendCapabilities:
    return ANDROID_UIAUTOMATOR2_CAPABILITIES


def ios_dvt_snap_capabilities() -> BackendCapabilities:
    return IOS_DVT_SNAP_CAPABILITIES


def ios_wda_capabilities() -> BackendCapabilities:
    return IOS_WDA_CAPABILITIES
