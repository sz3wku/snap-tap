from __future__ import annotations

from snap_tap.backends.android.uiautomator2.device_state import (
    parse_trust_state,
    parse_window_state,
    read_device_state,
)


class _ShellResult:
    def __init__(self, output: str) -> None:
        self.output = output


class _Device:
    info = {"screenOn": True}

    def shell(self, command: list[str], timeout: int = 3) -> _ShellResult:
        assert timeout == 3
        if command == ["dumpsys", "window"]:
            return _ShellResult(
                "screenState=SCREEN_STATE_ON\n"
                "mAwake=true\n"
                "showing=false, secure=false, deviceHasKeyguard=true\n"
            )
        if command == ["dumpsys", "trust"]:
            return _ShellResult("deviceLocked=0\nraw-secret-ish-text")
        raise AssertionError(f"unexpected command: {command!r}")


class _SwipeKeyguardDevice:
    info = {"screenOn": True}

    def shell(self, command: list[str], timeout: int = 3) -> _ShellResult:
        if command == ["dumpsys", "window"]:
            return _ShellResult(
                "KeyguardServiceDelegate\n"
                "  showing=true\n"
                "  secure=false\n"
                "  screenState=SCREEN_STATE_ON\n"
                "  KeyguardStateMonitor\n"
                "    mIsShowing=true\n"
                "isKeyguardShowing=true\n"
            )
        if command == ["dumpsys", "trust"]:
            return _ShellResult("deviceLocked=0\n")
        raise AssertionError(f"unexpected command: {command!r}")


def test_parse_window_state_reads_screen_lock_and_secure_flags() -> None:
    state = parse_window_state(
        "screenState=SCREEN_STATE_ON\n"
        "isKeyguardShowing=true\n"
        "showing=true, secure=true, deviceHasKeyguard=true\n"
    )

    assert state == {
        "screen_on": "true",
        "keyguard_locked": "true",
        "keyguard_secure": "true",
    }


def test_parse_trust_state_reads_device_locked_without_raw_output() -> None:
    assert parse_trust_state("deviceLocked=0\nSensitive surrounding text") == {
        "keyguard_locked": "false"
    }


def test_read_device_state_exports_only_whitelisted_metadata() -> None:
    state = read_device_state(_Device())

    assert state == {
        "screen_on": "true",
        "keyguard_locked": "false",
        "keyguard_secure": "false",
    }
    assert "raw-secret-ish-text" not in str(state)


def test_read_device_state_prefers_visible_keyguard_over_trust_unlocked() -> None:
    state = read_device_state(_SwipeKeyguardDevice())

    assert state == {
        "screen_on": "true",
        "keyguard_locked": "true",
        "keyguard_secure": "false",
    }
