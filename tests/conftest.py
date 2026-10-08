import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # 테스트는 외부 API 없이, 임시 DB 로
    for k in ("NCP_MAP_KEY_ID", "NCP_MAP_KEY", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"):
        monkeypatch.setenv(k, "")
    from app import config
    monkeypatch.setattr(config, "NCP_MAP_KEY_ID", "")
    monkeypatch.setattr(config, "NCP_MAP_KEY", "")
    monkeypatch.setattr(config, "NAVER_CLIENT_ID", "")
    monkeypatch.setattr(config, "NAVER_CLIENT_SECRET", "")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
