# 04. 프로젝트 스펙

## 기술 스택
| 영역 | 선택 | 이유 |
|------|------|------|
| 백엔드 | Python 3.13, FastAPI, Uvicorn | REST API + 정적 파일 제공 |
| DB | SQLite (`sqlite3` 표준 모듈) | 설치 불필요, 실습용 |
| HTTP | httpx | 네이버 API 호출 |
| 프론트 | 바닐라 HTML/CSS/JS | 네이버 지도 SDK 를 iframe 없이 직접 로드 |
| 지도 | NAVER Maps JavaScript API v3 | 요구사항 |
| 테스트 | pytest + FastAPI TestClient | |

## 폴더 구조
```
차량운송_TMS_NaverMap/
├─ PRD/                 # 01~05 문서
├─ app/
│  ├─ main.py           # FastAPI 라우트
│  ├─ config.py         # .env 로드, 키 존재 여부
│  ├─ db.py             # 스키마·연결
│  ├─ naver.py          # Geocoding / 지역검색 / Directions 5 + 대체 계산
│  ├─ geo.py            # haversine, 경로 보간
│  ├─ dispatch.py       # 차종 호환, 추천 점수, 운임
│  ├─ orders.py         # 오더 생성·상태 전이
│  ├─ simulator.py      # 운송 시뮬레이션 tick
│  └─ seed.py           # 샘플 데이터
├─ static/              # index.html, app.js, style.css
├─ tests/
├─ data/tms.db          # 실행 시 생성 (git 제외)
├─ .env.example
├─ requirements.txt
└─ run.bat
```

## API
| Method | Path | 설명 |
|--------|------|------|
| GET | /api/config | 지도 키 ID(공개용), 사용 가능 기능 |
| GET | /api/places?q= | 장소 검색 (Geocoding → 지역검색) |
| GET | /api/vehicles | 차량 목록 |
| GET | /api/orders?status= | 오더 목록 |
| GET | /api/orders/{id} | 오더 상세 + 경로 + 이력 |
| POST | /api/orders | 오더 생성 (경로·운임 자동 계산) |
| GET | /api/orders/{id}/recommend | 추천 차량 상위 3 |
| POST | /api/orders/{id}/assign | 배정 `{vehicle_id}` |
| POST | /api/orders/{id}/status | 상태 전이 `{to, note}` |
| POST | /api/sim/tick | 시뮬레이션 1스텝 `{minutes}` |
| GET | /api/kpi | KPI |
| POST | /api/reset | 샘플 데이터 초기화 |

## 환경 변수 (.env)
| 키 | 용도 | 필수 |
|----|------|------|
| NCP_MAP_KEY_ID | NCP Maps Client ID — 지도 JS(`ncpKeyId`) + Geocoding/Directions 헤더 | 지도 표시에 필수 |
| NCP_MAP_KEY | NCP Maps Client Secret — Geocoding/Directions 헤더 | 도로 경로에 필수 |
| NAVER_CLIENT_ID / NAVER_CLIENT_SECRET | 네이버 개발자센터 검색 API (장소 검색 대체) | 선택 |
| NCP_MAPS_BASE | 기본 `https://maps.apigw.ntruss.com` | 선택 |
| PORT | 기본 8520 | 선택 |

## 절대 하지 마
- Client Secret(`NCP_MAP_KEY`, `NAVER_CLIENT_SECRET`)을 프론트로 내려보내지 말 것. 프론트에는 `NCP_MAP_KEY_ID` 만 전달.
- `.env` 를 git 커밋·공유 금지.
- 상태 전이를 프론트에서 판단하지 말 것 — 서버 `ALLOWED` 표가 유일한 기준.
- 네이버 API 실패를 예외로 터뜨리지 말 것 — 대체 계산 + `route_source` 표시.

## 실행
```bash
py -3.13 -m pip install -r requirements.txt
py -3.13 -m uvicorn app.main:app --port 8520
```
브라우저: http://localhost:8520 (NCP 콘솔 Web 서비스 URL 에 동일 주소 등록)
