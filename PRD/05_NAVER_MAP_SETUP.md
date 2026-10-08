# 05. 네이버 지도 API 설정 가이드 (교육생용)

> 카카오 지도 설정 가이드를 네이버 지도(NAVER Cloud Platform Maps) 기준으로 바꾼 문서
> 예상 소요 시간: 약 10분 / 준비물: 네이버 계정, NAVER Cloud Platform 가입(결제수단 등록 필요)

## 전체 흐름
```
① NCP 가입·로그인 → ② Maps Application 등록 → ③ API 선택(Dynamic Map, Geocoding, Directions 5)
→ ④ Web 서비스 URL 등록 → ⑤ Client ID / Secret 복사 → ⑥ .env 입력 → ⑦ 실행 확인
```

## 1. Application 등록
```
https://console.ncloud.com → Services → Application Services → Maps → Application 등록
```
- Application 이름: 자유 (예: `NaviHaul-TMS`)
- **API 선택** (체크):
  - Dynamic Map — 지도 화면 (필수)
  - Geocoding — 주소 → 좌표
  - Directions 5 — 도로 경로·거리·시간
- 무료 사용량 범위에서 실습 가능. 사용량은 콘솔에서 확인.

## 2. 서비스 환경 등록 (필수)
```
Web 서비스 URL: http://localhost:8520
```
- 등록된 URL 에서만 지도가 뜸. 포트 바꾸면 그 포트로 다시 등록.
- 빠뜨리면 지도 대신 "인증 실패" 안내가 나옴 (앱이 `navermap_authFailure` 로 감지).

## 3. 인증 정보 확인
```
Maps → Application → 인증 정보
```
| 콘솔 표시 | .env 키 | 사용처 |
|-----------|---------|--------|
| Client ID | `NCP_MAP_KEY_ID` | 지도 JS (`ncpKeyId`), API 헤더 `x-ncp-apigw-api-key-id` |
| Client Secret | `NCP_MAP_KEY` | API 헤더 `x-ncp-apigw-api-key` (서버에서만) |

> 네이버 **개발자센터**(developers.naver.com) 의 검색 API 키와는 다른 키임. 개발자센터 키는 `NAVER_CLIENT_ID/SECRET` 에 넣으면 장소 검색 대체용으로 쓰임.

## 4. .env 설정
```bash
copy .env.example .env
```
```env
NCP_MAP_KEY_ID=발급받은_Client_ID
NCP_MAP_KEY=발급받은_Client_Secret
```
⚠️ `.env` 는 절대 커밋·공유 금지. 노출되면 콘솔에서 재발급.

## 5. 실행 확인
```bash
run.bat
```
- 상단 배지: `지도 ✓ / 경로 ✓ / 검색 ✓`
- 관제 지도에 차량·상하차지 마커 표시
- 오더 선택 시 도로를 따라가는 경로선 표시 (직선이면 대체 모드)

## 문제 해결
| 증상 | 원인 | 해결 |
|------|------|------|
| 지도 자리에 "인증 실패" | Web 서비스 URL 미등록 / Dynamic Map 미선택 / Client ID 오타 | 2·1·3 단계 재확인 |
| 경로가 직선, 배지 `경로: 대체` | Directions 5 미선택 또는 Secret 오류 (401) | Application 에서 Directions 5 체크, `NCP_MAP_KEY` 확인 |
| 장소 검색 결과 없음 | Geocoding 은 정확한 주소만 인식 | 도로명 주소로 입력하거나 개발자센터 키 등록(상호명 검색) |
| 회사망에서만 안 됨 | 방화벽이 `oapi.map.naver.com` 차단 | 다른 네트워크로 원인 분리 |

## 참고 좌표
| 지점 | lat | lng |
|------|-----|-----|
| 서울역 | 37.5547 | 126.9707 |
| 평택항 | 36.9690 | 126.8300 |
| 부산신항 | 35.0758 | 128.8170 |
| 광주 | 35.1595 | 126.8526 |
