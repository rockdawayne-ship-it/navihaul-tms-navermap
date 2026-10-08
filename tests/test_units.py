import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dispatch, geo  # noqa: E402


def test_haversine_seoul_busan():
    km = geo.haversine_km(37.5547, 126.9707, 35.1100, 129.0414)
    assert 320 < km < 335


def test_fallback_route_has_path_and_road_factor():
    r = geo.fallback_route(37.0, 127.0, 36.0, 127.0)
    straight = geo.haversine_km(37.0, 127.0, 36.0, 127.0)
    assert r["source"] == "fallback"
    assert abs(r["distance_km"] - round(straight * geo.ROAD_FACTOR, 1)) < 0.11
    assert r["path"][0] == [127.0, 37.0] and r["path"][-1] == [127.0, 36.0]


def test_point_along_bounds():
    path = [[127.0, 37.0], [127.0, 36.0]]
    assert geo.point_along(path, 0) == (37.0, 127.0)
    assert geo.point_along(path, 1) == (36.0, 127.0)
    lat, lng = geo.point_along(path, 0.5)
    assert abs(lat - 36.5) < 0.01


def test_compatibility_rules():
    assert dispatch.compatible("CARGO", "WING")
    assert dispatch.compatible("BOX", "WING")
    assert not dispatch.compatible("WING", "CARGO")
    assert not dispatch.compatible("REEFER", "WING")
    assert dispatch.compatible("REEFER", "REEFER")


def test_eligible_rejects_busy_and_small():
    order = {"vehicle_type": "CARGO", "weight_ton": 5, "origin_lat": 37, "origin_lng": 127}
    busy = {"status": "ON_TRIP", "vehicle_type": "CARGO", "capacity_ton": 5, "lat": 37, "lng": 127}
    small = {"status": "IDLE", "vehicle_type": "CARGO", "capacity_ton": 2.5, "lat": 37, "lng": 127}
    ok = {"status": "IDLE", "vehicle_type": "WING", "capacity_ton": 5, "lat": 37, "lng": 127}
    assert not dispatch.eligible(order, busy)[0]
    assert "적재 부족" in dispatch.eligible(order, small)[1]
    assert dispatch.eligible(order, ok)[0]


def test_recommend_prefers_nearest():
    order = {"vehicle_type": "CARGO", "weight_ton": 5, "origin_lat": 37.0, "origin_lng": 127.0}
    near = {"id": 1, "plate": "near", "status": "IDLE", "vehicle_type": "CARGO", "capacity_ton": 5, "lat": 37.05, "lng": 127.0}
    far = {"id": 2, "plate": "far", "status": "IDLE", "vehicle_type": "CARGO", "capacity_ton": 5, "lat": 35.0, "lng": 129.0}
    bad = {"id": 3, "plate": "bad", "status": "IDLE", "vehicle_type": "BOX", "capacity_ton": 5, "lat": 37.0, "lng": 127.0}
    rec = dispatch.recommend(order, [far, near, bad])
    assert [c["plate"] for c in rec["candidates"]] == ["near", "far"]
    assert rec["rejected"][0]["plate"] == "bad"
    assert rec["candidates"][0]["reasons"]


def test_fare_rounding():
    assert dispatch.fare(100, 5) == 200_000
    assert dispatch.fare(100, 1) % 100 == 0
