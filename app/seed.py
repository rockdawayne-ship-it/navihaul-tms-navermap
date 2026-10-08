"""샘플 데이터. 전국 주요 물류 거점 좌표(실제 지점 근사값)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import db, dispatch, geo, orders

PLACES = {
    "평택항 물류센터": ("경기 평택시 포승읍 평택항만길 73", 36.9690, 126.8300),
    "군포 복합물류터미널": ("경기 군포시 산본로 1", 37.3400, 126.9400),
    "용인 남사 물류센터": ("경기 용인시 처인구 남사읍 봉명리", 37.1100, 127.1300),
    "인천신항 배후단지": ("인천 연수구 송도동", 37.3950, 126.6200),
    "안성 물류단지": ("경기 안성시 원곡면", 37.0600, 127.1500),
    "천안 물류센터": ("충남 천안시 서북구 성거읍", 36.8900, 127.2000),
    "대전 유성 물류센터": ("대전 유성구 대정동", 36.3100, 127.3200),
    "청주 오창 물류단지": ("충북 청주시 청원구 오창읍", 36.7200, 127.4300),
    "구미 공단 물류센터": ("경북 구미시 공단동", 36.1100, 128.3800),
    "대구 물류단지": ("대구 달서구 월배로", 35.8300, 128.5300),
    "부산신항 배후단지": ("부산 강서구 성북동", 35.0758, 128.8170),
    "울산 온산 물류센터": ("울산 울주군 온산읍", 35.4300, 129.3300),
    "광주 하남산단": ("광주 광산구 하남산단로", 35.1900, 126.8100),
    "전주 물류센터": ("전북 전주시 덕진구 팔복동", 35.8500, 127.1000),
    "원주 문막 물류센터": ("강원 원주시 문막읍", 37.3100, 127.8200),
    "강릉 물류센터": ("강원 강릉시 성산면", 37.7400, 128.8300),
}

SHIPPERS = [("한빛유통", "김과장 010-1111-2222"), ("대성식품", "이대리 010-2222-3333"),
            ("코어전자", "박부장 010-3333-4444"), ("그린팜", "최팀장 010-4444-5555"),
            ("세진케미칼", "정과장 010-5555-6666")]

VEHICLES = [
    ("경기12바3456", "WING", 5, "김철수", "010-9000-0001", "군포 복합물류터미널"),
    ("경기34사7890", "WING", 11, "이영희", "010-9000-0002", "평택항 물류센터"),
    ("서울88아1234", "CARGO", 5, "박민수", "010-9000-0003", "용인 남사 물류센터"),
    ("인천77자5678", "BOX", 2.5, "최지훈", "010-9000-0004", "인천신항 배후단지"),
    ("충남55바2468", "REEFER", 5, "정우성", "010-9000-0005", "천안 물류센터"),
    ("대전66사1357", "CARGO", 11, "강호동", "010-9000-0006", "대전 유성 물류센터"),
    ("경북44아8642", "WING", 25, "유재석", "010-9000-0007", "구미 공단 물류센터"),
    ("부산99자9753", "WING", 11, "신동엽", "010-9000-0008", "부산신항 배후단지"),
    ("광주33바1593", "CARGO", 5, "서장훈", "010-9000-0009", "광주 하남산단"),
    ("전북22사7531", "BOX", 1, "김종국", "010-9000-0010", "전주 물류센터"),
    ("강원11아2580", "REEFER", 11, "하하", "010-9000-0011", "원주 문막 물류센터"),
    ("울산00자3690", "CARGO", 25, "송지효", "010-9000-0012", "울산 온산 물류센터"),
]

# (화주idx, 상차지, 하차지, 차종, 톤, 품목, 상차 +h, 도착 +h)
ORDERS = [
    (0, "평택항 물류센터", "부산신항 배후단지", "WING", 8, "팔레트 14 (생활용품)", 2, 9),
    (1, "천안 물류센터", "광주 하남산단", "REEFER", 3, "냉장식품 120박스", 3, 8),
    (2, "구미 공단 물류센터", "인천신항 배후단지", "WING", 18, "전자부품 22팔레트", 4, 12),
    (3, "전주 물류센터", "군포 복합물류터미널", "CARGO", 4, "농산물 톤백 4", 1, 6),
    (4, "용인 남사 물류센터", "대구 물류단지", "CARGO", 9, "화학원료 드럼 40", 5, 11),
    (0, "안성 물류단지", "강릉 물류센터", "BOX", 2, "소형가전 80박스", 2, 7),
    (1, "대전 유성 물류센터", "울산 온산 물류센터", "REEFER", 9, "냉동식품 팔레트 10", 6, 12),
    (2, "인천신항 배후단지", "청주 오창 물류단지", "WING", 4, "부품 8팔레트", 1, 5),
    (3, "광주 하남산단", "평택항 물류센터", "CARGO", 20, "철강 코일 3", 7, 14),
    (4, "원주 문막 물류센터", "대전 유성 물류센터", "BOX", 1, "샘플 30박스", 3, 7),
    (0, "부산신항 배후단지", "군포 복합물류터미널", "WING", 10, "수입잡화 16팔레트", 4, 11),
    (1, "청주 오창 물류단지", "전주 물류센터", "CARGO", 3, "포장재 톤백", 2, 6),
    (2, "대구 물류단지", "용인 남사 물류센터", "WING", 22, "디스플레이 모듈", 8, 15),
    (3, "강릉 물류센터", "안성 물류단지", "CARGO", 4, "수산가공품", 5, 10),
]


def reset(conn, call_api: bool = False) -> dict:
    for t in ("vehicle_positions", "order_events", "orders", "vehicles", "shippers"):
        conn.execute(f"DELETE FROM {t}")
    ts = orders.now_iso()
    for name, contact in SHIPPERS:
        conn.execute("INSERT INTO shippers (name, contact) VALUES (?,?)", (name, contact))
    for plate, vtype, cap, drv, phone, home in VEHICLES:
        _, lat, lng = PLACES[home]
        conn.execute(
            "INSERT INTO vehicles (plate, vehicle_type, capacity_ton, driver_name, driver_phone, status, lat, lng, home_label, updated_at) VALUES (?,?,?,?,?,'IDLE',?,?,?,?)",
            (plate, vtype, cap, drv, phone, lat, lng, home, ts))
    base = datetime.now().replace(minute=0, second=0, microsecond=0)
    for i, (sidx, org, dst, vtype, ton, desc, ph, dh) in enumerate(ORDERS, start=1):
        oaddr, olat, olng = PLACES[org]
        daddr, dlat, dlng = PLACES[dst]
        payload = {
            "shipper_id": sidx + 1, "origin_name": org, "origin_addr": oaddr, "origin_lat": olat, "origin_lng": olng,
            "dest_name": dst, "dest_addr": daddr, "dest_lat": dlat, "dest_lng": dlng,
            "pickup_at": (base + timedelta(hours=ph)).isoformat(), "due_at": (base + timedelta(hours=dh)).isoformat(),
            "vehicle_type": vtype, "weight_ton": ton, "cargo_desc": desc,
        }
        if call_api:
            orders.create_order(conn, payload)
        else:
            # 시드는 API 호출 없이 대체 경로로 빠르게 생성
            route = geo.fallback_route(olat, olng, dlat, dlng)
            order_no = f"TO-{datetime.now().strftime('%y%m%d')}-{i:03d}"
            conn.execute(
                """INSERT INTO orders (order_no, shipper_id, origin_name, origin_addr, origin_lat, origin_lng,
                   dest_name, dest_addr, dest_lat, dest_lng, pickup_at, due_at, vehicle_type, weight_ton, cargo_desc,
                   status, distance_km, duration_min, route_source, route_path, fare_krw, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'REQUESTED',?,?,?,?,?,?)""",
                (order_no, payload["shipper_id"], org, oaddr, olat, olng, dst, daddr, dlat, dlng,
                 payload["pickup_at"], payload["due_at"], vtype, ton, desc,
                 route["distance_km"], route["duration_min"], route["source"], json.dumps(route["path"]),
                 dispatch.fare(route["distance_km"], ton), ts))
            oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO order_events (order_id, from_status, to_status, note, at) VALUES (?,?,?,?,?)",
                         (oid, None, "REQUESTED", "샘플 오더", ts))
    # 시연용 초기 상태: 1~3번 오더 추천 1순위로 배정, 1번은 운송중까지 진행
    for oid in (1, 2, 3):
        rec = orders.recommend(conn, oid)
        if rec["candidates"]:
            orders.assign(conn, oid, rec["candidates"][0]["vehicle_id"], "샘플 배정")
    orders.change_status(conn, 1, "LOADED", "샘플 상차")
    orders.change_status(conn, 1, "IN_TRANSIT", "샘플 출발")
    conn.execute("UPDATE orders SET progress=0.35 WHERE id=1")
    from .simulator import tick
    tick(conn, minutes=0, auto_deliver=False)
    return {"shippers": len(SHIPPERS), "vehicles": len(VEHICLES), "orders": len(ORDERS)}


if __name__ == "__main__":
    db.init_db()
    with db.get_conn() as conn:
        print(reset(conn))
