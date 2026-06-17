from __future__ import annotations

from pathlib import Path

from mobile_text_alias_helpers import (
    FakeTextExecutor,
    build_text_alias_app,
    json_payload,
    write_latest_text_source,
)
from typer.testing import CliRunner

from snap_tap.backends.android.uiautomator2.text import (
    TEXT_INPUT_MODE,
    TEXT_REPLACE_MODE,
)
from snap_tap.targets import read_latest_snap_source


def test_mobile_input_default_output_renders_after_snap_table(
    tmp_path: Path,
) -> None:
    write_latest_text_source(tmp_path)
    executor = FakeTextExecutor()
    result = CliRunner().invoke(
        build_text_alias_app(tmp_path, executor),
        [
            "input",
            "RFCN4010FCK",
            "e001",
            "--text",
            "hakar smoke",
        ],
    )

    assert result.exit_code == 0
    assert "targets: 0 tap | 1 input | 0 scroll areas | 1 visible" in result.stdout
    assert "e001" in result.stdout
    assert "Message" in result.stdout
    assert "primitive_receipt.v1" not in result.stdout
    assert "hakar smoke" not in result.stdout

    latest = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    assert latest.snapshot.snapshot_id == "after"
    assert [target.display_id for target in latest.targets] == ["e001"]


