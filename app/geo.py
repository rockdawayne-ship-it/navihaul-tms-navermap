"""좌표 계산 유틸. 좌표는 (lat, lng), 경로는 [[lng, lat], ...] (네이버 Directions 형식)."""
from __future__ import annotations

import math

EARTH_KM = 6371.0088
ROAD_FACTOR = 1.3  # 직선거리 → 도로거리 보정 (대체 모드)
AVG_SPEED_KMH = 70.0  # 대체 모드 평균 속도


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def fallback_route(lat1: float, lng1: float, lat2: float, lng2: float, steps: int = 20) -> dict:
    """API 없이 직선 보간 경로. 거리는 도로 보정, 시간은 평균 속도."""
    straight = haversine_km(lat1, lng1, lat2, lng2)
    km = round(straight * ROAD_FACTOR, 1)
    path = [
        [round(lng1 + (lng2 - lng1) * i / steps, 6), round(lat1 + (lat2 - lat1) * i / steps, 6)]
        for i in range(steps + 1)
    ]
    return {
        "distance_km": km,
        "duration_min": round(km / AVG_SPEED_KMH * 60, 1),
        "path": path,
        "source": "fallback",
    }


def path_length_km(path: list[list[float]]) -> float:
    total = 0.0
    for (lng1, lat1), (lng2, lat2) in zip(path, path[1:]):
        total += haversine_km(lat1, lng1, lat2, lng2)
    return total


def point_along(path: list[list[float]], progress: float) -> tuple[float, float]:
    """경로상 진행률(0~1) 위치를 (lat, lng) 로 반환."""
    if not path:
        raise ValueError("empty path")
    if len(path) == 1 or progress <= 0:
        return path[0][1], path[0][0]
    if progress >= 1:
        return path[-1][1], path[-1][0]
    total = path_length_km(path)
    target = total * progress
    acc = 0.0
    for (lng1, lat1), (lng2, lat2) in zip(path, path[1:]):
        seg = haversine_km(lat1, lng1, lat2, lng2)
        if acc + seg >= target and seg > 0:
            t = (target - acc) / seg
            return lat1 + (lat2 - lat1) * t, lng1 + (lng2 - lng1) * t
        acc += seg
    return path[-1][1], path[-1][0]
