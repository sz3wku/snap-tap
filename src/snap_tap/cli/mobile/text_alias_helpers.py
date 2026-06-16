from __future__ import annotations

import hashlib

from snap_tap.primitives import PrimitiveReceipt, invalid_request_receipt


def blocked_text_receipt(
    *,
    device_id: str | None,
    request: dict[str, object],
    detail: str,
    operation: str,
    code: str = "primitive_invalid_request",
) -> PrimitiveReceipt:
    return invalid_request_receipt(
        device_id=device_id,
        request=request,
        code=code,
        detail=detail,
        operation=operation,
    )


def safe_text_request_metadata(
    *,
    mode: str,
    device_id: str | None,
    target_id: str | None,
    session_id: str,
    text: str | None,
) -> dict[str, object]:
    return {
        "operation": mode,
        "device_id": device_id,
        "target_id": target_id,
        "session_id": session_id,
        "mode": mode,
        "text_length": len(text) if isinstance(text, str) else 0,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()
        if isinstance(text, str)
        else None,
    }


def target_id_error(target_id: str) -> str | None:
    if (
        len(target_id) < 4
        or not target_id.startswith("e")
        or not target_id[1:].isdigit()
    ):
        return "Target id must look like e001."
    return None


def normalized_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if not value or not value.strip() or len(value) > 4096:
        return None
    if "\x00" in value:
        return None
    return value
