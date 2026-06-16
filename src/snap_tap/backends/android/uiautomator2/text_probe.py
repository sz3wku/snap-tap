from __future__ import annotations

from xml.etree import ElementTree


def enable_fast_input(device: object) -> str:
    for name in ("set_input_ime", "set_fastinput_ime"):
        method = getattr(device, name, None)
        if not callable(method):
            continue
        try:
            method(True)
            return name
        except TypeError:
            method()
            return name
    return "unavailable"


def send_text(device: object, text: str, *, replace: bool) -> object:
    send_keys = getattr(device, "send_keys", None)
    if not callable(send_keys):
        raise RuntimeError("Connected device does not expose send_keys.")
    if replace:
        try:
            return send_keys(text, clear=True)
        except TypeError:
            clear_text = getattr(device, "clear_text", None)
            if not callable(clear_text):
                raise
            clear_text()
            return send_keys(text)
    return send_keys(text)


def safe_focused_text(xml: str) -> tuple[str | None, str | None]:
    try:
        return focused_text(xml), None
    except Exception as exc:
        return None, type(exc).__name__


def focused_text(xml: str) -> str | None:
    root = ElementTree.fromstring(xml)
    for node in root.iter("node"):
        if node.attrib.get("focused") == "true":
            return node.attrib.get("text") or ""
    return None


def text_was_applied(
    before_text: str | None,
    after_text: str | None,
    text: str,
    *,
    replace: bool,
) -> bool:
    if before_text is None or after_text is None:
        return False
    if replace:
        return after_text == text and after_text != before_text
    return after_text != before_text and text in after_text
