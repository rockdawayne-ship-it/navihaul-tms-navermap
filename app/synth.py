"""합성 데이터 생성 + 가상 시계 시뮬레이션 + KPI 리포트.

실행 예:
  py -3.13 -m app.synth --vehicles 30 --orders 200 --days 7 --seed 42
  py -3.13 -m app.synth --no-api            # Directions 5 대신 대체 경로 (빠름, 무료)

동작:
  1) 거점 16곳에 차량 N대, 화주 8곳, 오더 M건(상차 희망시각을 기간 내 업무시간에 분산) 생성
  2) 가상 시계를 `step` 분 단위로 진행하며
     - 상차 희망시각 2시간 전부터 접수 오더에 추천 1순위 차량을 자동 배정
     - 차량이 상차지에 도착(공차거리 / 60km/h)하면 상차완료 → 운송중
     - simulator.tick 으로 이동, 도착 시 자동 도착완료
  3) reports/sim_<timestamp>/ 에 kpi.json, orders.csv, vehicles.csv, report.html 저장
결과는 앱 DB(data/tms.db)에 그대로 남아 http://localhost:8520 에서 볼 수 있다.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from . import config, db, dispatch, geo, orders, seed, simulator
from .seed import PLACES

SHIPPERS = ["한빛유통", "대성식품", "코어전자", "그린팜", "세진케미칼", "동방제지", "미래가전", "한솔물류"]
CARGO = {
    "CARGO": ["철강 코일", "건자재 팔레트", "농산물 톤백", "포장재", "기계 부품"],
    "WING": ["생활용품 팔레트", "전자부품 팔레트", "수입잡화", "음료 팔레트", "타이어"],
    "BOX": ["소형가전 박스", "의류 박스", "문구류", "화장품 박스", "서적"],
    "REEFER": ["냉장식품", "냉동식품 팔레트", "신선 농산물", "의약품(냉장)", "유제품"],
}
VTYPE_W = [("CARGO", 0.35), ("WING", 0.35), ("BOX", 0.15), ("REEFER", 0.15)]
TON_BY_TYPE = {"CARGO": [1, 2.5, 5, 11, 25], "WING": [5, 11, 25], "BOX": [1, 2.5, 5], "REEFER": [2.5, 5, 11]}
SURNAMES = "김이박최정강조윤장임한오서신권황안송류전홍"
GIVEN = ["철수", "영희", "민수", "지훈", "우성", "호동", "재석", "동엽", "장훈", "종국", "지효", "수현", "민지", "현우", "서준"]
REGIONS = ["서울", "경기", "인천", "충남", "충북", "대전", "경북", "대구", "부산", "울산", "경남", "전북", "전남", "광주", "강원"]
EMPTY_SPEED_KMH = 60.0
ASSIGN_LEAD_H = 2.0  # 상차 희망 N시간 전부터 배정 시도


def _pick(rng, weighted):
    r, acc = rng.random(), 0.0
    for v, w in weighted:
        acc += w
        if r <= acc:
            return v
    return weighted[-1][0]


# ---------------------------------------------------------------- 생성
def generate(conn, n_vehicles: int, n_orders: int, days: int, start: datetime, rng: random.Random, use_api: bool) -> dict:
    for t in ("vehicle_positions", "order_events", "orders", "vehicles", "shippers"):
        conn.execute(f"DELETE FROM {t}")
    ts = orders.now_iso(start)
    for name in SHIPPERS:
        conn.execute("INSERT INTO shippers (name, contact) VALUES (?,?)", (name, f"담당 010-{rng.randint(1000,9999)}-{rng.randint(1000,9999)}"))
    places = list(PLACES.items())
    plates = set()
    for i in range(n_vehicles):
        vtype = _pick(rng, VTYPE_W)
        cap = rng.choice(TON_BY_TYPE[vtype])
        while True:
            plate = f"{rng.choice(REGIONS)}{rng.randint(10,99)}{rng.choice('가나다라마바사아자하')}{rng.randint(1000,9999)}"
            if plate not in plates:
                plates.add(plate)
                break
        home, (_, lat, lng) = rng.choice(places)
        conn.execute(
            "INSERT INTO vehicles (plate, vehicle_type, capacity_ton, driver_name, driver_phone, status, lat, lng, home_label, updated_at) VALUES (?,?,?,?,?,'IDLE',?,?,?,?)",
            (plate, vtype, cap, rng.choice(SURNAMES) + rng.choice(GIVEN), f"010-{rng.randint(1000,9999)}-{rng.randint(1000,9999)}", lat, lng, home, ts))
    api_calls = 0
    for i in range(n_orders):
        vtype = _pick(rng, VTYPE_W)
        ton = rng.choice(TON_BY_TYPE[vtype])
        weight = round(ton * rng.uniform(0.5, 0.95), 1)
        (oname, (oaddr, olat, olng)), (dname, (daddr, dlat, dlng)) = rng.sample(places, 2)
        day = rng.randint(0, days - 1)
        hour = _pick(rng, [(6, .1), (7, .15), (8, .2), (9, .2), (10, .1), (11, .05), (13, .1), (14, .05), (15, .05)])
        pickup = start + timedelta(days=day, hours=hour, minutes=rng.choice([0, 0, 30]))
        straight = geo.haversine_km(olat, olng, dlat, dlng) * geo.ROAD_FACTOR
        due = pickup + timedelta(hours=max(3, straight / 65 + rng.uniform(1.0, 3.0)))
        payload = {
            "shipper_id": rng.randint(1, len(SHIPPERS)), "origin_name": oname, "origin_addr": oaddr, "origin_lat": olat, "origin_lng": olng,
            "dest_name": dname, "dest_addr": daddr, "dest_lat": dlat, "dest_lng": dlng,
            "pickup_at": pickup.isoformat(), "due_at": due.replace(microsecond=0).isoformat(),
            "vehicle_type": vtype, "weight_ton": weight, "cargo_desc": f"{rng.choice(CARGO[vtype])} {rng.randint(2, 24)}",
        }
        if use_api:
            orders.create_order(conn, payload)
            api_calls += 1
        else:
            _create_order_fallback(conn, payload, i + 1, start)
        if (i + 1) % 25 == 0:
            print(f"  orders {i + 1}/{n_orders}")
    conn.execute("UPDATE orders SET created_at=? ", (ts,))
    return {"vehicles": n_vehicles, "orders": n_orders, "api_calls": api_calls}


def _create_order_fallback(conn, p: dict, seq: int, start: datetime) -> None:
    route = geo.fallback_route(p["origin_lat"], p["origin_lng"], p["dest_lat"], p["dest_lng"])
    order_no = f"SY-{start.strftime('%y%m%d')}-{seq:04d}"
    conn.execute(
        """INSERT INTO orders (order_no, shipper_id, origin_name, origin_addr, origin_lat, origin_lng,
           dest_name, dest_addr, dest_lat, dest_lng, pickup_at, due_at, vehicle_type, weight_ton, cargo_desc,
           status, distance_km, duration_min, route_source, route_path, fare_krw, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'REQUESTED',?,?,?,?,?,?)""",
        (order_no, p["shipper_id"], p["origin_name"], p["origin_addr"], p["origin_lat"], p["origin_lng"],
         p["dest_name"], p["dest_addr"], p["dest_lat"], p["dest_lng"], p["pickup_at"], p["due_at"],
         p["vehicle_type"], p["weight_ton"], p["cargo_desc"], route["distance_km"], route["duration_min"],
         route["source"], json.dumps(route["path"]), dispatch.fare(route["distance_km"], p["weight_ton"]), orders.now_iso(start)))
    oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute("INSERT INTO order_events (order_id, from_status, to_status, note, at) VALUES (?,?,?,?,?)",
                 (oid, None, "REQUESTED", "합성 오더", orders.now_iso(start)))


# ---------------------------------------------------------------- 시뮬레이션
def run(conn, start: datetime, end: datetime, step_min: int = 15, log=print) -> dict:
    """가상 시계를 start→end 로 진행. 반환: 이벤트 통계."""
    clock = start
    arrive_at: dict[int, datetime] = {}  # order_id → 차량 상차지 도착 예정
    stats = {"assigned": 0, "no_candidate_ticks": 0, "loaded": 0, "delivered": 0, "steps": 0}
    while clock <= end:
        iso = clock.isoformat()
        # 1) 배정: 상차 희망 2시간 전 ~ 접수 상태
        lead = (clock + timedelta(hours=ASSIGN_LEAD_H)).isoformat()
        for o in db.rows(conn.execute("SELECT id FROM orders WHERE status='REQUESTED' AND pickup_at<=? ORDER BY pickup_at", (lead,))):
            rec = orders.recommend(conn, o["id"])
            if rec["candidates"]:
                c = rec["candidates"][0]
                orders.assign(conn, o["id"], c["vehicle_id"], f"자동 배정 {c['score']}점", clock)
                arrive_at[o["id"]] = clock + timedelta(hours=c["empty_km"] / EMPTY_SPEED_KMH)
                stats["assigned"] += 1
            else:
                stats["no_candidate_ticks"] += 1
        # 2) 상차: 차량 도착 and 상차 희망시각 도달
        for o in db.rows(conn.execute("SELECT id, pickup_at FROM orders WHERE status='ASSIGNED'")):
            ready = arrive_at.get(o["id"], clock)
            if clock >= ready and iso >= o["pickup_at"]:
                orders.change_status(conn, o["id"], "LOADED", "상차 완료(시뮬)", clock)
                orders.change_status(conn, o["id"], "IN_TRANSIT", "출발(시뮬)", clock)
                stats["loaded"] += 1
        # 3) 이동
        r = simulator.tick(conn, step_min, True, clock)
        stats["delivered"] += len(r["delivered"])
        stats["steps"] += 1
        if clock.hour == 0 and clock.minute == 0:
            log(f"  {clock.date()}  assigned={stats['assigned']} loaded={stats['loaded']} delivered={stats['delivered']}")
        clock += timedelta(minutes=step_min)
    return stats


# ---------------------------------------------------------------- KPI
def kpi_report(conn, start: datetime, end: datetime) -> dict:
    base = orders.kpi(conn)
    rows = db.rows(conn.execute("SELECT * FROM orders"))
    hours = (end - start).total_seconds() / 3600
    vehicles = db.rows(conn.execute("SELECT * FROM vehicles"))
    # 차량별 가동(운송 시간 = duration_min 합)
    busy = {}
    for o in rows:
        if o["vehicle_id"] and o["status"] in ("IN_TRANSIT", "DELIVERED"):
            busy[o["vehicle_id"]] = busy.get(o["vehicle_id"], 0) + (o["duration_min"] or 0) / 60
    util = [min(1.0, busy.get(v["id"], 0) / hours) for v in vehicles]
    waits = []
    for o in rows:
        if o["assigned_at"] and o["created_at"]:
            waits.append((datetime.fromisoformat(o["pickup_at"]) - datetime.fromisoformat(o["assigned_at"])).total_seconds() / 3600)
    delivered = [o for o in rows if o["status"] == "DELIVERED"]
    late = [o for o in delivered if o["due_at"] and o["delivered_at"] > o["due_at"]]
    late_min = [(datetime.fromisoformat(o["delivered_at"]) - datetime.fromisoformat(o["due_at"])).total_seconds() / 60 for o in late]
    by_type = {}
    for o in rows:
        d = by_type.setdefault(o["vehicle_type"], {"orders": 0, "delivered": 0, "unassigned": 0})
        d["orders"] += 1
        d["delivered"] += o["status"] == "DELIVERED"
        d["unassigned"] += o["status"] == "REQUESTED"
    per_vehicle = []
    for v in vehicles:
        trips = [o for o in rows if o["vehicle_id"] == v["id"] and o["status"] in ("IN_TRANSIT", "DELIVERED")]
        per_vehicle.append({
            "plate": v["plate"], "type": v["vehicle_type"], "ton": v["capacity_ton"], "home": v["home_label"],
            "trips": len(trips), "km": round(sum(o["distance_km"] or 0 for o in trips), 1),
            "empty_km": round(sum(o["empty_km"] or 0 for o in trips), 1),
            "fare": int(sum(o["fare_krw"] or 0 for o in trips)),
            "util_pct": round(min(1.0, busy.get(v["id"], 0) / hours) * 100, 1),
        })
    per_vehicle.sort(key=lambda x: -x["fare"])
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "hours": round(hours, 1)},
        **base,
        "unassigned_final": base["by_status"]["REQUESTED"],
        "delivered": len(delivered),
        "late_delivered": len(late),
        "avg_late_min": round(sum(late_min) / len(late_min), 1) if late_min else 0,
        "avg_assign_lead_h": round(sum(waits) / len(waits), 2) if waits else None,
        "vehicle_util_avg_pct": round(sum(util) / len(util) * 100, 1) if util else 0,
        "vehicle_util_min_pct": round(min(util) * 100, 1) if util else 0,
        "vehicle_util_max_pct": round(max(util) * 100, 1) if util else 0,
        "by_vehicle_type": by_type,
        "per_vehicle": per_vehicle,
        "route_sources": {r["route_source"]: r["n"] for r in conn.execute("SELECT route_source, COUNT(*) n FROM orders GROUP BY route_source")},
    }


def write_report(conn, k: dict, out: Path, gen: dict, stats: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "kpi.json").write_text(json.dumps(k, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = ["order_no", "status", "vehicle_type", "weight_ton", "origin_name", "dest_name", "pickup_at", "due_at",
            "vehicle_id", "distance_km", "duration_min", "route_source", "fare_krw", "empty_km", "assigned_at", "loaded_at", "departed_at", "delivered_at"]
    with (out / "orders.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for o in conn.execute(f"SELECT {', '.join(cols)} FROM orders ORDER BY id"):
            w.writerow(list(o))
    with (out / "vehicles.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(k["per_vehicle"][0].keys()))
        w.writeheader()
        w.writerows(k["per_vehicle"])
    (out / "report.html").write_text(_html(k, gen, stats), encoding="utf-8")


def _html(k: dict, gen: dict, stats: dict) -> str:
    card = lambda v, l: f'<div class="c"><b>{v}</b><small>{l}</small></div>'
    bs = k["by_status"]
    ontime = f"{k['on_time_rate']}%" if k["on_time_rate"] is not None else "-"
    rows = "".join(
        f"<tr><td>{v['plate']}</td><td>{dispatch.VEHICLE_TYPES.get(v['type'], v['type'])} {v['ton']}t</td><td>{v['home']}</td>"
        f"<td>{v['trips']}</td><td>{v['km']:,}</td><td>{v['empty_km']:,}</td><td>{v['fare']:,}</td>"
        f"<td><div class='bar'><i style='width:{v['util_pct']}%'></i></div>{v['util_pct']}%</td></tr>"
        for v in k["per_vehicle"])
    types = "".join(f"<tr><td>{dispatch.VEHICLE_TYPES.get(t, t)}</td><td>{d['orders']}</td><td>{d['delivered']}</td><td>{d['unassigned']}</td></tr>"
                    for t, d in k["by_vehicle_type"].items())
    # 상태별 막대
    total = max(1, k["orders_total"])
    seg = "".join(f'<i class="{s}" style="width:{bs[s]/total*100:.1f}%" title="{orders.STATUS_KO[s]} {bs[s]}"></i>' for s in orders.ALLOWED)
    legend = " · ".join(f"{orders.STATUS_KO[s]} {bs[s]}" for s in orders.ALLOWED if bs[s])
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>합성 데이터 시뮬레이션 리포트</title>
<style>
body{{font:14px/1.6 "Pretendard","Malgun Gothic",system-ui;margin:0;background:#f4f6fa;color:#1b2430}}main{{max-width:1100px;margin:0 auto;padding:32px 24px}}
h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:17px;margin:32px 0 10px;border-bottom:2px solid #03c75a;padding-bottom:6px}}.meta{{color:#6b7786;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:16px 0}}.c{{background:#fff;border:1px solid #e3e7ee;border-radius:8px;padding:10px 12px}}.c b{{display:block;font-size:22px}}.c small{{color:#6b7786;font-size:11px}}
table{{width:100%;border-collapse:collapse;background:#fff;font-size:13px}}th,td{{border:1px solid #e3e7ee;padding:6px 8px;text-align:left}}th{{background:#eef1f6}}td:nth-child(n+4){{text-align:right}}
.bar{{display:inline-block;width:90px;height:8px;background:#eef1f6;border-radius:999px;vertical-align:middle;margin-right:6px;overflow:hidden}}.bar i{{display:block;height:100%;background:#2f6fed}}
.stack{{display:flex;height:18px;border-radius:999px;overflow:hidden;background:#eef1f6;margin:6px 0}}.stack i{{display:block;height:100%}}
.REQUESTED{{background:#94a3b8}}.ASSIGNED{{background:#f59f00}}.LOADED{{background:#7c3aed}}.IN_TRANSIT{{background:#2f6fed}}.DELIVERED{{background:#2f9e44}}.CANCELLED{{background:#cbd5e1}}
</style></head><body><main>
<h1>🚛 합성 데이터 시뮬레이션 리포트</h1>
<div class="meta">기간 {k['period']['start'][:16]} ~ {k['period']['end'][:16]} ({k['period']['hours']}h) · 차량 {gen['vehicles']}대 · 오더 {gen['orders']}건 · 경로 출처 {k['route_sources']} · Directions 호출 {gen['api_calls']}회 · 스텝 {stats['steps']}</div>
<div class="grid">
{card(k['orders_total'], '전체 오더')}{card(f"{k['dispatch_rate']}%", '배차율')}{card(k['delivered'], '도착완료')}{card(ontime, '정시 도착률')}
{card(k['unassigned_final'], '기간 내 미배차')}{card(k['late_delivered'], f"지연 도착 (평균 {k['avg_late_min']}분)")}
{card(f"{k['total_km']:,}km", '운행거리')}{card(f"{k['empty_ratio']}%", f"공차율 ({k['empty_km']:,}km)")}{card(f"{k['fare_total']:,}원", '운임 합계')}
{card(f"{k['vehicle_util_avg_pct']}%", f"차량 가동률 평균 (최소 {k['vehicle_util_min_pct']} / 최대 {k['vehicle_util_max_pct']})")}
{card(k['avg_assign_lead_h'], '평균 배정 리드타임(h, 상차 전)')}{card(stats['no_candidate_ticks'], '후보 없음 스텝 수')}
</div>
<h2>오더 상태 분포</h2><div class="stack">{seg}</div><div class="meta">{legend}</div>
<h2>차종별</h2><table><tr><th>차종</th><th>오더</th><th>도착완료</th><th>미배차</th></tr>{types}</table>
<h2>차량별 실적 (운임 순)</h2><table><tr><th>차량</th><th>차종</th><th>거점</th><th>운행</th><th>km</th><th>공차km</th><th>운임</th><th>가동률</th></tr>{rows}</table>
<h2>해석 가이드</h2><ul>
<li><b>미배차</b>가 많으면 해당 차종·톤급 차량 부족 또는 거점 편중. 차종별 표에서 어느 차종이 막혔는지 확인.</li>
<li><b>공차율</b>이 25% 넘으면 거점 배치가 수요와 어긋남. 차량별 표에서 공차km 큰 차량의 거점을 수요 많은 곳으로 이동 검토.</li>
<li><b>가동률</b> 편차가 크면 추천 점수의 공평성 가중치(15점)를 올려 분산. 평균이 30% 미만이면 차량 과잉.</li>
<li><b>지연 도착</b>은 도착 약속시각이 너무 타이트하거나 배정 리드타임이 짧은 경우. 리드타임 2h → 4h 로 늘려 재실행 비교.</li>
</ul>
<p class="meta">원본: kpi.json · orders.csv · vehicles.csv (같은 폴더). 앱 화면: http://localhost:8520</p>
</main></body></html>"""


