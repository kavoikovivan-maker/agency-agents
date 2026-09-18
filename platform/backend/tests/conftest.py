"""Shared pytest fixtures. Configures an isolated temp data dir before app import."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="agency-test-"))
os.environ.setdefault("APP_DATA_DIR", str(_TEST_DATA_DIR))
os.environ.setdefault("MODEL_PROVIDER", "mock")
os.environ.setdefault("APP_PASSWORD", "")
os.environ.setdefault("ALLOWED_ORIGINS", "http://testserver")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app


@pytest.fixture()
def client():
    with TestClient(fastapi_app) as c:
        yield c
