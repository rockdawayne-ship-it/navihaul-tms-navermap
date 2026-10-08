"""환경 변수 로드. .env 가 있으면 읽고, 없으면 OS 환경 변수만 사용한다."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")

NCP_MAP_KEY_ID = os.getenv("NCP_MAP_KEY_ID", "")
NCP_MAP_KEY = os.getenv("NCP_MAP_KEY", "")
NCP_MAPS_BASE = os.getenv("NCP_MAPS_BASE", "https://maps.apigw.ntruss.com")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
DB_PATH = Path(os.getenv("TMS_DB_PATH", str(DATA_DIR / "tms.db")))
PORT = int(os.getenv("PORT", "8520"))


def features() -> dict:
    """프론트에 알려줄 기능 가용 여부. Secret 은 절대 포함하지 않는다."""
    return {
        "map": bool(NCP_MAP_KEY_ID),
        "directions": bool(NCP_MAP_KEY_ID and NCP_MAP_KEY),
        "geocode": bool(NCP_MAP_KEY_ID and NCP_MAP_KEY),
        "local_search": bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET),
    }
