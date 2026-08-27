import os

import pytest

from dupster.infrastructure.device import (
    HDD,
    SSD,
    clear_cache,
    default_workers,
    detect_device_type,
)


@pytest.fixture(autouse=True)
def _clean():
    clear_cache()
    yield
    clear_cache()
    os.environ.pop("DUPSTER_DEVICE_TYPE", None)


def test_detect_returns_a_known_type(tmp_path):
    assert detect_device_type(str(tmp_path)) in (SSD, HDD)


def test_env_override_wins(tmp_path):
    os.environ["DUPSTER_DEVICE_TYPE"] = "hdd"
    assert detect_device_type(str(tmp_path)) == HDD
    os.environ["DUPSTER_DEVICE_TYPE"] = "ssd"
    assert detect_device_type(str(tmp_path)) == SSD


def test_bad_override_is_ignored(tmp_path):
    os.environ["DUPSTER_DEVICE_TYPE"] = "floppy"
    assert detect_device_type(str(tmp_path)) in (SSD, HDD)


def test_missing_path_falls_back_to_ssd(tmp_path):
    assert detect_device_type(str(tmp_path / "does-not-exist")) == SSD


def test_spinning_disks_use_a_single_reader():
    # Concurrent reads on a platter cause seek thrash, so HDDs get one reader.
    assert default_workers(HDD) == 1


def test_solid_state_uses_a_deep_queue():
    assert default_workers(SSD) > 1
    assert default_workers(SSD) <= 32