def test_mobile_input_json_returns_receipt_and_next_snap(
    tmp_path: Path,
) -> None:
    write_latest_text_source(tmp_path)
    before = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    executor = FakeTextExecutor()

    result = CliRunner().invoke(
        build_text_alias_app(tmp_path, executor),
        [
            "input",
            "RFCN4010FCK",
            "e001",
            "--text",
            "hakar smoke",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json_payload(result.stdout)
    assert payload["schema_version"] == "primitive_result.v1"
    assert payload["operation"] == TEXT_INPUT_MODE
    assert payload["receipt"]["schema_version"] == "primitive_receipt.v1"
    assert payload["receipt"]["after_snapshot"]["snapshot_id"] == "after"
    assert payload["next_snap"]["schema_version"] == "mobile_snap.v1"
    assert payload["next_snap"]["snapshot"]["snapshot_id"] == "after"
    after = read_latest_snap_source(
        device_id="RFCN4010FCK",
        session_id="default",
        cache_root=tmp_path,
    )
    assert before.snapshot.snapshot_id != "after"
    assert after.snapshot.snapshot_id == "after"


def test_mobile_input_id_builds_text_request_from_latest_source(
    tmp_path: Path,
) -> None:
    write_latest_text_source(tmp_path)
    executor = FakeTextExecutor()
    result = CliRunner().invoke(
        build_text_alias_app(tmp_path, executor),
        [
            "input",
            "RFCN4010FCK",
            "e001",
            "--text",
            "hakar smoke",
            "--json",
        ],
    )

    payload = json_payload(result.stdout)
    assert result.exit_code == 0
    assert payload["schema_version"] == "primitive_result.v1"
    assert payload["operation"] == TEXT_INPUT_MODE
    assert payload["receipt"]["schema_version"] == "primitive_receipt.v1"
    assert payload["receipt"]["operation"] == TEXT_INPUT_MODE
    assert payload["receipt"]["request"]["text_length"] == 11
    assert payload["next_snap"]["summary"]["input_count"] == 1
    assert "hakar smoke" not in result.stdout
    assert len(executor.calls) == 1
    request = executor.calls[0]
    assert request.text == "hakar smoke"
    assert request.mode == TEXT_INPUT_MODE
    assert request.signature.schema_version == "target_signature.v1"
    assert request.signature.display_id == "e001"
    assert request.signature.source_snapshot_id == "snap_mobile"


def test_mobile_replace_text_id_uses_replace_mode(tmp_path: Path) -> None:
    write_latest_text_source(tmp_path)
    executor = FakeTextExecutor()
    result = CliRunner().invoke(
        build_text_alias_app(tmp_path, executor),
        [
            "replace-text",
            "RFCN4010FCK",
            "e001",
            "--text",
            "new caption",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json_payload(result.stdout)
    assert payload["operation"] == TEXT_REPLACE_MODE
    assert payload["receipt"]["operation"] == TEXT_REPLACE_MODE
    assert payload["next_snap"]["schema_version"] == "mobile_snap.v1"
    assert "new caption" not in result.stdout
    assert executor.calls[0].mode == TEXT_REPLACE_MODE


def test_mobile_text_alias_invalid_inputs_fail_before_executor(
    tmp_path: Path,
) -> None:
    executor = FakeTextExecutor()
    app = build_text_alias_app(tmp_path, executor)
    runner = CliRunner()

    malformed_id = runner.invoke(
        app,
        ["input", "save", "--device", "RFCN4010FCK", "--text", "hello", "--json"],
    )
    bad_serial = runner.invoke(
        app,
        ["input", "e001", "--device", "bad serial", "--text", "hello", "--json"],
    )
    bad_session = runner.invoke(
        app,
        [
            "input",
            "e001",
            "--device",
            "RFCN4010FCK",
            "--session",
            "../bad",
            "--text",
            "hello",
            "--json",
        ],
    )
    missing_source = runner.invoke(
        app,
        ["input", "e001", "--device", "RFCN4010FCK", "--text", "hello", "--json"],
    )

    assert malformed_id.exit_code == 1
    assert bad_serial.exit_code == 1
    assert bad_session.exit_code == 1
    assert missing_source.exit_code == 1
    assert json_payload(malformed_id.stdout)["receipt"]["error"]["code"] == (
        "primitive_invalid_request"
    )
    assert json_payload(bad_serial.stdout)["receipt"]["error"]["code"] == (
        "primitive_invalid_request"
    )
    assert json_payload(bad_session.stdout)["receipt"]["error"]["code"] == (
        "latest_snapshot_ref_invalid"
    )
    assert json_payload(missing_source.stdout)["receipt"]["error"]["code"] == (
        "latest_snap_source_missing"
    )
    assert json_payload(malformed_id.stdout)["next_snap"] is None
    assert executor.calls == []


def test_mobile_text_alias_rejects_positional_serial_with_device_option(
    tmp_path: Path,
) -> None:
    write_latest_text_source(tmp_path)
    executor = FakeTextExecutor()

    result = CliRunner().invoke(
        build_text_alias_app(tmp_path, executor),
        [
            "input",
            "RFCN4010FCK",
            "e001",
            "--device",
            "RFCN4010FCK",
            "--text",
            "hello",
            "--json",
        ],
    )

    payload = json_payload(result.stdout)
    assert result.exit_code == 1
    assert payload["schema_version"] == "primitive_result.v1"
    assert payload["receipt"]["error"]["code"] == "invalid_arguments"
    assert payload["next_snap"] is None
    assert executor.calls == []


def test_mobile_text_alias_non_input_source_fails_before_executor(
    tmp_path: Path,
) -> None:
    write_latest_text_source(tmp_path, input_target=False)
    executor = FakeTextExecutor()

    result = CliRunner().invoke(
        build_text_alias_app(tmp_path, executor),
        ["input", "e001", "--device", "RFCN4010FCK", "--text", "hello", "--json"],
    )

    payload = json_payload(result.stdout)
    assert result.exit_code == 1
    assert payload["receipt"]["error"]["code"] == "latest_snap_source_target_not_input"
    assert payload["receipt"]["attempted_touch"] is False
    assert payload["next_snap"] is None
    assert executor.calls == []


def test_mobile_text_alias_invalid_text_does_not_leak_raw_text(
    tmp_path: Path,
) -> None:
    executor = FakeTextExecutor()
    secret = "SECRET_TEXT_SHOULD_NOT_LEAK"
    invalid_text = secret + ("x" * 4096)

    result = CliRunner().invoke(
        build_text_alias_app(tmp_path, executor),
        ["input", "e001", "--device", "RFCN4010FCK", "--text", invalid_text, "--json"],
    )

    payload = json_payload(result.stdout)
    assert result.exit_code == 1
    assert payload["receipt"]["error"]["code"] == "primitive_invalid_request"
    assert payload["receipt"]["request"]["text_length"] == len(invalid_text)
    assert "text_sha256" not in payload["receipt"]["request"]
    assert payload["next_snap"] is None
    assert secret not in result.stdout
    assert executor.calls == []
