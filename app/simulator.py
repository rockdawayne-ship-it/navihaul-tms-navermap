"""운송 시뮬레이터. 실제 GPS 대신 운송중 차량을 경로를 따라 이동시킨다."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import db, orders


def tick(conn, minutes: float = 10.0, auto_deliver: bool = True, now: datetime | None = None) -> dict:
    """운송중(IN_TRANSIT) 오더를 `minutes` 분만큼 진행. 진행률 1 도달 시 자동 도착 처리.

    `now` 를 주면 가상 시계 기준으로 ETA·시각을 기록한다(합성 데이터 시뮬레이션용).
    """
    moved, delivered = [], []
    rows = db.rows(conn.execute(
        "SELECT id, vehicle_id, duration_min, progress, route_path, due_at FROM orders WHERE status='IN_TRANSIT'"))
    ts = orders.now_iso(now)
    clock = now or datetime.now()
    for o in rows:
        dur = o["duration_min"] or 1
        progress = min(1.0, (o["progress"] or 0) + minutes / dur)
        path = json.loads(o["route_path"]) if o["route_path"] else []
        if not path:
            continue
        from .geo import point_along, path_length_km
        lat, lng = point_along(path, progress)
        remaining_min = dur * (1 - progress)
        eta = (clock + timedelta(minutes=remaining_min)).replace(microsecond=0).isoformat()
        speed = (path_length_km(path) / dur * 60) if dur else 0
        conn.execute("UPDATE orders SET progress=?, eta=? WHERE id=?", (progress, eta, o["id"]))
        conn.execute("UPDATE vehicles SET lat=?, lng=?, updated_at=? WHERE id=?", (lat, lng, ts, o["vehicle_id"]))
        conn.execute("INSERT INTO vehicle_positions (vehicle_id, order_id, lat, lng, speed_kmh, at) VALUES (?,?,?,?,?,?)",
                     (o["vehicle_id"], o["id"], lat, lng, round(speed, 1), ts))
        moved.append({"order_id": o["id"], "progress": round(progress, 3), "eta": eta,
                      "late": bool(o["due_at"] and eta > o["due_at"])})
        if auto_deliver and progress >= 1.0:
            orders.change_status(conn, o["id"], "DELIVERED", "시뮬레이터 도착", now)
            delivered.append(o["id"])
    return {"minutes": minutes, "moved": moved, "delivered": delivered}
