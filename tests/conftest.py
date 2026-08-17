"""Shared fixtures for the test suite."""

import sys
from pathlib import Path

import pytest

# Make backend modules importable without installing as a package.
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def flask_client():
    """Create a Flask test client."""
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
