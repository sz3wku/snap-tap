from __future__ import annotations

from collections.abc import Sequence

from snap_tap.backends.android.uiautomator2.app_lifecycle import (
    open_uiautomator2_app,
    parse_launchable_activities,
    read_uiautomator2_launchable_apps,
)
from snap_tap.backends.android.uiautomator2.process_runner import (
    ProcessResult,
    ProcessRunner,
)


class FakeProcessRunner(ProcessRunner):
    def __init__(self, result: ProcessResult | None = None) -> None:
        self.calls: list[tuple[list[str], float]] = []
        self._result = result or ProcessResult(returncode=0, stdout="", stderr="")

    def run(self, args: Sequence[str], timeout_s: float) -> ProcessResult:
        self.calls.append((list(args), timeout_s))
        return self._result


def test_parse_launchable_activities_returns_packages_and_components() -> None:
    apps = parse_launchable_activities(
        """
        2 activities found:
          Activity #0:
            com.android.vending/.AssetBrowserActivity
          Activity #1:
            com.instagram.android/.activity.MainTabActivity
        """
    )

    assert [(app.package, app.activity) for app in apps] == [
        ("com.android.vending", ".AssetBrowserActivity"),
        ("com.instagram.android", ".activity.MainTabActivity"),
    ]


def test_launchable_apps_query_uses_adb_argument_list() -> None:
    runner = FakeProcessRunner(
        ProcessResult(
            returncode=0,
            stdout="com.instagram.android/.activity.MainTabActivity\n",
            stderr="",
        )
    )

    result = read_uiautomator2_launchable_apps(
        device_id="RFCN4010FCK",
        timeout_s=3.0,
        process_runner=runner,
    )

    assert result.ok is True
    assert [app.package for app in result.apps] == ["com.instagram.android"]
    assert runner.calls == [
        (
            [
                "adb",
                "-s",
                "RFCN4010FCK",
                "shell",
                "cmd",
                "package",
                "query-activities",
                "--brief",
                "-a",
                "android.intent.action.MAIN",
                "-c",
                "android.intent.category.LAUNCHER",
            ],
            3.0,
        )
    ]


def test_open_app_package_uses_monkey_without_name_resolution() -> None:
    runner = FakeProcessRunner(ProcessResult(returncode=0, stdout="", stderr=""))

    result = open_uiautomator2_app(
        device_id="RFCN4010FCK",
        package="com.instagram.android",
        process_runner=runner,
    )

    assert result.ok is True
    assert runner.calls[0][0] == [
        "adb",
        "-s",
        "RFCN4010FCK",
        "shell",
        "monkey",
        "-p",
        "com.instagram.android",
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    ]


def test_open_app_component_uses_am_start() -> None:
    runner = FakeProcessRunner(ProcessResult(returncode=0, stdout="", stderr=""))

    result = open_uiautomator2_app(
        device_id="RFCN4010FCK",
        package="com.instagram.android",
        activity=".activity.MainTabActivity",
        process_runner=runner,
    )

    assert result.ok is True
    assert runner.calls[0][0] == [
        "adb",
        "-s",
        "RFCN4010FCK",
        "shell",
        "am",
        "start",
        "-a",
        "android.intent.action.MAIN",
        "-c",
        "android.intent.category.LAUNCHER",
        "-n",
        "com.instagram.android/.activity.MainTabActivity",
    ]
