"""Shared pytest fixtures for the REDELIVER test suite.

Provides:
- ``client``: a ``TestClient`` wired to the FastAPI app.
- ``frozen_clock``: a deterministic ``datetime`` used everywhere instead of
  the system clock.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


def _test_settings() -> Settings:
    """Return settings tuned for tests (e.g. relaxed CORS)."""
    return Settings(
        cors_origins="*",
        log_level="WARNING",
        app_env="test",
    )


@pytest.fixture()
def client() -> TestClient:
    """Fresh ``TestClient`` per test with overridden settings."""
    app = create_app()
    app.dependency_overrides[get_settings] = _test_settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def frozen_clock() -> datetime:
    """A fixed point in time used by all date/time-sensitive tests.

    Monday 2026-10-26 14:30 UTC.
    """
    return datetime(2026, 10, 26, 14, 30, tzinfo=timezone.utc)
