import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from aisstream_mock import VALID_KEY  # noqa: E402

from tracktrust.settings import Region, RecorderSettings, Settings  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path / "data",
        regions=(
            Region("gulf_hormuz", ((22.0, 47.5), (30.5, 62.5)), "test", True),
            Region("red_sea_aden", ((11.0, 32.0), (30.0, 51.5)), "test", False),
        ),
        recorder=RecorderSettings(stall_timeout_s=5, max_backoff_s=2, auto_compact=True, status_interval_s=60),
    )


@pytest.fixture
def api_key():
    return VALID_KEY


@pytest.fixture(autouse=True)
def _restore_logging():
    """The CLI replaces the root logging handlers; put pytest's back afterwards."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    monkeypatch.delenv("AISSTREAM_API_KEY", raising=False)
    monkeypatch.delenv("TRACKTRUST_CONFIG", raising=False)
    monkeypatch.delenv("TRACKTRUST_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
