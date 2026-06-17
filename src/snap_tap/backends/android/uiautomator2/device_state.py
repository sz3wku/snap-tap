from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

STATE_TRUE = "true"
STATE_FALSE = "false"
STATE_UNKNOWN = "unknown"


def read_device_state(device: object) -> dict[str, str]:
    info = _read_info(device)
    window_text = _safe_shell_text(device, ["dumpsys", "window"])
    trust_text = _safe_shell_text(device, ["dumpsys", "trust"])
    info_state = state_from_info(info)
    window_state = parse_window_state(window_text)
    trust_state = parse_trust_state(trust_text)
    return {
        "screen_on": _first_known(
            info_state.get("screen_on"),
            window_state.get("screen_on"),
        ),
        "keyguard_locked": _first_known(
            window_state.get("keyguard_locked"),
            trust_state.get("keyguard_locked"),
        ),
        "keyguard_secure": _first_known(window_state.get("keyguard_secure")),
    }


def state_from_info(info: object) -> dict[str, str]:
    if not isinstance(info, Mapping):
        return {"screen_on": STATE_UNKNOWN}
    return {"screen_on": _truth_string(info.get("screenOn"))}


def dimensions_from_info(info: object) -> tuple[int | None, int | None]:
    if not isinstance(info, Mapping):
        return None, None
    return _positive_int(info.get("displayWidth")), _positive_int(
        info.get("displayHeight")
    )


def parse_window_state(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    return {
        "screen_on": _screen_on_from_window(text),
        "keyguard_locked": _keyguard_locked_from_window(text),
        "keyguard_secure": _keyguard_secure_from_window(text),
    }


def parse_trust_state(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    match = re.search(r"\bdeviceLocked=(0|1|true|false)\b", text, re.IGNORECASE)
    if match is None:
        return {}
    return {"keyguard_locked": _truth_string(match.group(1))}


def is_true(value: object) -> bool:
    return value is True or value == STATE_TRUE


def is_false(value: object) -> bool:
    return value is False or value == STATE_FALSE


def _read_info(device: object) -> object:
    info = getattr(device, "info", None)
    if callable(info):
        return info()
    return info


def _safe_shell_text(device: object, command: Sequence[str]) -> str | None:
    shell = getattr(device, "shell", None)
    if not callable(shell):
        return None
    try:
        result = shell(list(command), timeout=3)
    except TypeError:
        try:
            result = shell(" ".join(command))
        except Exception:
            return None
    except Exception:
        return None
    return _shell_output_text(result)


def _shell_output_text(result: object) -> str | None:
    output = getattr(result, "output", result)
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    if isinstance(output, str):
        return output
    if isinstance(result, tuple) and result:
        first = result[0]
        if isinstance(first, bytes):
            return first.decode("utf-8", errors="replace")
        if isinstance(first, str):
            return first
    return None


def _screen_on_from_window(text: str) -> str:
    if re.search(r"\bscreenState=SCREEN_STATE_ON\b", text):
        return STATE_TRUE
    if re.search(r"\bscreenState=SCREEN_STATE_OFF\b", text):
        return STATE_FALSE
    if re.search(r"\bmScreenOnFully=true\b|\bmAwake=true\b", text):
        return STATE_TRUE
    if re.search(r"\bmScreenOnFully=false\b|\bmAwake=false\b", text):
        return STATE_FALSE
    return STATE_UNKNOWN


def _keyguard_locked_from_window(text: str) -> str:
    for pattern in (
        r"\bisKeyguardShowing=(true|false)\b",
        r"\bmIsShowing=(true|false)\b",
        r"\bisKeyguardLocked=(true|false)\b",
        r"\bmShowingLockscreen=(true|false)\b",
        r"\bmDreamingLockscreen=(true|false)\b",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            return _truth_string(match.group(1))
    return STATE_UNKNOWN


def _keyguard_secure_from_window(text: str) -> str:
    for pattern in (
        r"\bsecure=(true|false)\b",
        r"\bmSecure=(true|false)\b",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            return _truth_string(match.group(1))
    return STATE_UNKNOWN


def _truth_string(value: object) -> str:
    if isinstance(value, bool):
        return STATE_TRUE if value else STATE_FALSE
    if isinstance(value, int) and not isinstance(value, bool):
        if value == 1:
            return STATE_TRUE
        if value == 0:
            return STATE_FALSE
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return STATE_TRUE
        if normalized in {"false", "0", "no", "off"}:
            return STATE_FALSE
    return STATE_UNKNOWN


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None


def _first_known(*values: object) -> str:
    for value in values:
        if value in {STATE_TRUE, STATE_FALSE}:
            return str(value)
    return STATE_UNKNOWN


__all__ = [
    "STATE_FALSE",
    "STATE_TRUE",
    "STATE_UNKNOWN",
    "dimensions_from_info",
    "is_false",
    "is_true",
    "parse_trust_state",
    "parse_window_state",
    "read_device_state",
    "state_from_info",
]
