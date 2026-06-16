from __future__ import annotations

from snap_tap.backends import (
    android_uiautomator2_capabilities,
    ios_dvt_snap_capabilities,
    ios_wda_capabilities,
)


def test_android_uiautomator2_supports_full_primitive_surface() -> None:
    capabilities = android_uiautomator2_capabilities()

    assert capabilities.platform == "android"
    assert capabilities.backend_name == "uiautomator2"
    assert capabilities.requirements == ()
    assert capabilities.supports("snap")
    assert capabilities.supports("targets")
    assert capabilities.supports("tap")
    assert capabilities.supports("text")
    assert capabilities.supports("navigation")


def test_ios_dvt_is_snap_only_and_blocks_snap_on_setup_gates() -> None:
    capabilities = ios_dvt_snap_capabilities()

    assert capabilities.platform == "ios"
    assert capabilities.backend_name == "ios-dvt"
    assert capabilities.supports("discover")
    assert capabilities.supports("snap")
    assert not capabilities.supports("targets")
    assert not capabilities.supports("tap")

    snap_blockers = {
        requirement.code
        for requirement in capabilities.blocking_requirements("snap")
    }
    assert snap_blockers == {
        "ios_developer_mode_required",
        "ios_developer_disk_image_required",
        "ios_admin_tunneld_required",
    }


def test_ios_wda_declares_tap_input_and_wda_blockers() -> None:
    capabilities = ios_wda_capabilities()

    assert capabilities.platform == "ios"
    assert capabilities.backend_name == "ios-wda"
    assert capabilities.supports("targets")
    assert capabilities.supports("tap")
    assert capabilities.supports("text")
    assert capabilities.supports("swipe")

    tap_blockers = {
        requirement.code
        for requirement in capabilities.blocking_requirements("tap")
    }
    assert tap_blockers == {
        "ios_developer_mode_required",
        "ios_developer_disk_image_required",
        "ios_admin_tunneld_required",
        "ios_wda_runner_required",
    }
