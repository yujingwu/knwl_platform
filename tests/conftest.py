import importlib
import json

import pytest
from fastapi.testclient import TestClient

from app.core import config


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    api_keys = {"key_admin": ["t1", "t2"], "key_t1": ["t1"], "key_t2": ["t2"]}
    monkeypatch.setenv("API_KEYS_JSON", json.dumps(api_keys))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LOG_LEVEL", "CRITICAL")
    monkeypatch.setenv("APP_DISABLE_AUTOCREATE", "1")
    config.get_settings.cache_clear()
    from app import main as main_module

    importlib.reload(main_module)
    app = main_module.create_app()
    with TestClient(app) as client:
        yield client

