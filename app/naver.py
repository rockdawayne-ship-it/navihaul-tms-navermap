"""네이버 API 래퍼.

- NCP Maps Geocoding  : 주소 → 좌표
- NCP Maps Directions5: 자동차 경로 (거리·시간·path)
- 네이버 개발자센터 지역 검색: 상호명 검색 (대체)
모든 함수는 실패 시 예외 대신 빈 결과/대체값을 돌려준다.
"""
from __future__ import annotations

import html
import logging
import re

import httpx

from . import config, geo

log = logging.getLogger("tms.naver")
TIMEOUT = 6.0


def _ncp_headers() -> dict:
    return {
        "x-ncp-apigw-api-key-id": config.NCP_MAP_KEY_ID,
        "x-ncp-apigw-api-key": config.NCP_MAP_KEY,
        "Accept": "application/json",
    }


def geocode(query: str) -> list[dict]:
    """NCP Geocoding. 반환: [{name, address, lat, lng, source}]"""
    if not config.features()["geocode"]:
        return []
    url = f"{config.NCP_MAPS_BASE}/map-geocode/v2/geocode"
    try:
        r = httpx.get(url, params={"query": query, "count": 5}, headers=_ncp_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("geocode failed: %s", e)
        return []
    out = []
    for a in data.get("addresses", []):
        out.append({
            "name": a.get("roadAddress") or a.get("jibunAddress") or query,
            "address": a.get("roadAddress") or a.get("jibunAddress") or "",
            "lat": float(a["y"]), "lng": float(a["x"]),
            "source": "ncp-geocode",
        })
    return out


def local_search(query: str) -> list[dict]:
    """네이버 개발자센터 지역 검색. mapx/mapy 는 WGS84 × 1e7."""
    if not config.features()["local_search"]:
        return []
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {"X-Naver-Client-Id": config.NAVER_CLIENT_ID, "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET}
    try:
        r = httpx.get(url, params={"query": query, "display": 5}, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("local_search failed: %s", e)
        return []
    out = []
    for it in data.get("items", []):
        try:
            lng = int(it["mapx"]) / 1e7
            lat = int(it["mapy"]) / 1e7
        except (KeyError, ValueError):
            continue
        name = html.unescape(re.sub(r"<[^>]+>", "", it.get("title", "")))
        out.append({
            "name": name,
            "address": it.get("roadAddress") or it.get("address") or "",
            "lat": lat, "lng": lng,
            "source": "naver-local",
        })
    return out


def search_places(query: str) -> list[dict]:
    """상호명이면 지역검색이 유리, 주소면 Geocoding 이 유리. 둘 다 시도해 합친다."""
    query = query.strip()
    if not query:
        return []
    results = local_search(query) + geocode(query)
    seen, out = set(), []
    for p in results:
        key = (round(p["lat"], 5), round(p["lng"], 5))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out[:8]


def directions(lat1: float, lng1: float, lat2: float, lng2: float, option: str = "trafast") -> dict:
    """Directions 5 driving. 실패 시 geo.fallback_route."""
    if not config.features()["directions"]:
        return geo.fallback_route(lat1, lng1, lat2, lng2)
    url = f"{config.NCP_MAPS_BASE}/map-direction/v1/driving"
    params = {"start": f"{lng1},{lat1}", "goal": f"{lng2},{lat2}", "option": option}
    try:
        r = httpx.get(url, params=params, headers=_ncp_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        route = data["route"][option][0]
        summ = route["summary"]
        path = route["path"]
        # path 가 수천 점이면 저장·전송 부담 → 400점 이하로 샘플링
        if len(path) > 400:
            step = len(path) / 400
            path = [path[int(i * step)] for i in range(400)] + [path[-1]]
        return {
            "distance_km": round(summ["distance"] / 1000, 1),
            "duration_min": round(summ["duration"] / 60000, 1),
            "path": path,
            "source": "naver-directions",
        }
    except Exception as e:  # noqa: BLE001
        log.warning("directions failed, fallback: %s", e)
        return geo.fallback_route(lat1, lng1, lat2, lng2)
