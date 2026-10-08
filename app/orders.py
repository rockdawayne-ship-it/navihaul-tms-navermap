"""오더 생성·배정·상태 전이. 상태 전이의 유일한 기준은 ALLOWED."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import db, dispatch, geo, naver

ALLOWED = {
    "REQUESTED": {"ASSIGNED", "CANCELLED"},
    "ASSIGNED": {"LOADED", "CANCELLED"},
    "LOADED": {"IN_TRANSIT"},
    "IN_TRANSIT": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}
STATUS_KO = {
    "REQUESTED": "접수", "ASSIGNED": "배차", "LOADED": "상차완료",
    "IN_TRANSIT": "운송중", "DELIVERED": "도착완료", "CANCELLED": "취소",
}


class TransitionError(Exception):
    pass


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def next_order_no(conn) -> str:
    prefix = "TO-" + datetime.now().strftime("%y%m%d") + "-"
    row = db.one(conn.execute("SELECT order_no FROM orders WHERE order_no LIKE ? ORDER BY order_no DESC LIMIT 1", (prefix + "%",)))
    seq = int(row["order_no"].rsplit("-", 1)[1]) + 1 if row else 1
    return f"{prefix}{seq:03d}"


def create_order(conn, payload: dict) -> dict:
    route = naver.directions(payload["origin_lat"], payload["origin_lng"], payload["dest_lat"], payload["dest_lng"])
    order_no = next_order_no(conn)
    created = now_iso()
    cur = conn.execute(
        """INSERT INTO orders (order_no, shipper_id, origin_name, origin_addr, origin_lat, origin_lng,
           dest_name, dest_addr, dest_lat, dest_lng, pickup_at, due_at, vehicle_type, weight_ton, cargo_desc,
           status, distance_km, duration_min, route_source, route_path, fare_krw, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'REQUESTED',?,?,?,?,?,?)""",
        (order_no, payload.get("shipper_id"), payload["origin_name"], payload.get("origin_addr", ""),
         payload["origin_lat"], payload["origin_lng"], payload["dest_name"], payload.get("dest_addr", ""),
         payload["dest_lat"], payload["dest_lng"], payload.get("pickup_at"), payload.get("due_at"),
         payload["vehicle_type"], payload["weight_ton"], payload.get("cargo_desc", ""),
         route["distance_km"], route["duration_min"], route["source"], json.dumps(route["path"]),
         dispatch.fare(route["distance_km"], payload["weight_ton"]), created),
    )
    oid = cur.lastrowid
    conn.execute("INSERT INTO order_events (order_id, from_status, to_status, note, at) VALUES (?,?,?,?,?)",
                 (oid, None, "REQUESTED", "오더 등록", created))
    return get_order(conn, oid)


def get_order(conn, oid: int) -> dict | None:
    o = db.one(conn.execute(
        """SELECT o.*, s.name AS shipper_name, v.plate, v.driver_name, v.driver_phone,
                  v.lat AS vehicle_lat, v.lng AS vehicle_lng
           FROM orders o LEFT JOIN shippers s ON s.id=o.shipper_id LEFT JOIN vehicles v ON v.id=o.vehicle_id
           WHERE o.id=?""", (oid,)))
    if not o:
        return None
    o["route_path"] = json.loads(o["route_path"]) if o.get("route_path") else []
    o["status_ko"] = STATUS_KO.get(o["status"], o["status"])
    o["events"] = db.rows(conn.execute("SELECT * FROM order_events WHERE order_id=? ORDER BY at, id", (oid,)))
    return o


def list_orders(conn, status: str | None = None) -> list[dict]:
    sql = """SELECT o.id, o.order_no, o.status, o.shipper_id, s.name AS shipper_name,
                    o.origin_name, o.origin_lat, o.origin_lng, o.dest_name, o.dest_lat, o.dest_lng,
                    o.pickup_at, o.due_at, o.vehicle_type, o.weight_ton, o.cargo_desc,
                    o.vehicle_id, v.plate, v.driver_name, o.distance_km, o.duration_min, o.route_source,
                    o.fare_krw, o.empty_km, o.progress, o.eta, o.created_at
             FROM orders o LEFT JOIN shippers s ON s.id=o.shipper_id LEFT JOIN vehicles v ON v.id=o.vehicle_id"""
    args: tuple = ()
    if status:
        sql += " WHERE o.status=?"
        args = (status,)
    sql += " ORDER BY o.id DESC"
    out = db.rows(conn.execute(sql, args))
    for o in out:
        o["status_ko"] = STATUS_KO.get(o["status"], o["status"])
    return out


def trip_counts(conn) -> dict[int, int]:
    return {r["vehicle_id"]: r["n"] for r in conn.execute(
        "SELECT vehicle_id, COUNT(*) AS n FROM orders WHERE vehicle_id IS NOT NULL AND status NOT IN ('CANCELLED') GROUP BY vehicle_id")}


def recommend(conn, oid: int) -> dict:
    o = get_order(conn, oid)
    if not o:
        raise KeyError("order not found")
    vehicles = db.rows(conn.execute("SELECT * FROM vehicles"))
    return dispatch.recommend(o, vehicles, trip_counts(conn))


def _transition(conn, o: dict, to: str, note: str = "") -> None:
    if to not in ALLOWED.get(o["status"], set()):
        raise TransitionError(f"{STATUS_KO.get(o['status'])} → {STATUS_KO.get(to, to)} 전이 불가")
    conn.execute("INSERT INTO order_events (order_id, from_status, to_status, note, at) VALUES (?,?,?,?,?)",
                 (o["id"], o["status"], to, note, now_iso()))


def assign(conn, oid: int, vehicle_id: int, note: str = "") -> dict:
    o = get_order(conn, oid)
    if not o:
        raise KeyError("order not found")
    v = db.one(conn.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)))
    if not v:
        raise KeyError("vehicle not found")
    ok, reason = dispatch.eligible(o, v)
    if not ok:
        raise TransitionError(f"배정 불가: {reason}")
    _transition(conn, o, "ASSIGNED", note or f"{v['plate']} 배정")
    empty_km = round(geo.haversine_km(v["lat"], v["lng"], o["origin_lat"], o["origin_lng"]) * geo.ROAD_FACTOR, 1)
    ts = now_iso()
    conn.execute("UPDATE orders SET status='ASSIGNED', vehicle_id=?, empty_km=?, assigned_at=? WHERE id=?",
                 (vehicle_id, empty_km, ts, oid))
    conn.execute("UPDATE vehicles SET status='ASSIGNED', updated_at=? WHERE id=?", (ts, vehicle_id))
    return get_order(conn, oid)


def change_status(conn, oid: int, to: str, note: str = "") -> dict:
    o = get_order(conn, oid)
    if not o:
        raise KeyError("order not found")
    _transition(conn, o, to, note)
    ts = now_iso()
    vid = o["vehicle_id"]
    if to == "LOADED":
        conn.execute("UPDATE orders SET status='LOADED', loaded_at=?, progress=0 WHERE id=?", (ts, oid))
        conn.execute("UPDATE vehicles SET status='ON_TRIP', lat=?, lng=?, updated_at=? WHERE id=?",
                     (o["origin_lat"], o["origin_lng"], ts, vid))
    elif to == "IN_TRANSIT":
        eta = (datetime.now() + timedelta(minutes=o["duration_min"] or 0)).replace(microsecond=0).isoformat()
        conn.execute("UPDATE orders SET status='IN_TRANSIT', departed_at=?, eta=?, progress=0 WHERE id=?", (ts, eta, oid))
    elif to == "DELIVERED":
        conn.execute("UPDATE orders SET status='DELIVERED', delivered_at=?, progress=1, eta=? WHERE id=?", (ts, ts, oid))
        conn.execute("UPDATE vehicles SET status='IDLE', lat=?, lng=?, updated_at=? WHERE id=?",
                     (o["dest_lat"], o["dest_lng"], ts, vid))
    elif to == "CANCELLED":
        conn.execute("UPDATE orders SET status='CANCELLED', vehicle_id=NULL WHERE id=?", (oid,))
        if vid:
            conn.execute("UPDATE vehicles SET status='IDLE', updated_at=? WHERE id=?", (ts, vid))
    else:
        conn.execute("UPDATE orders SET status=? WHERE id=?", (to, oid))
    return get_order(conn, oid)


def kpi(conn) -> dict:
    counts = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) n FROM orders GROUP BY status")}
    total = sum(counts.values())
    active = total - counts.get("CANCELLED", 0)
    assigned_plus = active - counts.get("REQUESTED", 0)
    agg = db.one(conn.execute(
        """SELECT COALESCE(SUM(distance_km),0) km, COALESCE(SUM(empty_km),0) empty, COALESCE(SUM(fare_krw),0) fare
           FROM orders WHERE status IN ('ASSIGNED','LOADED','IN_TRANSIT','DELIVERED')"""))
    delivered = db.rows(conn.execute("SELECT delivered_at, due_at FROM orders WHERE status='DELIVERED'"))
    on_time = sum(1 for d in delivered if not d["due_at"] or (d["delivered_at"] or "") <= d["due_at"])
    late_now = db.one(conn.execute(
        "SELECT COUNT(*) n FROM orders WHERE status='IN_TRANSIT' AND due_at IS NOT NULL AND eta > due_at"))["n"]
    vstat = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) n FROM vehicles GROUP BY status")}
    return {
        "orders_total": total,
        "by_status": {k: counts.get(k, 0) for k in ALLOWED},
        "dispatch_rate": round(assigned_plus / active * 100, 1) if active else 0.0,
        "in_transit": counts.get("IN_TRANSIT", 0),
        "late_now": late_now,
        "on_time_rate": round(on_time / len(delivered) * 100, 1) if delivered else None,
        "total_km": round(agg["km"], 1),
        "empty_km": round(agg["empty"], 1),
        "empty_ratio": round(agg["empty"] / (agg["km"] + agg["empty"]) * 100, 1) if (agg["km"] + agg["empty"]) else 0.0,
        "fare_total": int(agg["fare"]),
        "vehicles": {k: vstat.get(k, 0) for k in ("IDLE", "ASSIGNED", "ON_TRIP", "OFF")},
    }
