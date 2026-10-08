"""두 시뮬레이션 리포트 폴더의 kpi.json 을 비교한 compare.html 생성.

실행: py -3.13 -m app.compare reports/cmp_v30 reports/cmp_v15 --labels "차량 30대" "차량 15대" --out reports/compare_v30_v15.html
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROWS = [
    ("배차율 (%)", "dispatch_rate", "높을수록 좋음"),
    ("도착완료 (건)", "delivered", "높을수록 좋음"),
    ("기간 내 미배차 (건)", "unassigned_final", "낮을수록 좋음"),
    ("정시 도착률 (%)", "on_time_rate", "높을수록 좋음"),
    ("지연 도착 (건)", "late_delivered", "낮을수록 좋음"),
    ("평균 지연 (분)", "avg_late_min", "낮을수록 좋음"),
    ("평균 배정 리드타임 (h, 상차 전)", "avg_assign_lead_h", "양수 = 상차 전 배정. 음수 = 상차 시각 지난 뒤 배정"),
    ("운행거리 (km)", "total_km", "오더 동일하면 비슷"),
    ("공차거리 (km)", "empty_km", "낮을수록 좋음"),
    ("공차율 (%)", "empty_ratio", "낮을수록 좋음"),
    ("차량 가동률 평균 (%)", "vehicle_util_avg_pct", "너무 낮으면 차량 과잉, 너무 높으면 지연"),
    ("차량 가동률 최소/최대 (%)", ("vehicle_util_min_pct", "vehicle_util_max_pct"), "편차 크면 공평성 가중치 조정"),
    ("운임 합계 (원)", "fare_total", ""),
]


def _fmt(v):
    if isinstance(v, float):
        return f"{v:,.1f}"
    if isinstance(v, int):
        return f"{v:,}"
    return "-" if v is None else str(v)


def build(dirs: list[Path], labels: list[str]) -> str:
    ks = [json.loads((d / "kpi.json").read_text(encoding="utf-8")) for d in dirs]
    head = "".join(f"<th>{l}</th>" for l in labels)
    body = ""
    for name, key, note in ROWS:
        cells = []
        for k in ks:
            if isinstance(key, tuple):
                cells.append(" / ".join(_fmt(k[x]) for x in key))
            else:
                cells.append(_fmt(k[key]))
        body += f"<tr><td>{name}</td>{''.join(f'<td>{c}</td>' for c in cells)}<td class='n'>{note}</td></tr>"
    types = sorted({t for k in ks for t in k["by_vehicle_type"]})
    tbody = ""
    for t in types:
        cells = "".join(f"<td>{k['by_vehicle_type'].get(t, {}).get('delivered', 0)} / {k['by_vehicle_type'].get(t, {}).get('orders', 0)}</td>" for k in ks)
        tbody += f"<tr><td>{t}</td>{cells}</tr>"
    meta = " · ".join(f"{l}: 차량 {len(k['per_vehicle'])}대, 오더 {k['orders_total']}건, {k['period']['hours']}h" for l, k in zip(labels, ks))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>시나리오 비교</title>
<style>body{{font:14px/1.6 "Pretendard","Malgun Gothic",system-ui;margin:0;background:#f4f6fa;color:#1b2430}}main{{max-width:1000px;margin:0 auto;padding:32px 24px}}
h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:16px;margin:28px 0 8px;border-bottom:2px solid #03c75a;padding-bottom:6px}}.meta{{color:#6b7786;font-size:13px}}
table{{width:100%;border-collapse:collapse;background:#fff;font-size:13px}}th,td{{border:1px solid #e3e7ee;padding:7px 10px;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{background:#eef1f6}}td.n{{text-align:left;color:#6b7786;font-size:12px}}
</style></head><body><main>
<h1>🚛 시나리오 비교</h1><div class="meta">{meta}</div>
<h2>KPI</h2><table><tr><th>지표</th>{head}<th>해석</th></tr>{body}</table>
<h2>차종별 도착완료 / 오더</h2><table><tr><th>차종</th>{head}</tr>{tbody}</table>
</main></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--labels", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    labels = a.labels or a.dirs
    Path(a.out).write_text(build([Path(d) for d in a.dirs], labels), encoding="utf-8")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
