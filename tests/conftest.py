"""Shared fixtures for korb tests."""

from datetime import datetime, tzinfo
from pathlib import Path

import pytest

from korb.core import LOCAL_TZ

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Freeze `datetime.now()` as seen by korb.schedule so the static
    fixture HTML dates (Jan/Jun 2026) remain in the future for pending-game logic."""
    fixed = datetime(2026, 1, 10, 0, 0, tzinfo=LOCAL_TZ)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return fixed

    monkeypatch.setattr("korb.schedule.datetime", _FixedDatetime)
    return fixed


@pytest.fixture
def ergebnisse_path() -> str:
    return str(FIXTURES_DIR / "ergebnisse_minimal.html")


@pytest.fixture
def spielplan_path() -> str:
    return str(FIXTURES_DIR / "spielplan_minimal.html")


@pytest.fixture
def spielplan_finalized_path() -> str:
    return str(FIXTURES_DIR / "spielplan_finalized.html")
