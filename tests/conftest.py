"""Test setup: isolate the SQLite database and model files in a temp dir.

These environment variables must be set before any `src.app` module is
imported, because the engine and model paths are created at import time.
"""

import os
import tempfile
import uuid

_TMP = tempfile.mkdtemp(prefix="ottc-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["MODEL_DIR"] = os.path.join(_TMP, "models")
os.environ.setdefault("REDIS_HOST", "127.0.0.1")

import pytest  # noqa: E402


@pytest.fixture
def make_event():
    def _make(**overrides):
        event = {
            "event_id": f"evt-{uuid.uuid4().hex[:10]}",
            "user_id": "sub-0001",
            "device_id": "tv-0001",
            "content_id": "title-001",
            "event_type": "play",
            "timestamp": "2026-01-01T12:00:00Z",
            "region": "US",
            "is_eu": False,
            "has_consent": True,
            "ip_address": "192.0.2.10",
        }
        event.update(overrides)
        return event

    return _make


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from src.app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client):
    r = client.post("/token", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
