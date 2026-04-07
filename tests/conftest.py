"""Shared fixtures for korb tests."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def ergebnisse_path() -> str:
    return str(FIXTURES_DIR / "ergebnisse_minimal.html")


@pytest.fixture
def spielplan_path() -> str:
    return str(FIXTURES_DIR / "spielplan_minimal.html")


@pytest.fixture
def spielplan_finalized_path() -> str:
    return str(FIXTURES_DIR / "spielplan_finalized.html")
