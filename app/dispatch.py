"""배차 규칙: 차종 호환, 추천 점수, 운임."""
from __future__ import annotations

from . import geo

VEHICLE_TYPES = {"CARGO": "카고", "WING": "윙바디", "BOX": "탑차", "REEFER": "냉장냉동"}

# 요구 차종 → 허용 차종
COMPATIBLE = {
    "REEFER": {"REEFER"},
    "WING": {"WING"},
    "BOX": {"BOX", "WING"},
    "CARGO": {"CARGO", "WING"},
}

TON_FACTOR = {1: 0.6, 2.5: 0.8, 5: 1.0, 11: 1.4, 25: 1.9}
BASE_FARE = 50_000
PER_KM = 1_500


def compatible(required: str, vehicle_type: str) -> bool:
    return vehicle_type in COMPATIBLE.get(required, {required})


def eligible(order: dict, vehicle: dict) -> tuple[bool, str]:
    """필수 조건. (가능 여부, 불가 사유)"""
    if vehicle["status"] != "IDLE":
        return False, f"차량 상태 {vehicle['status']} (공차 아님)"
    if not compatible(order["vehicle_type"], vehicle["vehicle_type"]):
        return False, f"차종 불일치 ({VEHICLE_TYPES.get(vehicle['vehicle_type'], vehicle['vehicle_type'])})"
    if vehicle["capacity_ton"] < order["weight_ton"]:
        return False, f"적재 부족 ({vehicle['capacity_ton']}t < {order['weight_ton']}t)"
    if vehicle.get("lat") is None or vehicle.get("lng") is None:
        return False, "차량 위치 미확인"
    return True, ""


def ton_factor(capacity: float) -> float:
    key = min(TON_FACTOR, key=lambda k: abs(k - capacity))
    return TON_FACTOR[key]


def fare(distance_km: float, weight_ton: float) -> int:
    raw = BASE_FARE + distance_km * PER_KM * ton_factor(weight_ton)
    return int(round(raw / 100) * 100)


def recommend(order: dict, vehicles: list[dict], trip_counts: dict[int, int] | None = None, top: int = 3) -> dict:
    """추천 결과: {candidates:[...], rejected:[...]}.

    점수(0~100): 공차거리 60 + 적재 적합도 25 + 운행 공평성 15.
    """
    trip_counts = trip_counts or {}
    cands, rejected = [], []
    for v in vehicles:
        ok, reason = eligible(order, v)
        if not ok:
            rejected.append({"vehicle_id": v["id"], "plate": v["plate"], "reason": reason})
            continue
        empty_km = geo.haversine_km(v["lat"], v["lng"], order["origin_lat"], order["origin_lng"]) * geo.ROAD_FACTOR
        cands.append((v, empty_km))
    if not cands:
        return {"candidates": [], "rejected": rejected}

    max_empty = max(e for _, e in cands) or 1.0
    max_trips = max([trip_counts.get(v["id"], 0) for v, _ in cands] + [1])
    scored = []
    for v, empty_km in cands:
        s_dist = 60 * (1 - empty_km / max_empty) if len(cands) > 1 else 60
        over = v["capacity_ton"] / order["weight_ton"] if order["weight_ton"] else 1
        s_fit = 25 if over <= 1.5 else (15 if over <= 2.5 else 5)
        trips = trip_counts.get(v["id"], 0)
        s_fair = 15 * (1 - trips / max_trips) if max_trips else 15
        score = round(s_dist + s_fit + s_fair, 1)
        reasons = [f"상차지까지 공차 {empty_km:.0f}km"]
        reasons.append("적재 적합" if s_fit == 25 else f"적재 여유 큼 ({v['capacity_ton']}t)")
        reasons.append(f"최근 운행 {trips}회")
        scored.append({
            "vehicle_id": v["id"], "plate": v["plate"],
            "vehicle_type": v["vehicle_type"], "capacity_ton": v["capacity_ton"],
            "driver_name": v.get("driver_name"),
            "empty_km": round(empty_km, 1), "score": score, "reasons": reasons,
        })
    scored.sort(key=lambda c: (-c["score"], c["empty_km"]))
    return {"candidates": scored[:top], "rejected": rejected}
