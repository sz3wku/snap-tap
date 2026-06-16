from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite

from snap_tap.snapshots.manifest_source_types import invalid_manifest_source


def mapping(value: object, field_name: str) -> Mapping[object, object]:
    if not isinstance(value, Mapping):
        raise invalid_manifest_source(f"{field_name} must be an object.")
    return value


def sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise invalid_manifest_source(f"{field_name} must be a list.")
    return value


def required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise invalid_manifest_source(f"{field_name} must be text.")
    normalized = value.strip()
    if not normalized:
        raise invalid_manifest_source(f"{field_name} must not be empty.")
    if normalized != value:
        raise invalid_manifest_source(f"{field_name} must already be normalized.")
    return normalized


def optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return required_text(value, field_name)


def non_negative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise invalid_manifest_source(f"{field_name} must be a non-negative integer.")
    return value


def optional_positive_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    integer = non_negative_int(value, field_name)
    if integer <= 0:
        raise invalid_manifest_source(f"{field_name} must be positive.")
    return integer


def number(value: object, field_name: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise invalid_manifest_source(f"{field_name} must be a finite number.")
    return float(value)


def boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise invalid_manifest_source(f"{field_name} must be a boolean.")
    return value


def optional_bool(value: object) -> bool:
    if value is None:
        return False
    return boolean(value, "element.scrollable")


def sha256_text(value: object, field_name: str) -> str:
    text = required_text(value, field_name)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise invalid_manifest_source(f"{field_name} must be lowercase sha256 hex.")
    return text


def reject_json_constant(value: str) -> object:
    raise ValueError(f"Snapshot manifest JSON contains unsupported constant {value}.")