# ---------------------------------------------------------------- CLI
def main() -> None:
    ap = argparse.ArgumentParser(description="합성 데이터 시뮬레이션")
    ap.add_argument("--vehicles", type=int, default=30)
    ap.add_argument("--orders", type=int, default=200)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--step", type=int, default=15, help="가상 시계 스텝(분)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start", default=None, help="시작일 YYYY-MM-DD (기본: 오늘 00:00)")
    ap.add_argument("--no-api", action="store_true", help="Directions 5 대신 대체 경로")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rng = random.Random(a.seed)
    start = datetime.fromisoformat(a.start) if a.start else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=a.days, hours=12)  # 마지막 날 오더가 도착할 여유
    use_api = (not a.no_api) and config.features()["directions"]
    print(f"generate: vehicles={a.vehicles} orders={a.orders} days={a.days} api={'Directions5' if use_api else 'fallback'}")
    db.init_db()
    with db.get_conn() as conn:
        gen = generate(conn, a.vehicles, a.orders, a.days, start, rng, use_api)
    print(f"simulate: {start} → {end} step={a.step}min")
    with db.get_conn() as conn:
        stats = run(conn, start, end, a.step)
        k = kpi_report(conn, start, end)
        out = Path(a.out) if a.out else config.ROOT / "reports" / f"sim_{datetime.now().strftime('%Y%m%d_%H%M')}"
        write_report(conn, k, out, gen, stats)
    print(json.dumps({x: k[x] for x in ("orders_total", "dispatch_rate", "delivered", "on_time_rate", "unassigned_final",
                                         "late_delivered", "empty_ratio", "vehicle_util_avg_pct", "fare_total")}, ensure_ascii=False))
    print(f"report: {out / 'report.html'}")


if __name__ == "__main__":
    main()
