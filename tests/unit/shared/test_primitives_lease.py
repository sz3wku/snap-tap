from __future__ import annotations

import time
from pathlib import Path

import pytest

from snap_tap.primitives import PrimitiveLeaseConflict, PrimitiveLeaseManager


def test_lease_conflict_crosses_manager_instances(tmp_path: Path) -> None:
    first = PrimitiveLeaseManager(lock_root=tmp_path)
    second = PrimitiveLeaseManager(lock_root=tmp_path)

    lease = first.acquire(device_id="RFCN4010FCK")
    try:
        with pytest.raises(PrimitiveLeaseConflict):
            second.acquire(device_id="RFCN4010FCK")
    finally:
        first.release(lease)

    next_lease = second.acquire(device_id="RFCN4010FCK")
    second.release(next_lease)


def test_expired_unreleased_file_lease_still_blocks(tmp_path: Path) -> None:
    first = PrimitiveLeaseManager(lock_root=tmp_path)
    second = PrimitiveLeaseManager(lock_root=tmp_path)

    lease = first.acquire(device_id="RFCN4010FCK", timeout_s=0.001)
    time.sleep(0.01)
    try:
        with pytest.raises(PrimitiveLeaseConflict):
            second.acquire(device_id="RFCN4010FCK")
    finally:
        first.release(lease)

    next_lease = second.acquire(device_id="RFCN4010FCK")
    second.release(next_lease)
