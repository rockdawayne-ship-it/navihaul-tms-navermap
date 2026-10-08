# NaviHaul — 차량 운송 관제 TMS (네이버 지도)

화물 운송 오더 등록 → 경로·운임 계산 → 배차 추천/배정 → 운송 시뮬레이션·ETA 관제를 네이버 지도 위에서 수행하는 교육용 TMS.

## 빠른 시작
```bash
py -3.13 -m pip install -r requirements.txt
copy .env.example .env     # NCP_MAP_KEY_ID / NCP_MAP_KEY 입력 (PRD/05_NAVER_MAP_SETUP.md)
run.bat                    # http://localhost:8520
```
첫 실행 시 샘플 데이터(화주 5, 차량 12, 오더 14)가 자동 생성됨.

## 키 없이 실행하면
| 항목 | 키 있음 | 키 없음 |
|------|---------|---------|
| 지도 | 네이버 지도 표시 | 안내 문구 (나머지 기능 동작) |
| 경로 | Directions 5 도로 경로 | 직선 × 1.3 보정 (`route_source=fallback`, 주황 점선) |
| 장소 검색 | Geocoding + 지역검색 | 개발자센터 키만 있으면 지역검색, 없으면 지도 우클릭 지정 |

## 테스트
```bash
py -3.13 -m pytest -q
```

## 문서
`PRD/` — 01 PRD · 02 데이터 모델 · 03 단계 · 04 프로젝트 스펙 · 05 네이버 지도 설정 가이드

## 교육생 매뉴얼
- [E2E 매뉴얼 (Markdown)](docs/E2E_매뉴얼_교육생용.md)
- [E2E 매뉴얼 (HTML, 스크린샷 내장 단일 파일)](docs/E2E_매뉴얼_교육생용.html) — 앱 실행 중이면 http://localhost:8520/docs-manual/E2E_매뉴얼_교육생용.html

