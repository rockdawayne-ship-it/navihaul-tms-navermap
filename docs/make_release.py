"""교육생 배포용 패키지 생성.

실행: py -3.13 docs/make_release.py
결과: deliverables/NaviHaul_TMS_배포본_YYYYMMDD.zip
  - 소스 전체 (.env, data/, __pycache__, .git, .fablize, deliverables 제외)
  - docs/E2E_매뉴얼_교육생용.html (스크린샷 내장)
  - 설치.cmd / 실행.cmd / 테스트.cmd (더블클릭용)
  - 시작하세요.txt
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "deliverables"
EXCLUDE_DIRS = {".git", ".fablize", ".pytest_cache", "__pycache__", "data", "deliverables", "uploads"}
EXCLUDE_FILES = {".env"}

INSTALL_CMD = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/2] Python 3.13 확인
py -3.13 --version || (echo Python 3.13 이 없습니다. https://www.python.org/downloads/ 에서 설치 후 "Add to PATH" 체크 & pause & exit /b 1)
echo [2/2] 패키지 설치
py -3.13 -m pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo 설치 완료. .env 파일을 열어 NCP_MAP_KEY_ID / NCP_MAP_KEY 를 입력한 뒤 실행.cmd 를 더블클릭하세요.
echo (키 발급: docs\\E2E_매뉴얼_교육생용.html 3장)
pause
"""

RUN_CMD = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" http://localhost:8520
py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8520
pause
"""

TEST_CMD = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3.13 -m pytest -q
pause
"""

START_TXT = """NaviHaul 차량 운송 관제 TMS — 교육생 배포본

1. 설치.cmd 더블클릭  (Python 3.13 필요)
2. .env 파일 열어 NCP Maps 키 입력  (발급 방법: docs\\E2E_매뉴얼_교육생용.html 3장)
3. 실행.cmd 더블클릭  → 브라우저 http://localhost:8520
4. 테스트.cmd 더블클릭 → "12 passed" 확인

매뉴얼: docs\\E2E_매뉴얼_교육생용.html (브라우저로 열기)
설계 문서: PRD\\
원본 저장소: https://github.com/rockdawayne-ship-it/navihaul-tms-navermap
문의: AI LEX 3기 물류 AX과정 / 천동암 교수

주의
- .env 는 절대 공유·업로드 금지 (키 노출 시 NCP 콘솔에서 재발급)
- 포트를 바꾸면 NCP 콘솔 Web 서비스 URL 도 같이 등록해야 지도가 뜸
"""


def should_skip(p: Path) -> bool:
    if p.name in EXCLUDE_FILES:
        return True
    return any(part in EXCLUDE_DIRS for part in p.relative_to(ROOT).parts)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    stamp = date.today().strftime("%Y%m%d")
    name = f"NaviHaul_TMS_배포본_{stamp}"
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / name
        for p in ROOT.rglob("*"):
            if p.is_dir() or should_skip(p):
                continue
            dst = stage / p.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
        (stage / "설치.cmd").write_text(INSTALL_CMD, encoding="utf-8")
        (stage / "실행.cmd").write_text(RUN_CMD, encoding="utf-8")
        (stage / "테스트.cmd").write_text(TEST_CMD, encoding="utf-8")
        (stage / "시작하세요.txt").write_text(START_TXT, encoding="utf-8")
        zip_path = shutil.make_archive(str(OUT_DIR / name), "zip", td, name)
    digest = hashlib.sha256(Path(zip_path).read_bytes()).hexdigest()
    (OUT_DIR / "SHA256SUMS.txt").write_text(f"{digest}  {Path(zip_path).name}\n", encoding="utf-8")
    n = sum(1 for _ in __import__("zipfile").ZipFile(zip_path).namelist())
    print(f"{zip_path}  {Path(zip_path).stat().st_size // 1024} KB  {n} files\nsha256 {digest}")


if __name__ == "__main__":
    main()
