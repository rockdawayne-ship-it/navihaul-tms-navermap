/* NaviHaul TMS 프론트 — 네이버 지도 v3 */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const api = async (path, opt = {}) => {
    const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opt });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || r.statusText);
    return data;
  };
  const fmtT = (s) => (s ? s.replace("T", " ").slice(5, 16) : "-");
  const fmtW = (n) => (n == null ? "-" : n.toLocaleString("ko-KR") + "원");
  const toast = (msg, err = false) => {
    const t = $("#toast"); t.textContent = msg; t.className = "show" + (err ? " err" : "");
    clearTimeout(toast._h); toast._h = setTimeout(() => (t.className = ""), 2600);
  };

  const state = {
    cfg: null, orders: [], vehicles: [], selected: null, filter: "", autoTimer: null,
    map: null, mapReady: false, vMarkers: new Map(), oMarkers: [], polyline: null, info: null,
    picked: { origin: null, dest: null }, pickMarkers: { origin: null, dest: null },
  };
  const TYPE_KO = { CARGO: "카고", WING: "윙바디", BOX: "탑차", REEFER: "냉장냉동" };
  const VSTAT_KO = { IDLE: "공차", ASSIGNED: "배차", ON_TRIP: "운행", OFF: "휴무" };

  /* ---------- 네이버 지도 ---------- */
  function loadMap() {
    const keyId = state.cfg.map_key_id;
    if (!keyId) return showMapFallback("NCP_MAP_KEY_ID 가 설정되지 않아 지도를 표시할 수 없습니다.");
    window.navermap_authFailure = () =>
      showMapFallback("네이버 지도 인증 실패. NCP 콘솔에서 Web 서비스 URL(<code>" + location.origin + "</code>) 등록과 Dynamic Map 선택을 확인하세요.");
    const s = document.createElement("script");
    s.src = "https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=" + encodeURIComponent(keyId);
    s.onload = initMap;
    s.onerror = () => showMapFallback("지도 스크립트를 불러오지 못했습니다 (네트워크/방화벽).");
    document.head.appendChild(s);
  }
  function showMapFallback(html) {
    const f = $("#mapFallback"); f.innerHTML = "<div><b>🗺️ 지도 미표시</b><br><br>" + html + "<br><br><small>PRD/05_NAVER_MAP_SETUP.md 참고. 나머지 기능은 동작합니다.</small></div>";
    f.classList.remove("hidden");
  }
  function initMap() {
    if (!window.naver || !naver.maps) return showMapFallback("naver.maps 객체를 찾을 수 없습니다.");
    state.map = new naver.maps.Map("map", { center: new naver.maps.LatLng(36.5, 127.8), zoom: 7, mapTypeControl: true, zoomControl: true, zoomControlOptions: { position: naver.maps.Position.TOP_RIGHT } });
    state.info = new naver.maps.InfoWindow({ content: "", borderWidth: 0, backgroundColor: "transparent", disableAnchor: true });
    naver.maps.Event.addListener(state.map, "rightclick", (e) => {
      const side = state.picked.origin ? "dest" : "origin";
      pickPlace(side, { name: `지도 지정 (${e.coord.lat().toFixed(4)}, ${e.coord.lng().toFixed(4)})`, address: "", lat: e.coord.lat(), lng: e.coord.lng() });
      switchTab("new");
      toast(side === "origin" ? "상차지를 지도에서 지정했습니다" : "하차지를 지도에서 지정했습니다");
    });
    naver.maps.Event.addListener(state.map, "click", () => state.info.close());
    state.mapReady = true;
    renderVehicleMarkers(); renderSelectedRoute();
  }
  const htmlIcon = (html, ax = 0.5, ay = 0.5) => ({ content: html, anchor: new naver.maps.Point(ax * 40, ay * 20) });
  function vehicleHtml(v) { return `<div class="marker ${v.status}">🚛 ${v.plate.slice(-4)}</div>`; }
  function vehicleInfo(v) {
    return `<div class="infowin"><b>${v.plate} · ${TYPE_KO[v.vehicle_type]} ${v.capacity_ton}t</b>${v.driver_name || ""} ${v.driver_phone || ""}<br>상태: ${VSTAT_KO[v.status]}${v.order_no ? "<br>오더: " + v.order_no : ""}<br><small>갱신 ${fmtT(v.updated_at)}</small></div>`;
  }
  function renderVehicleMarkers() {
    if (!state.mapReady) return;
    const seen = new Set();
    for (const v of state.vehicles) {
      if (v.lat == null) continue;
      seen.add(v.id);
      const pos = new naver.maps.LatLng(v.lat, v.lng);
      let m = state.vMarkers.get(v.id);
      if (!m) {
        m = new naver.maps.Marker({ position: pos, map: state.map, icon: htmlIcon(vehicleHtml(v)), zIndex: 50 });
        naver.maps.Event.addListener(m, "click", () => { state.info.setContent(vehicleInfo(m._v)); state.info.open(state.map, m); if (m._v.order_id) selectOrder(m._v.order_id); });
        state.vMarkers.set(v.id, m);
      } else { m.setPosition(pos); m.setIcon(htmlIcon(vehicleHtml(v))); }
      m._v = v;
    }
    for (const [id, m] of state.vMarkers) if (!seen.has(id)) { m.setMap(null); state.vMarkers.delete(id); }
  }
  function clearRoute() {
    state.oMarkers.forEach((m) => m.setMap(null)); state.oMarkers = [];
    if (state.polyline) { state.polyline.setMap(null); state.polyline = null; }
  }
  function renderSelectedRoute() {
    if (!state.mapReady) return;
    clearRoute();
    const o = state.selected; if (!o) return;
    const org = new naver.maps.LatLng(o.origin_lat, o.origin_lng), dst = new naver.maps.LatLng(o.dest_lat, o.dest_lng);
    state.oMarkers.push(new naver.maps.Marker({ position: org, map: state.map, icon: htmlIcon(`<div class="pinmark org">▲ 상차 ${o.origin_name}</div>`, 0.1, 1), zIndex: 60 }));
    state.oMarkers.push(new naver.maps.Marker({ position: dst, map: state.map, icon: htmlIcon(`<div class="pinmark dst">▼ 하차 ${o.dest_name}</div>`, 0.1, 1), zIndex: 60 }));
    if (o.route_path && o.route_path.length) {
      const path = o.route_path.map(([lng, lat]) => new naver.maps.LatLng(lat, lng));
      state.polyline = new naver.maps.Polyline({ map: state.map, path, strokeColor: o.route_source === "fallback" ? "#f59f00" : "#2f6fed", strokeWeight: 5, strokeOpacity: 0.85, strokeStyle: o.route_source === "fallback" ? "shortdash" : "solid" });
      const b = new naver.maps.LatLngBounds(org, dst); path.forEach((p) => b.extend(p));
      if (o.vehicle_lat != null) b.extend(new naver.maps.LatLng(o.vehicle_lat, o.vehicle_lng));
      state.map.fitBounds(b, { top: 60, right: 60, bottom: 60, left: 60 });
    }
  }
  function renderPickMarker(side) {
    if (!state.mapReady) return;
    const p = state.picked[side];
    if (state.pickMarkers[side]) { state.pickMarkers[side].setMap(null); state.pickMarkers[side] = null; }
    if (!p) return;
    state.pickMarkers[side] = new naver.maps.Marker({ position: new naver.maps.LatLng(p.lat, p.lng), map: state.map, icon: htmlIcon(`<div class="pinmark ${side === "origin" ? "org" : "dst"}">${side === "origin" ? "▲ 상차(신규)" : "▼ 하차(신규)"}</div>`, 0.1, 1), zIndex: 70 });
    state.map.panTo(new naver.maps.LatLng(p.lat, p.lng));
  }

  /* ---------- 데이터 ---------- */
  async function refresh(keepDetail = true) {
    const [orders, vehicles, kpi] = await Promise.all([api("/api/orders"), api("/api/vehicles"), api("/api/kpi")]);
    state.orders = orders; state.vehicles = vehicles;
    renderKpi(kpi); renderOrders(); renderVehicles(); renderVehicleMarkers();
    if (keepDetail && state.selected) await selectOrder(state.selected.id, false);
  }
  function renderBadges() {
    const f = state.cfg.features;
    const b = (on, label) => `<span class="badge ${on ? "on" : "off"}">${label} ${on ? "✓" : "대체"}</span>`;
    $("#badges").innerHTML = b(f.map, "지도") + b(f.directions, "경로") + b(f.geocode || f.local_search, "검색");
  }
  function renderKpi(k) {
    const c = (v, l, warn = false) => `<div class="card ${warn ? "warn" : ""}"><b>${v}</b><small>${l}</small></div>`;
    $("#kpi").innerHTML =
      c(k.orders_total, "전체 오더") + c(k.by_status.REQUESTED, "미배차") + c(k.dispatch_rate + "%", "배차율") +
      c(k.in_transit, "운송중") + c(k.late_now, "지연 예상", k.late_now > 0) +
      c(k.on_time_rate == null ? "-" : k.on_time_rate + "%", "정시 도착률") +
      c(k.total_km.toLocaleString() + "km", `운행거리 (공차 ${k.empty_ratio}%)`) +
      c(`${k.vehicles.IDLE}/${state.vehicles.length}`, "공차 차량");
  }
  function renderOrders() {
    const statuses = state.cfg.statuses;
    $("#statusFilters").innerHTML = `<button data-f="" class="${state.filter === "" ? "active" : ""}">전체</button>` +
      Object.entries(statuses).map(([k, v]) => `<button data-f="${k}" class="${state.filter === k ? "active" : ""}">${v}</button>`).join("");
    const list = state.orders.filter((o) => !state.filter || o.status === state.filter);
    $("#orderList").innerHTML = list.map((o) => {
      const late = o.status === "IN_TRANSIT" && o.due_at && o.eta > o.due_at;
      return `<li data-id="${o.id}" class="${state.selected?.id === o.id ? "active" : ""}">
        <div class="t"><span>${o.order_no}</span><span class="status ${o.status}">${o.status_ko}</span></div>
        <div class="s">${o.origin_name} → ${o.dest_name}</div>
        <div class="s">${TYPE_KO[o.vehicle_type]} ${o.weight_ton}t · ${o.distance_km}km · ${o.shipper_name || ""}${o.plate ? " · " + o.plate : ""}${late ? ' <span class="late">지연</span>' : ""}</div>
      </li>`;
    }).join("") || `<li class="s">해당 상태 오더 없음</li>`;
  }
  function renderVehicles() {
    $("#vehicleList").innerHTML = state.vehicles.map((v) => `<li data-vid="${v.id}">
      <div class="t"><span>${v.plate}</span><span class="status ${v.status === "ON_TRIP" ? "IN_TRANSIT" : v.status === "ASSIGNED" ? "ASSIGNED" : "DELIVERED"}">${VSTAT_KO[v.status]}</span></div>
      <div class="s">${TYPE_KO[v.vehicle_type]} ${v.capacity_ton}t · ${v.driver_name} ${v.driver_phone}</div>
      <div class="s">${v.order_no ? "오더 " + v.order_no : "거점 " + (v.home_label || "")}</div></li>`).join("");
  }

  async function selectOrder(id, pan = true) {
    const o = await api(`/api/orders/${id}`);
    state.selected = o;
    renderOrders();
    renderDetail(o);
    if (pan) renderSelectedRoute(); else if (state.polyline) { renderSelectedRoute(); }
    if (["REQUESTED"].includes(o.status)) loadRecommend(o.id);
  }
  function renderDetail(o) {
    const late = o.status === "IN_TRANSIT" && o.due_at && o.eta > o.due_at;
    const next = state.cfg.allowed[o.status] || [];
    const nextBtns = next.filter((s) => s !== "ASSIGNED").map((s) =>
      `<button data-to="${s}" class="${s === "CANCELLED" ? "danger" : ""}">${state.cfg.statuses[s]}</button>`).join("");
    $("#detail").innerHTML = `
      <h3><span>${o.order_no}</span><span class="status ${o.status}">${o.status_ko}</span></h3>
      <dl>
        <dt>화주</dt><dd>${o.shipper_name || "-"}</dd>
        <dt>상차지</dt><dd>${o.origin_name}<br><small>${o.origin_addr || ""}</small></dd>
        <dt>하차지</dt><dd>${o.dest_name}<br><small>${o.dest_addr || ""}</small></dd>
        <dt>화물</dt><dd>${TYPE_KO[o.vehicle_type]} · ${o.weight_ton}t · ${o.cargo_desc || ""}</dd>
        <dt>상차/도착</dt><dd>${fmtT(o.pickup_at)} / ${fmtT(o.due_at)}</dd>
        <dt>경로</dt><dd>${o.distance_km}km · ${Math.round(o.duration_min)}분 <small>(${o.route_source === "naver-directions" ? "네이버 길찾기" : "대체 계산"})</small></dd>
        <dt>운임</dt><dd>${fmtW(o.fare_krw)}</dd>
        <dt>차량</dt><dd>${o.plate ? `${o.plate} · ${o.driver_name || ""} ${o.driver_phone || ""}<br><small>공차 ${o.empty_km ?? 0}km</small>` : "미배정"}</dd>
        ${o.status === "IN_TRANSIT" ? `<dt>진행</dt><dd><div class="progress"><i style="width:${Math.round(o.progress * 100)}%"></i></div>${Math.round(o.progress * 100)}% · ETA ${fmtT(o.eta)} ${late ? '<span class="late">· 지연 예상</span>' : ""}</dd>` : ""}
      </dl>
      <div class="btns">${nextBtns}</div>
      <div id="recommend"></div>
      <h4>이력</h4><ol class="events">${o.events.map((e) => `<li>${fmtT(e.at)} ${state.cfg.statuses[e.to_status]}${e.note ? " — " + e.note : ""}</li>`).join("")}</ol>`;
    $$("#detail .btns button").forEach((b) => b.onclick = async () => {
      const to = b.dataset.to;
      const note = to === "CANCELLED" ? (prompt("취소 사유") ?? null) : "";
      if (note === null) return;
      try { await api(`/api/orders/${o.id}/status`, { method: "POST", body: JSON.stringify({ to, note }) }); toast(`${state.cfg.statuses[to]} 처리`); await refresh(); }
      catch (e) { toast(e.message, true); }
    });
  }
  async function loadRecommend(oid) {
    const rec = await api(`/api/orders/${oid}/recommend`);
    const box = $("#recommend"); if (!box) return;
    box.innerHTML = `<h4>🤖 배차 추천 (상위 ${rec.candidates.length})</h4>` +
      (rec.candidates.map((c, i) => `<div class="cand ${i === 0 ? "rank1" : ""}">
        <div class="h"><span>${i + 1}위 ${c.plate} · ${TYPE_KO[c.vehicle_type]} ${c.capacity_ton}t</span><span class="score">${c.score}점</span></div>
        <ul>${c.reasons.map((r) => `<li>${r}</li>`).join("")}</ul>
        <button class="primary" data-vid="${c.vehicle_id}">${c.driver_name || ""} 배정</button></div>`).join("") || `<div class="rej">조건에 맞는 공차 차량이 없습니다.</div>`) +
      (rec.rejected.length ? `<details class="rej"><summary>제외 ${rec.rejected.length}대</summary>${rec.rejected.map((r) => `${r.plate}: ${r.reason}`).join("<br>")}</details>` : "");
    $$("#recommend button").forEach((b) => b.onclick = async () => {
      try { await api(`/api/orders/${oid}/assign`, { method: "POST", body: JSON.stringify({ vehicle_id: +b.dataset.vid }) }); toast("배정 완료"); await refresh(); }
      catch (e) { toast(e.message, true); }
    });
  }

  /* ---------- 오더 등록 ---------- */
  async function searchPlace(side) {
    const q = $(side === "origin" ? "#originQ" : "#destQ").value.trim(); if (!q) return;
    const ul = $(side === "origin" ? "#originResults" : "#destResults");
    ul.innerHTML = "<li>검색 중…</li>";
    const { items } = await api("/api/places?q=" + encodeURIComponent(q));
    ul.innerHTML = items.map((p, i) => `<li data-i="${i}">${p.name}<small>${p.address} · ${p.source}</small></li>`).join("") ||
      `<li><small>결과 없음. ${state.cfg.features.geocode || state.cfg.features.local_search ? "도로명 주소로 다시 검색하거나" : "검색 API 키가 없습니다."} 지도에서 우클릭으로 지정하세요.</small></li>`;
    $$("li[data-i]", ul).forEach((li) => li.onclick = () => { pickPlace(side, items[+li.dataset.i]); ul.innerHTML = ""; });
  }
  function pickPlace(side, p) {
    state.picked[side] = p;
    $(side === "origin" ? "#originPicked" : "#destPicked").textContent = `✔ ${p.name} (${p.lat.toFixed(5)}, ${p.lng.toFixed(5)})`;
    renderPickMarker(side);
  }
  async function submitOrder(e) {
    e.preventDefault();
    const f = e.target, msg = $("#formMsg"); msg.className = "msg";
    const { origin, dest } = state.picked;
    if (!origin || !dest) { msg.className = "msg err"; msg.textContent = "상차지·하차지를 모두 선택하세요."; return; }
    const body = {
      shipper_id: +f.shipper_id.value || null,
      origin_name: origin.name, origin_addr: origin.address, origin_lat: origin.lat, origin_lng: origin.lng,
      dest_name: dest.name, dest_addr: dest.address, dest_lat: dest.lat, dest_lng: dest.lng,
      pickup_at: f.pickup_at.value || null, due_at: f.due_at.value || null,
      vehicle_type: f.vehicle_type.value, weight_ton: +f.weight_ton.value, cargo_desc: f.cargo_desc.value,
    };
    msg.textContent = "경로 계산 중…";
    try {
      const o = await api("/api/orders", { method: "POST", body: JSON.stringify(body) });
      msg.textContent = `등록 완료 ${o.order_no} · ${o.distance_km}km · ${Math.round(o.duration_min)}분 · ${fmtW(o.fare_krw)}`;
      state.picked = { origin: null, dest: null }; renderPickMarker("origin"); renderPickMarker("dest");
      $("#originPicked").textContent = "미선택"; $("#destPicked").textContent = "미선택"; f.cargo_desc.value = "";
      await refresh(false); switchTab("orders"); await selectOrder(o.id);
    } catch (err) { msg.className = "msg err"; msg.textContent = err.message; }
  }

  /* ---------- 시뮬 ---------- */
  async function tick() {
    const minutes = +$("#simMin").value || 10;
    const r = await api("/api/sim/tick", { method: "POST", body: JSON.stringify({ minutes }) });
    if (r.delivered.length) toast(`도착 완료 ${r.delivered.length}건`);
    await refresh();
  }
  function toggleAuto() {
    if (state.autoTimer) { clearInterval(state.autoTimer); state.autoTimer = null; $("#btnAuto").textContent = "⏵ 자동"; return; }
    state.autoTimer = setInterval(tick, 2000); $("#btnAuto").textContent = "⏸ 자동 중"; tick();
  }

  /* ---------- UI 배선 ---------- */
  function switchTab(name) {
    $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    $$(".tab").forEach((t) => t.classList.toggle("hidden", t.id !== "tab-" + name));
  }
  function wire() {
    $$(".tabs button").forEach((b) => b.onclick = () => switchTab(b.dataset.tab));
    $("#statusFilters").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; state.filter = b.dataset.f; renderOrders(); };
    $("#orderList").onclick = (e) => { const li = e.target.closest("li[data-id]"); if (li) selectOrder(+li.dataset.id); };
    $("#vehicleList").onclick = (e) => {
      const li = e.target.closest("li[data-vid]"); if (!li) return;
      const v = state.vehicles.find((x) => x.id === +li.dataset.vid);
      if (v && state.mapReady) { state.map.panTo(new naver.maps.LatLng(v.lat, v.lng)); const m = state.vMarkers.get(v.id); if (m) { state.info.setContent(vehicleInfo(v)); state.info.open(state.map, m); } }
      if (v?.order_id) selectOrder(v.order_id);
    };
    $$("button[data-side]").forEach((b) => b.onclick = () => searchPlace(b.dataset.side));
    ["#originQ", "#destQ"].forEach((id, i) => $(id).onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); searchPlace(i ? "dest" : "origin"); } });
    $("#orderForm").onsubmit = submitOrder;
    $("#btnTick").onclick = tick;
    $("#btnAuto").onclick = toggleAuto;
    $("#btnReset").onclick = async () => { if (!confirm("샘플 데이터로 초기화할까요? 등록한 오더가 삭제됩니다.")) return; await api("/api/reset", { method: "POST" }); state.selected = null; $("#detail").innerHTML = '<div class="empty">오더를 선택하면 상세·추천·경로가 표시됩니다.</div>'; clearRoute(); await refresh(false); toast("초기화 완료"); };
  }

  async function boot() {
    state.cfg = await api("/api/config");
    renderBadges();
    const shippers = await api("/api/shippers");
    $("#shipperSel").innerHTML = shippers.map((s) => `<option value="${s.id}">${s.name}</option>`).join("");
    wire();
    await refresh(false);
    loadMap();
    setInterval(() => refresh(), 15000);
  }
  boot().catch((e) => toast("초기화 실패: " + e.message, true));
})();
