def test_startup_seeds_and_config(client):
    cfg = client.get("/api/config").json()
    assert cfg["features"]["map"] is False
    assert len(client.get("/api/vehicles").json()) == 12
    assert len(client.get("/api/orders").json()) == 14


def test_full_order_lifecycle(client):
    body = {
        "shipper_id": 1, "origin_name": "A", "origin_lat": 37.0, "origin_lng": 127.0,
        "dest_name": "B", "dest_lat": 36.0, "dest_lng": 127.5,
        "vehicle_type": "CARGO", "weight_ton": 3, "cargo_desc": "test",
    }
    r = client.post("/api/orders", json=body)
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["status"] == "REQUESTED" and o["route_source"] == "fallback" and o["distance_km"] > 0
    oid = o["id"]

    rec = client.get(f"/api/orders/{oid}/recommend").json()
    assert rec["candidates"], rec
    vid = rec["candidates"][0]["vehicle_id"]

    # 순서 위반: 접수 → 운송중 불가
    assert client.post(f"/api/orders/{oid}/status", json={"to": "IN_TRANSIT"}).status_code == 409

    r = client.post(f"/api/orders/{oid}/assign", json={"vehicle_id": vid})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ASSIGNED" and r.json()["empty_km"] >= 0

    # 같은 차량 재배정 불가 (공차 아님)
    r2 = client.post("/api/orders", json=body).json()
    assert client.post(f"/api/orders/{r2['id']}/assign", json={"vehicle_id": vid}).status_code == 409

    for to in ("LOADED", "IN_TRANSIT"):
        assert client.post(f"/api/orders/{oid}/status", json={"to": to}).status_code == 200
    o = client.get(f"/api/orders/{oid}").json()
    assert o["eta"] and o["progress"] == 0

    # 시뮬레이터: 소요시간의 절반 진행 → 위치 이동
    half = o["duration_min"] / 2
    t = client.post("/api/sim/tick", json={"minutes": half}).json()
    mv = [m for m in t["moved"] if m["order_id"] == oid][0]
    assert 0.45 < mv["progress"] < 0.55
    v = [v for v in client.get("/api/vehicles").json() if v["id"] == vid][0]
    assert 36.0 < v["lat"] < 37.0 and v["status"] == "ON_TRIP"

    # 끝까지 진행 → 자동 도착, 차량 공차 + 하차지 위치
    client.post("/api/sim/tick", json={"minutes": o["duration_min"]})
    o = client.get(f"/api/orders/{oid}").json()
    assert o["status"] == "DELIVERED"
    v = [v for v in client.get("/api/vehicles").json() if v["id"] == vid][0]
    assert v["status"] == "IDLE" and abs(v["lat"] - 36.0) < 1e-6
    assert [e["to_status"] for e in o["events"]] == ["REQUESTED", "ASSIGNED", "LOADED", "IN_TRANSIT", "DELIVERED"]


def test_assign_rejects_incompatible_vehicle(client):
    body = {"origin_name": "A", "origin_lat": 37.0, "origin_lng": 127.0, "dest_name": "B",
            "dest_lat": 36.0, "dest_lng": 127.5, "vehicle_type": "REEFER", "weight_ton": 3}
    oid = client.post("/api/orders", json=body).json()["id"]
    wing = [v for v in client.get("/api/vehicles").json() if v["vehicle_type"] == "WING" and v["status"] == "IDLE"][0]
    r = client.post(f"/api/orders/{oid}/assign", json={"vehicle_id": wing["id"]})
    assert r.status_code == 409 and "차종" in r.json()["detail"]


def test_cancel_releases_vehicle(client):
    o = [o for o in client.get("/api/orders").json() if o["status"] == "ASSIGNED"][0]
    r = client.post(f"/api/orders/{o['id']}/status", json={"to": "CANCELLED", "note": "화주 취소"})
    assert r.status_code == 200 and r.json()["vehicle_id"] is None
    v = [v for v in client.get("/api/vehicles").json() if v["id"] == o["vehicle_id"]][0]
    assert v["status"] == "IDLE"


def test_kpi_and_places_without_keys(client):
    k = client.get("/api/kpi").json()
    assert k["orders_total"] == 14 and k["in_transit"] == 1
    assert client.get("/api/places", params={"q": "평택"}).json() == {"items": []}
    assert client.get("/").status_code == 200
