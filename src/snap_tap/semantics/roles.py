from __future__ import annotations

import re

from snap_tap.semantics.models import SemanticRole
from snap_tap.snapshots import SnapshotElement

_TOKEN_RE = re.compile(r"[a-z0-9]+")
__all__ = ["SemanticRole", "classify_semantic_role"]


def classify_semantic_role(element: SnapshotElement) -> SemanticRole:
    class_name = (element.class_name or "").lower()
    resource_tokens = _tokens(element.resource_id)

    if _is_input(class_name, resource_tokens):
        return SemanticRole.INPUT
    if _is_tab(class_name, resource_tokens):
        return SemanticRole.TAB
    if _is_list_item(class_name, resource_tokens):
        return SemanticRole.LIST_ITEM
    if _is_button_class(class_name) or (
        element.visible and element.enabled and element.clickable
    ):
        return SemanticRole.BUTTON
    if _is_image_class(class_name):
        return SemanticRole.IMAGE
    if _is_text_class(class_name):
        return SemanticRole.TEXT
    return SemanticRole.UNKNOWN


def _is_input(class_name: str, resource_tokens: set[str]) -> bool:
    return (
        "edittext" in class_name
        or "textinputedittext" in class_name
        or bool(resource_tokens & {"input", "edit", "field"})
    )


def _is_tab(class_name: str, resource_tokens: set[str]) -> bool:
    return (
        class_name.endswith(".tab")
        or "tablayout" in class_name
        or "tabwidget" in class_name
        or "tabitem" in class_name
        or "tab" in resource_tokens
    )


def _is_list_item(class_name: str, resource_tokens: set[str]) -> bool:
    return (
        "listitem" in class_name
        or class_name.endswith(".row")
        or class_name.endswith(".cell")
        or bool(resource_tokens & {"row", "item", "cell", "listitem"})
    )


def _is_button_class(class_name: str) -> bool:
    return "imagebutton" in class_name or class_name.endswith("button")


def _is_image_class(class_name: str) -> bool:
    return "imageview" in class_name


def _is_text_class(class_name: str) -> bool:
    return "textview" in class_name or "statictext" in class_name


def _tokens(value: str | None) -> set[str]:
    if value is None:
        return set()
    return set(_TOKEN_RE.findall(value.lower()))
