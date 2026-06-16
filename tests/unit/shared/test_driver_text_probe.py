from __future__ import annotations

from snap_tap.backends.android.uiautomator2.text_probe import focused_text, safe_focused_text, text_was_applied


def test_focused_text_reads_focused_node_text() -> None:
    xml = (
        '<hierarchy><node focused="false" text="old" />'
        '<node focused="true" text="hakar_fast" /></hierarchy>'
    )

    assert focused_text(xml) == "hakar_fast"


def test_safe_focused_text_returns_error_name_for_malformed_xml() -> None:
    text, error = safe_focused_text("<hierarchy>")

    assert text is None
    assert error == "ParseError"


def test_text_was_applied_accepts_replace_exact_match() -> None:
    assert text_was_applied("old", "new text", "new text", replace=True) is True
    assert text_was_applied("old", "new text extra", "new text", replace=True) is False
    assert text_was_applied(None, "new text", "new text", replace=True) is False


def test_text_was_applied_accepts_input_change_containing_payload() -> None:
    assert text_was_applied("", "hello", "hello", replace=False) is True
    assert text_was_applied("old ", "old hello", "hello", replace=False) is True
    assert text_was_applied("old", "old", "hello", replace=False) is False
    assert text_was_applied(None, "hello", "hello", replace=False) is False
