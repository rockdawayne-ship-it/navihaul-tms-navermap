# 02. 데이터 모델

> SQLite 1개 파일(`data/tms.db`). 좌표는 WGS84 (lat, lng).

## ERD 개요

```
shippers 1 ── N orders N ── 1 vehicles
                 │                │
                 N                N
           order_events     vehicle_positions
```

## 테이블

### shippers (화주)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | |
| name | TEXT NOT NULL UNIQUE | 화주명 |
| contact | TEXT | 담당자/연락처 |

### vehicles (차량)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | |
| plate | TEXT UNIQUE | 차량번호 (예: 경기12바3456) |
| vehicle_type | TEXT | CARGO(카고) / WING(윙바디) / BOX(탑차) / REEFER(냉장·냉동) |
| capacity_ton | REAL | 적재 톤수 (1, 2.5, 5, 11, 25) |
| driver_name | TEXT | 기사명 |
| driver_phone | TEXT | 연락처 |
| status | TEXT | IDLE / ASSIGNED / ON_TRIP / OFF |
| lat, lng | REAL | 현재(마지막 보고) 위치 |
| home_label | TEXT | 차고지 이름 |
| updated_at | TEXT | 위치 갱신 시각 (ISO) |

### orders (운송 오더)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | |
| order_no | TEXT UNIQUE | `TO-YYMMDD-NNN` |
| shipper_id | INTEGER FK | |
| origin_name, origin_addr | TEXT | 상차지 |
| origin_lat, origin_lng | REAL | |
| dest_name, dest_addr | TEXT | 하차지 |
| dest_lat, dest_lng | REAL | |
| pickup_at | TEXT | 상차 희망 시각 |
| due_at | TEXT | 도착 약속 시각 |
| vehicle_type | TEXT | 요구 차종 |
| weight_ton | REAL | 화물 중량 |
| cargo_desc | TEXT | 품목/수량 |
| status | TEXT | REQUESTED / ASSIGNED / LOADED / IN_TRANSIT / DELIVERED / CANCELLED |
| vehicle_id | INTEGER FK NULL | 배정 차량 |
| distance_km | REAL | 경로 거리 |
| duration_min | REAL | 예상 소요 |
| route_source | TEXT | `naver-directions` / `fallback` |
| route_path | TEXT | JSON `[[lng,lat],...]` |
| fare_krw | INTEGER | 예상 운임 |
| empty_km | REAL | 배정 시 차량 → 상차지 공차거리 |
| progress | REAL | 운송중 진행률 0~1 |
| eta | TEXT | 도착 예정 |
| created_at, assigned_at, loaded_at, departed_at, delivered_at | TEXT | 단계별 시각 |

### order_events (상태 이력)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | |
| order_id | INTEGER FK | |
| from_status, to_status | TEXT | |
| note | TEXT | 사유/메모 |
| at | TEXT | |

### vehicle_positions (위치 로그)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | |
| vehicle_id | INTEGER FK | |
| order_id | INTEGER NULL | |
| lat, lng | REAL | |
| speed_kmh | REAL | |
| at | TEXT | |

## 차종 호환 규칙
- 요구 차종이 REEFER 면 REEFER 만 허용.
- WING 요구 시 WING 만 허용, BOX 요구 시 BOX/WING 허용, CARGO 요구 시 CARGO/WING 허용.
- `capacity_ton >= weight_ton` 필수.

## 운임 계산 (예시)
`fare = 50,000 + distance_km × 1,500 × 톤급계수` (1t 0.6 / 2.5t 0.8 / 5t 1.0 / 11t 1.4 / 25t 1.9), 100원 단위 반올림.
