from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessTimeoutError(TimeoutError):
    pass


class ProcessRunner:
    def run(self, args: Sequence[str], timeout_s: float) -> ProcessResult:
        raise NotImplementedError


class SubprocessRunner(ProcessRunner):
    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = dict(env) if env is not None else _env_with_src_pythonpath()

    def run(self, args: Sequence[str], timeout_s: float) -> ProcessResult:
        if timeout_s <= 0:
            raise ProcessTimeoutError("Process timeout must be positive.")
        try:
            completed = subprocess.run(
                list(args),
                capture_output=True,
                check=False,
                env=self._env,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProcessTimeoutError(
                f"Process exceeded {timeout_s:.3f}s timeout."
            ) from exc
        return ProcessResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def _env_with_src_pythonpath() -> dict[str, str]:
    env = os.environ.copy()
    src_root = str(Path(__file__).resolve().parents[2])
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_root if not existing else f"{src_root}{os.pathsep}{existing}"
    )
    return env
