from __future__ import annotations

from snap_tap.snapshots import SnapshotBounds, SnapshotElement


ROLE_VALUES = ["button", "tab", "input", "text", "image", "list_item", "unknown"]


def test_semantic_role_enum_is_exact_s1_contract() -> None:
    from snap_tap.semantics.roles import SemanticRole

    assert [role.value for role in SemanticRole] == ROLE_VALUES


def test_semantic_role_precedence_uses_stronger_roles_before_button() -> None:
    from snap_tap.semantics.roles import SemanticRole, classify_semantic_role

    assert classify_semantic_role(_element(class_name="android.widget.EditText")) == (
        SemanticRole.INPUT
    )
    assert classify_semantic_role(_element(resource_id="com.example:id/home_tab")) == (
        SemanticRole.TAB
    )
    assert classify_semantic_role(_element(resource_id="com.example:id/feed_item")) == (
        SemanticRole.LIST_ITEM
    )


def test_semantic_role_button_then_image_then_text_then_unknown() -> None:
    from snap_tap.semantics.roles import SemanticRole, classify_semantic_role

    assert classify_semantic_role(_element(class_name="android.widget.ImageButton")) == (
        SemanticRole.BUTTON
    )
    assert classify_semantic_role(
        _element(class_name="android.widget.ImageView", clickable=False)
    ) == SemanticRole.IMAGE
    assert classify_semantic_role(
        _element(class_name="android.widget.TextView", clickable=False)
    ) == SemanticRole.TEXT
    assert classify_semantic_role(
        _element(enabled=False, clickable=True)
    ) == SemanticRole.UNKNOWN


def test_semantic_role_broad_button_fallback_requires_visible_enabled_clickable() -> None:
    from snap_tap.semantics.roles import SemanticRole, classify_semantic_role

    assert classify_semantic_role(_element()) == SemanticRole.BUTTON
    assert classify_semantic_role(_element(visible=False)) == SemanticRole.UNKNOWN
    assert classify_semantic_role(_element(enabled=False)) == SemanticRole.UNKNOWN
    assert classify_semantic_role(_element(clickable=False)) == SemanticRole.UNKNOWN


def _element(
    *,
    source_index: int = 0,
    visible: bool = True,
    enabled: bool = True,
    clickable: bool = True,
    class_name: str | None = None,
    resource_id: str | None = None,
    package: str | None = "com.example",
) -> SnapshotElement:
    return SnapshotElement(
        source_index=source_index,
        depth=0,
        bounds=SnapshotBounds(
            left=10,
            top=20,
            right=110,
            bottom=220,
            width=100,
            height=200,
            center_x=60.0,
            center_y=120.0,
        ),
        visible=visible,
        enabled=enabled,
        clickable=clickable,
        class_name=class_name,
        resource_id=resource_id,
        package=package,
    )
