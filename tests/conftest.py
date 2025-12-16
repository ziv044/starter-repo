"""Shared pytest fixtures for pm6 tests."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clean_env():
    """Clean up any PM6 env vars before each test."""
    # Clear any PM6 env vars that might interfere
    for key in list(os.environ.keys()):
        if key.startswith("PM6_"):
            del os.environ[key]
    yield


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database directory."""
    db_path = tmp_path / "db"
    db_path.mkdir()
    return db_path
