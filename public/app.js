'use strict';
/* GreenRoute AI — staff web app (admin, dispatcher, fleet manager, ops manager). */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 0) => (v == null ? '<span class="badge warn">thiếu dữ liệu</span>' : Number(v).toLocaleString('vi-VN', { maximumFractionDigits: d }));
// Last word that starts with a letter: "Phạm Văn Tài (VAN-01)" → "T", not "(".
const initial = name => ([...String(name).split(/\s+/)].reverse().find(w => /^\p{L}/u.test(w)) || '?')[0].toUpperCase();
const t2 = m => (m == null ? '' : `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(Math.round(m % 60)).padStart(2, '0')}`);
const ago = s => (s == null ? 'chưa có' : s < 60 ? `${s}s trước` : s < 3600 ? `${Math.round(s / 60)} phút trước` : `${Math.round(s / 3600)} giờ trước`);
const api = Auth.api;

const PALETTE = ['#16a34a', '#2563eb', '#d97706', '#9333ea', '#dc2626', '#0891b2', '#65a30d', '#db2777', '#4f46e5', '#ea580c', '#0d9488', '#a16207'];
const colorFor = id => { let h = 0; for (const c of String(id)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return PALETTE[h % PALETTE.length]; };
const METRIC_LABEL = {
  distance_km: 'Quãng đường (km)', duration_min: 'Tổng thời gian (phút)', total_cost_vnd: 'Tổng chi phí (VND)',
  energy_cost_vnd: 'Chi phí năng lượng (VND)', co2_direct_kg: 'CO₂ trực tiếp (kg)', co2_grid_indirect_kg: 'CO₂ gián tiếp điện lưới (kg)',
  co2_per_km: 'CO₂ / km (kg)', cost_per_order_vnd: 'Chi phí / đơn (VND)', co2_per_order: 'CO₂ / đơn (kg)',
  vehicles_used: 'Số xe dùng', orders_unassigned: 'Đơn chưa phân công',
};
const STATUS_LABEL = { pending: 'Chưa giao', delivered: 'Đã giao', failed: 'Thất bại' };

const PAGES = [
  { id: 'overview', icon: '🏠', title: 'Tổng quan', sub: 'Quy trình, chỉ số và cảnh báo trong ngày' },
  { id: 'plan', icon: '🧭', title: 'Lập tuyến', sub: 'OR-Tools phân đơn cho đội xe, so sánh với phương án cơ sở' },
  { id: 'live', icon: '📡', title: 'Theo dõi trực tiếp', sub: 'Vị trí tài xế, vệt di chuyển và tiến độ giao hàng' },
  { id: 'orders', icon: '📦', title: 'Đơn hàng', sub: 'Nhập, kiểm tra và quản lý đơn', roles: ['admin', 'dispatcher', 'ops_manager'] },
  { id: 'vehicles', icon: '🚚', title: 'Đội xe', sub: 'Sức chứa, chi phí, nhiên liệu và tình trạng xe' },
  { id: 'fuel', icon: '⛽', title: 'Kịch bản nhiên liệu', sub: 'So sánh chi phí và phát thải khi đổi nhiên liệu' },
  { id: 'history', icon: '🗂', title: 'Lịch sử & báo cáo', sub: 'Các lần tối ưu, xuất CSV/XLSX' },
  { id: 'admin', icon: '⚙️', title: 'Quản trị', sub: 'Tài khoản, cấu hình hệ số, dữ liệu mẫu, nhật ký', roles: ['admin'] },
  { id: 'method', icon: 'ℹ️', title: 'Phương pháp & giả định', sub: 'Công thức, nguồn hệ số, phạm vi phát thải' },
];

let CFG = null, RUN = null, ME = null, PAGE = null;
let planMap, planLayers, liveMap, liveLayers, liveFitted = false, liveTimer = null, FOCUS = null;
const can = (...roles) => roles.includes(ME?.role);

// ---------------------------------------------------------------- UI helpers
function toast(msg, type = '') {
  const el = Object.assign(document.createElement('div'), { className: `toast ${type}`, textContent: msg });
  $('#toasts').appendChild(el);
  setTimeout(() => el.remove(), type === 'err' ? 6000 : 3500);
}
async function busy(btn, fn) {
  const label = btn.innerHTML; btn.disabled = true;
  try { await fn(); } catch (e) { toast(e.message, 'err'); } finally { btn.disabled = false; btn.innerHTML = label; }
}
const alertBox = (type, html) => `<div class="alert ${type}">${html}</div>`;
const empty = (icon, html) => `<div class="empty"><div class="big">${icon}</div><p>${html}</p></div>`;
function store(key, val) { try { localStorage.setItem(key, val); } catch { /* storage blocked */ } }
function recall(key) { try { return localStorage.getItem(key); } catch { return null; } }

function applyRoles() {
  $$('[data-roles]').forEach(el => {
    if (el.dataset.roles.split(',').includes(ME.role)) el.removeAttribute('data-hidden-role');
    else el.setAttribute('data-hidden-role', '');
  });
}

// ---------------------------------------------------------------- Navigation
function buildMenu() {
  const pages = PAGES.filter(p => !p.roles || p.roles.includes(ME.role));
  $('#menu').innerHTML = pages.map((p, i) =>
    `${i === 3 ? '<div class="menu-label">Dữ liệu</div>' : ''}${i === 0 ? '<div class="menu-label">Vận hành</div>' : ''}` +
    `<button data-page="${p.id}"><span>${p.icon}</span> ${p.title}</button>`).join('');
  $('#menu').onclick = e => { const b = e.target.closest('[data-page]'); if (b) go(b.dataset.page); };
}
function go(id) {
  const page = PAGES.find(p => p.id === id && (!p.roles || p.roles.includes(ME.role))) || PAGES[0];
  PAGE = page.id;
  $$('.page').forEach(p => p.classList.toggle('active', p.id === `page-${page.id}`));
  $$('#menu [data-page]').forEach(b => b.classList.toggle('active', b.dataset.page === page.id));
  $('#page-title').textContent = page.title;
  $('#page-sub').textContent = page.sub;
  $('#sidebar').classList.remove('open');
  store('gr_page', page.id);
  clearInterval(liveTimer);
  const loaders = {
    overview: loadOverview, plan: () => { ensurePlanMap(); setTimeout(() => { planMap.invalidateSize(); if (RUN) drawPlanMap(RUN); }, 60); },
    live: () => { ensureLiveMap(); setTimeout(() => liveMap.invalidateSize(), 50); loadLive(); liveTimer = setInterval(() => loadLive().catch(() => {}), 10000); },
    orders: loadOrders, vehicles: loadVehicles, fuel: renderFuelEditor, history: loadHistory, admin: loadAdmin, method: renderMethod,
  };
  Promise.resolve(loaders[page.id]?.()).catch(e => toast(e.message, 'err'));
}
document.addEventListener('click', e => { const b = e.target.closest('[data-go]'); if (b) go(b.dataset.go); });
$('#menu-toggle').onclick = () => $('#sidebar').classList.toggle('open');

// ---------------------------------------------------------------- Overview
async function loadOverview() {
  const [runs, vehicles, live, orders] = await Promise.all([
    api('/api/optimization').then(r => r.body), api('/api/vehicles').then(r => r.body), api('/api/tracking').then(r => r.body),
    can('admin', 'dispatcher', 'ops_manager') ? api('/api/orders').then(r => r.body) : Promise.resolve(null),
  ]);
  const latest = runs[0], published = runs.find(r => r.published), plan = live.plan;
  const avail = vehicles.filter(v => v.available).length;
  const counts = plan?.counts || { pending: 0, delivered: 0, failed: 0 };
  const total = counts.pending + counts.delivered + counts.failed;
  const steps = [
    { t: 'Đơn hàng', ok: orders == null ? null : orders.length > 0, s: orders == null ? 'Điều phối viên phụ trách' : `${orders.length} đơn đã nhập`, go: 'orders', show: orders != null },
    { t: 'Đội xe', ok: avail > 0, s: `${avail}/${vehicles.length} xe sẵn sàng · ${vehicles.filter(v => v.driver).length} xe có tài xế`, go: 'vehicles' },
    { t: 'Lập tuyến tối ưu', ok: !!latest, s: latest ? `${new Date(latest.created_at).toLocaleString('vi-VN')} · ${latest.totals.vehicles_used} xe · ${fmt(latest.totals.distance_km, 1)} km` : 'Chưa chạy', go: 'plan' },
    { t: 'Phát hành cho tài xế', ok: !!published, s: published ? `Đã phát hành ${new Date(plan.published_at).toLocaleTimeString('vi-VN')} bởi ${esc(plan.published_by)}` : 'Chưa phát hành', go: 'plan' },
    { t: 'Theo dõi giao hàng', ok: total > 0 && counts.pending === 0, s: total ? `${counts.delivered} đã giao · ${counts.failed} thất bại · ${counts.pending} còn lại` : 'Chưa có tuyến chạy', go: 'live' },
  ];
  const current = steps.findIndex(s => s.ok === false);
  $('#ov-steps').innerHTML = steps.map((s, i) => `<div class="step ${s.ok ? 'done' : i === current ? 'current' : ''}">
      <div class="n">${s.ok ? '✓' : i + 1}</div><div class="t">${s.t}</div><div class="s">${s.s}</div>
      <button class="sm ${i === current ? '' : 'secondary'}" data-go="${s.go}">${i === current ? 'Làm ngay →' : 'Mở'}</button></div>`).join('');
  $('#ov-updated').textContent = `Cập nhật ${new Date().toLocaleTimeString('vi-VN')}`;

  const t = latest?.totals;
  const sharing = live.vehicles.filter(v => v.sharing && !v.stale).length;
  $('#ov-kpis').innerHTML = [
    ['📦 Đơn đã phân công', t ? `${t.orders_assigned}/${t.orders_total}` : '—', t ? `${t.assignment_rate_pct}% đơn` : 'chưa tối ưu', '--brand'],
    ['🚚 Xe sử dụng', t ? t.vehicles_used : '—', `${avail} xe sẵn sàng`, '--blue'],
    ['🛣 Tổng quãng đường', t ? `${fmt(t.distance_km, 1)} km` : '—', t ? `${fmt(t.duration_min / 60, 1)} giờ xe chạy` : '', '--violet'],
    ['💰 Tổng chi phí', t ? `${fmt(t.total_cost_vnd / 1000, 0)}k ₫` : '—', t?.cost_per_order_vnd ? `${fmt(t.cost_per_order_vnd)} ₫/đơn` : '', '--amber'],
    ['🌿 CO₂ trực tiếp', t ? `${fmt(t.co2_direct_kg, 1)} kg` : '—', t?.co2_per_order != null ? `${fmt(t.co2_per_order * 1000, 0)} g/đơn` : '', '--brand'],
    ['✅ Tiến độ giao', total ? `${Math.round((counts.delivered + counts.failed) / total * 100)}%` : '—', total ? `${counts.delivered}/${total} thành công` : 'chưa phát hành', '--blue'],
    ['📡 Tài xế online', `${sharing}`, `${live.vehicles.length} xe trong kế hoạch`, '--red'],
  ].map(([l, v, d, c]) => `<div class="kpi" style="--accent:var(${c})"><div class="l">${l}</div><div class="v">${v}</div><div class="d muted">${d}</div></div>`).join('');

  $('#ov-progress').innerHTML = live.vehicles.length ? `<div class="list">${live.vehicles.map(progressRow).join('')}</div>`
    : empty('🛵', 'Chưa có tuyến được phát hành.');

  const alerts = [];
  if (t?.orders_unassigned) alerts.push(['warn', `<b>${t.orders_unassigned} đơn chưa phân công</b> trong phương án mới nhất.`, 'plan']);
  const noDriver = live.vehicles.filter(v => !v.driver && v.total);
  if (noDriver.length) alerts.push(['err', `<b>${noDriver.length} xe chưa có tài xế:</b> ${noDriver.map(v => esc(v.vehicle_id)).join(', ')}.`, can('admin') ? 'admin' : null]);
  const lost = live.vehicles.filter(v => v.sharing && v.stale);
  if (lost.length) alerts.push(['warn', `<b>Mất tín hiệu:</b> ${lost.map(v => `${esc(v.vehicle_id)} (${ago(v.age_s)})`).join(', ')}.`, 'live']);
  if (counts.failed) alerts.push(['err', `<b>${counts.failed} đơn giao thất bại</b> — cần xử lý lại.`, 'live']);
  if (latest && !published) alerts.push(['info', 'Phương án mới nhất <b>chưa phát hành</b> — tài xế chưa nhận được tuyến.', 'plan']);
  $('#ov-alerts').innerHTML = alerts.length ? alerts.map(([k, h, g]) => `<div class="alert ${k}" style="align-items:center"><div style="flex:1">${h}</div>${g ? `<button class="sm secondary" data-go="${g}">Xem</button>` : ''}</div>`).join('')
    : alertBox('ok', '✓ Không có cảnh báo.');
  loadAnalytics().catch(e => toast(e.message, 'err'));
}

function progressRow(v) {
  const pctOk = v.total ? v.stops.filter(x => x.status === 'delivered').length / v.total * 100 : 0;
  const pctBad = v.total ? v.stops.filter(x => x.status === 'failed').length / v.total * 100 : 0;
  return `<div class="item clickable" data-focus="${esc(v.vehicle_id)}">
    <div class="top"><span class="dot" style="background:${colorFor(v.vehicle_id)}"></span><span class="id">${esc(v.vehicle_id)}</span>
      <span class="muted">${v.driver ? esc(v.driver.full_name) : '<span class="bad">chưa gán tài xế</span>'}</span>
      <span style="margin-left:auto">${signalBadge(v)}</span><a href="#" class="oid" data-vehicle="${esc(v.vehicle_id)}" style="font-size:12px">Chi tiết</a></div>
    <div style="display:flex;align-items:center;gap:10px;margin-top:8px"><div class="progress" style="flex:1"><span class="p-ok" style="width:${pctOk}%"></span><span class="p-bad" style="width:${pctBad}%"></span></div><small class="muted">${v.done}/${v.total}</small></div>
    ${v.next_stop ? `<div class="meta"><span>➡ Tiếp: <b>${esc(v.next_stop.order_id)}</b> (dự kiến ${esc(v.next_stop.arrival)})</span>${v.next_stop.distance_km != null ? `<span>cách ${fmt(v.next_stop.distance_km, 1)} km</span>` : ''}${v.trail_km ? `<span>đã đi ${fmt(v.trail_km, 1)} km</span>` : ''}</div>` : v.total ? '<div class="meta good">✓ Hoàn thành tuyến</div>' : ''}
  </div>`;
}
function signalBadge(v) {
  if (!v.driver) return '<span class="badge">—</span>';
  if (!v.sharing) return '<span class="badge">⏸ Chưa bắt đầu ca</span>';
  if (v.waiting_gps) return '<span class="badge info">⏳ Đã bắt đầu ca · đang chờ GPS</span>';
  if (v.stale) return `<span class="badge warn">⚠ Mất tín hiệu · ${ago(v.age_s)}</span>`;
  return `<span class="badge ok"><span class="live-dot"></span> Online · ${ago(v.age_s)}</span>`;
}
document.addEventListener('click', e => {
  const el = e.target.closest('[data-focus]'); if (!el) return;
  FOCUS = el.dataset.focus;
  if (PAGE !== 'live') go('live'); else focusVehicle(FOCUS);
});

// ---------------------------------------------------------------- Plan (optimisation)
function ensurePlanMap() {
  if (planMap) return;
  planMap = L.map('map', { zoomControl: true }).setView([10.78, 106.68], 12);
  baseTiles(planMap);
  planLayers = L.layerGroup().addTo(planMap);
}
function depotIcon() { return L.divIcon({ className: '', html: '<div class="veh-marker" style="--c:#142019">🏭 Kho</div>', iconSize: null }); }
function stopIcon(n, color, status = 'pending') {
  const bg = status === 'delivered' ? '#16a34a' : status === 'failed' ? '#dc2626' : color;
  return L.divIcon({ className: '', iconSize: null, html: `<div style="width:22px;height:22px;border-radius:50%;background:${bg};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35);color:#fff;font-size:10px;font-weight:700;display:grid;place-items:center;transform:translate(-50%,-50%)">${status === 'delivered' ? '✓' : status === 'failed' ? '✕' : n}</div>` });
}

function drawPlanMap(run) {
  ensurePlanMap(); planLayers.clearLayers();
  const d = run.depot, bounds = [[d.latitude, d.longitude]];
  L.marker([d.latitude, d.longitude], { icon: depotIcon() }).bindPopup(`<b>${esc(d.name)}</b>`).addTo(planLayers);
  const assigned = new Set();
  run.optimized.routes.forEach(r => {
    const c = colorFor(r.vehicle_id);
    const pts = [[d.latitude, d.longitude], ...r.stops.map(s => [s.latitude, s.longitude]), [d.latitude, d.longitude]];
    L.polyline(pts, { color: c, weight: 4, opacity: .85, dashArray: r.fuel_blend_code === 'electricity' ? '8 6' : null })
      .bindTooltip(`${esc(r.vehicle_id)} · ${r.distance_km} km`, { sticky: true }).addTo(planLayers);
    const peakStyle = { color: '#d03b3b', weight: 3, dashArray: '2 7', opacity: .95 };
    r.stops.forEach((s, k) => { if (s.peak) L.polyline([pts[k], pts[k + 1]], peakStyle).bindTooltip(`🚦 ${esc(r.vehicle_id)} → ${esc(s.order_id)}: +${s.peak_delay_min}′ (ước tính)`, { sticky: true }).addTo(planLayers); });
    if (r.return_peak) L.polyline(pts.slice(-2), peakStyle).addTo(planLayers);
    r.stops.forEach((s, k) => {
      assigned.add(s.order_id); bounds.push([s.latitude, s.longitude]);
      L.marker([s.latitude, s.longitude], { icon: stopIcon(k + 1, c) })
        .bindPopup(`<a href="#" class="oid" data-order="${esc(s.order_id)}">${esc(s.order_id)}</a><br>Xe <a href="#" class="oid" data-vehicle="${esc(r.vehicle_id)}">${esc(r.vehicle_id)}</a> · điểm ${k + 1}<br>Dự kiến ${s.arrival}${s.window ? `<br>Khung giờ ${s.window}` : ''}`).addTo(planLayers);
    });
  });
  run.input.orders.filter(o => !assigned.has(o.order_id)).forEach(o => {
    bounds.push([o.latitude, o.longitude]);
    L.circleMarker([o.latitude, o.longitude], { radius: 7, color: '#dc2626', fillOpacity: .7 }).bindPopup(`<b>${esc(o.order_id)}</b><br>CHƯA PHÂN CÔNG`).addTo(planLayers);
  });
  planMap.fitBounds(bounds, { padding: [24, 24] });
}

function deltaHtml(p, lowerIsBetter = true) {
  if (p == null) return '';
  const good = lowerIsBetter ? p < 0 : p > 0;
  return `<span class="${p === 0 ? 'muted' : good ? 'good' : 'bad'}">${p > 0 ? '▲ +' : p < 0 ? '▼ ' : ''}${p}%</span>`;
}

function renderRun(run) {
  RUN = run;
  $('#plan-empty').hidden = true; $('#plan-body').hidden = false;
  $('#btn-publish').disabled = !run.optimized.routes.length;
  $('#publish-msg').innerHTML = run.published_at ? alertBox('ok', `✓ Phương án này đã phát hành lúc ${new Date(run.published_at).toLocaleString('vi-VN')}.`) : '';
  const t = run.optimized.totals, cmp = Object.fromEntries(run.comparison.rows.map(r => [r.metric, r.change_pct]));
  // When baseline serves fewer orders, raw km/vehicle deltas flatter the optimiser — show the reason instead.
  const vsBase = m => run.comparison.comparable === false
    ? `<span class="muted" title="${esc(run.comparison.comparable_note)}">baseline chỉ giao ${run.baseline.totals.orders_assigned} đơn</span>`
    : deltaHtml(cmp[m]) + ' so với baseline';
  $('#kpis').innerHTML = [
    ['📦 Đơn đã phân công', `${t.orders_assigned}/${t.orders_total}`, `${t.assignment_rate_pct}%`, '--brand'],
    ['🚚 Xe sử dụng', t.vehicles_used, vsBase('vehicles_used'), '--blue'],
    ['🛣 Quãng đường', `${fmt(t.distance_km, 1)} km`, vsBase('distance_km'), '--violet'],
    ['💰 Tổng chi phí', `${fmt(t.total_cost_vnd)} ₫`, `${fmt(t.cost_per_order_vnd)} ₫/đơn · ${deltaHtml(cmp.cost_per_order_vnd)}`, '--amber'],
    ['🌿 CO₂ trực tiếp', `${fmt(t.co2_direct_kg, 2)} kg`, `${fmt((t.co2_per_order ?? 0) * 1000)} g/đơn · ${deltaHtml(cmp.co2_per_order)}`, '--brand'],
    ['⚡ CO₂ gián tiếp (điện)', `${fmt(t.co2_grid_indirect_kg, 2)} kg`, 'báo cáo riêng, không cộng', '--muted'],
    ['🚦 Giờ cao điểm', `${t.peak_legs ?? 0} chặng`, `+${fmt(t.peak_delay_min)}′ ước tính · ${t.late_risk ?? 0} đơn nguy cơ trễ`, '--red'],
  ].map(([l, v, d, c]) => `<div class="kpi" style="--accent:var(${c})"><div class="l">${l}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join('');

  $('#plan-v-routes').innerHTML = run.optimized.routes.map(r => {
    const c = colorFor(r.vehicle_id), vt = CFG.vehicle_types[r.vehicle_type]?.label || r.vehicle_type;
    return `<div class="item"><div class="top"><span class="dot" style="background:${c}"></span><a href="#" class="oid id" data-vehicle="${esc(r.vehicle_id)}">${esc(r.vehicle_id)}</a>
        <span class="badge">${esc(vt)}</span><span class="badge ${r.fuel_blend_code === 'electricity' ? 'info' : ''}">${esc(CFG.fuels[r.fuel_blend_code]?.label || r.fuel_blend_code)}</span>
        <span style="margin-left:auto" class="muted">${r.start}–${r.end}</span></div>
      <div class="meta"><span>📍 ${r.stops.length} điểm</span><span>🛣 ${fmt(r.distance_km, 1)} km</span><span>💰 ${fmt(r.operating_cost_vnd + (r.energy_cost_vnd ?? 0))} ₫</span><span>🌿 ${fmt(r.co2_direct_kg, 2)} kg</span>${r.peak_legs ? `<span>🚦 ${r.peak_legs} chặng giờ cao điểm · +${fmt(r.peak_delay_min)}′</span>` : ''}${r.late_risk ? `<span class="bad">⚠ ${r.late_risk} nguy cơ trễ</span>` : ''}</div>
      <div style="display:flex;align-items:center;gap:8px;margin-top:8px"><div class="progress" style="flex:1"><span class="p-ok" style="width:${Math.min(r.utilization_weight_pct, 100)}%;background:${c}"></span></div><small class="muted">tải ${r.load_weight_kg}/${r.capacity_weight_kg} kg</small></div>
      <details><summary>Thứ tự giao &amp; hệ số phát thải</summary><ol class="stops">${r.stops.map((s, i) => `<li><span class="i">${i + 1}.</span><a href="#" class="oid" data-order="${esc(s.order_id)}">${esc(s.order_id)}</a><span class="muted">${s.arrival}${s.window ? ` · khung ${s.window}` : ''}${s.wait_min ? ` · chờ ${s.wait_min}′` : ''}</span>${s.peak ? ` <span title="giờ cao điểm +${s.peak_delay_min}′">🚦</span>` : ''}${s.late_risk ? ' <span class="badge bad">nguy cơ trễ</span>' : ''}</li>`).join('')}</ol>
      <p class="hint" style="margin:8px 0 0">${r.factor ? `Hệ số ${r.factor.value} ${esc(r.factor.unit)} — ${esc(r.factor.source)} (${r.factor.year ?? '?'})${r.factor.official ? '' : ' <span class="badge sim">mô phỏng</span>'}` : 'Không có hệ số'}</p></details></div>`;
  }).join('');

  $('#plan-v-compare').innerHTML = (run.comparison.comparable === false ? alertBox('warn', `⚠ ${esc(run.comparison.comparable_note)}`) : '') +
    `<div class="tbl-wrap" style="margin-top:8px"><table><thead><tr><th>Chỉ số</th><th class="num">Baseline</th><th class="num">OR-Tools</th><th class="num">Thay đổi</th></tr></thead><tbody>${
      run.comparison.rows.map(r => `<tr><td>${METRIC_LABEL[r.metric] || r.metric}</td><td class="num">${fmt(r.reference, 2)}</td><td class="num">${fmt(r.candidate, 2)}</td><td class="num">${r.change_pct == null ? '—' : deltaHtml(r.change_pct)}</td></tr>`).join('')
    }</tbody></table></div><p class="hint">Baseline: ${esc(run.baseline.meta.algorithm)}. Cùng đơn, đội xe, ma trận khoảng cách và ràng buộc.<br>
    Bộ giải: ${esc(run.optimized.meta.algorithm)} · ${(run.optimized.meta.time_ms / 1000).toFixed(1)} giây · <b>${run.optimized.meta.status}</b></p>`;

  const un = run.optimized.unassigned;
  $('#un-count').textContent = un.length ? `(${un.length})` : '';
  $('#plan-v-unassigned').innerHTML = un.length ? `<div class="tbl-wrap"><table><thead><tr><th>Đơn</th><th>Lý do</th></tr></thead><tbody>${
    un.map(u => `<tr><td><a href="#" class="oid" data-order="${esc(u.order_id)}">${esc(u.order_id)}</a><br><code>${u.code}</code></td><td>${esc(u.message)}</td></tr>`).join('')}</tbody></table></div>` : alertBox('ok', '✓ Tất cả đơn đã được phân công.');

  const warns = [...(t.warnings || [])];
  if (run.assumptions.routing_fallback) warns.unshift(run.assumptions.routing_fallback);
  $('#run-warnings').innerHTML = warns.map(w => alertBox('warn', `⚠ ${esc(w)}`)).join('') +
    alertBox('info', `ℹ ${esc(run.assumptions.scope_note)}<br>ℹ ${esc(run.assumptions.routing_note)} · Cấu hình <code>${esc(run.assumptions.fuel_config_version)}</code>`);
  drawPlanMap(run);
  renderFuelEditor();
}
$('#plan-seg').onclick = e => {
  const b = e.target.closest('[data-v]'); if (!b) return;
  $$('#plan-seg button').forEach(x => x.classList.toggle('active', x === b));
  ['routes', 'compare', 'unassigned'].forEach(v => { $(`#plan-v-${v}`).hidden = v !== b.dataset.v; });
};

$('#btn-run').onclick = e => busy(e.target, async () => {
  e.target.innerHTML = '⏳ OR-Tools đang tính…';
  // Never let the previous plan be published while a new one is being computed.
  $('#btn-publish').disabled = true;
  $('#publish-msg').innerHTML = '';
  const { body } = await api('/api/optimization/run', { method: 'POST', body: JSON.stringify({ weights: { co2_vnd_per_kg: Number($('#w-co2').value) || 0 }, time_limit_s: Number($('#time-limit').value) || 5 }) });
  renderRun(body); toast(`Đã tối ưu: ${body.optimized.totals.orders_assigned}/${body.optimized.totals.orders_total} đơn, ${body.optimized.totals.vehicles_used} xe`, 'ok');
});
$('#btn-publish').onclick = e => busy(e.target, async () => {
  if (!RUN || !confirm('Phát hành phương án này cho tài xế?\nPhương án đang phát hành trước đó (nếu có) sẽ bị thay thế.')) return;
  const { body } = await api(`/api/optimization/${RUN.id}/publish`, { method: 'POST' });
  RUN.published_at = body.published_at;
  $('#publish-msg').innerHTML = alertBox('ok', `✓ Đã phát hành lúc ${new Date(body.published_at).toLocaleTimeString('vi-VN')}. Tài xế mở <b>${location.origin}/driver.html</b> để nhận tuyến.`) +
    (body.vehicles_without_driver.length ? alertBox('warn', `⚠ Xe chưa gán tài xế (không ai nhận tuyến): <b>${body.vehicles_without_driver.map(esc).join(', ')}</b>. Gán trong Quản trị → Tài khoản.`) : '');
  toast('Đã phát hành cho tài xế', 'ok');
});
$('#btn-depot').onclick = e => busy(e.target, async () => {
  await api('/api/depot', { method: 'PUT', body: JSON.stringify({ name: $('#depot-name').value, latitude: $('#depot-lat').value, longitude: $('#depot-lng').value }) });
  toast('Đã lưu kho — chạy tối ưu lại để áp dụng', 'ok');
});

// Pick the depot on a map (no geocoding service yet — gap A12).
let depotMap, depotPin;
function setDepotInputs(ll) {
  $('#depot-lat').value = ll.lat.toFixed(6);
  $('#depot-lng').value = ll.lng.toFixed(6);
}
$('#btn-depot-pick').onclick = () => {
  const box = $('#depot-pick');
  box.hidden = !box.hidden;
  if (box.hidden) return;
  const lat = Number($('#depot-lat').value) || 10.78, lng = Number($('#depot-lng').value) || 106.70;
  if (!depotMap) {
    depotMap = L.map('depot-map').setView([lat, lng], 16);
    baseTiles(depotMap);
    depotPin = L.marker([lat, lng], { draggable: true, icon: depotIcon() }).addTo(depotMap);
    depotPin.on('dragend', () => setDepotInputs(depotPin.getLatLng()));
    depotMap.on('click', ev => { depotPin.setLatLng(ev.latlng); setDepotInputs(ev.latlng); });
  }
  setTimeout(() => { depotMap.invalidateSize(); depotMap.setView([lat, lng], 16); depotPin.setLatLng([lat, lng]); }, 50);
};
['#depot-lat', '#depot-lng'].forEach(s => $(s).addEventListener('change', () => {
  // Accept "10.8030, 106.7065" pasted from Google Maps into either box.
  const pair = $(s).value.match(/(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)/);
  if (pair) { $('#depot-lat').value = pair[1]; $('#depot-lng').value = pair[2]; }
  const lat = Number($('#depot-lat').value), lng = Number($('#depot-lng').value);
  if (depotMap && lat && lng) { depotPin.setLatLng([lat, lng]); depotMap.setView([lat, lng], 16); }
}));

// ---------------------------------------------------------------- Live tracking
function ensureLiveMap() {
  if (liveMap) return;
  liveMap = L.map('live-map').setView([10.78, 106.68], 12);
  baseTiles(liveMap);
  liveLayers = L.layerGroup().addTo(liveMap);
}
let LIVE = null;
async function loadLive() {
  ensureLiveMap();
  const [{ body: live }, { body: board }] = await Promise.all([api('/api/tracking'), api('/api/dispatch')]);
  LIVE = live;
  liveLayers.clearLayers();
  const bounds = [];
  if (live.depot) { L.marker([live.depot.latitude, live.depot.longitude], { icon: depotIcon() }).addTo(liveLayers); bounds.push([live.depot.latitude, live.depot.longitude]); }
  live.vehicles.forEach(v => {
    const c = colorFor(v.vehicle_id);
    if (v.stops.length && live.depot) L.polyline([[live.depot.latitude, live.depot.longitude], ...v.stops.map(s => [s.latitude, s.longitude])], { color: c, weight: 2, opacity: .35, dashArray: '4 6' }).addTo(liveLayers);
    v.stops.forEach((s, i) => { bounds.push([s.latitude, s.longitude]); L.marker([s.latitude, s.longitude], { icon: stopIcon(i + 1, c, s.status) }).bindPopup(`<a href="#" class="oid" data-order="${esc(s.order_id)}">${esc(s.order_id)}</a> · ${STATUS_LABEL[s.status]}<br>Xe ${esc(v.vehicle_id)} · dự kiến ${s.arrival}`).addTo(liveLayers); });
    if (v.trail.length > 1) L.polyline(v.trail, { color: c, weight: 5, opacity: .9 }).addTo(liveLayers);
    if (v.last) {
      bounds.push([v.last.lat, v.last.lng]);
      if (v.last.acc) L.circle([v.last.lat, v.last.lng], { radius: v.last.acc, color: c, weight: 1, fillOpacity: .08 }).addTo(liveLayers);
      L.marker([v.last.lat, v.last.lng], { zIndexOffset: 1000, icon: L.divIcon({ className: '', iconSize: null, html: `<div class="veh-marker ${v.stale ? 'stale' : ''}" style="--c:${c}">🚚 ${esc(v.vehicle_id)}</div>` }) })
        .bindPopup(`<b>${esc(v.vehicle_id)}</b> — ${esc(v.driver?.full_name || '')}<br>Cập nhật ${ago(v.age_s)} · ±${v.last.acc ?? '?'} m${v.last.spd != null ? `<br>Tốc độ ${Math.round(v.last.spd * 3.6)} km/h` : ''}<br>Đã đi ${v.trail_km} km`).addTo(liveLayers);
    }
  });
  if (!liveFitted && bounds.length) { liveMap.fitBounds(bounds, { padding: [24, 24] }); liveFitted = true; }
  const online = live.vehicles.filter(v => v.sharing && !v.stale).length;
  $('#live-counts').innerHTML = `<span class="badge ok"><span class="live-dot"></span> ${online} online</span> <span class="badge">${live.vehicles.length} xe</span>`;
  $('#live-updated').textContent = `Tự làm mới 15 giây · ${new Date().toLocaleTimeString('vi-VN')}`;
  $('#live-list').innerHTML = live.vehicles.length ? live.vehicles.map(progressRow).join('')
    : empty('📡', 'Chưa có tuyến được phát hành. Vào <b>Lập tuyến</b> → chạy tối ưu → Phát hành.');
  renderDispatch(board);
  if (FOCUS) { focusVehicle(FOCUS); FOCUS = null; }
}
function focusVehicle(id) {
  const v = LIVE?.vehicles.find(x => x.vehicle_id === id); if (!v) return;
  if (v.last) liveMap.flyTo([v.last.lat, v.last.lng], 15);
  else if (v.stops.length) liveMap.fitBounds(v.stops.map(s => [s.latitude, s.longitude]), { padding: [30, 30] });
  else toast(`${id}: chưa có vị trí`);
}
$('#btn-live-refresh').onclick = e => busy(e.target, loadLive);

function locationCell(s) {
  if (!s.location_check) return '';
  if (s.location_check === 'missing') return `<span class="badge">không có định vị</span><br><small class="muted">${esc(s.location_error || '')}</small>`;
  const l = s.location;
  return `<span class="badge ${s.location_check === 'ok' ? 'ok' : 'bad'}">${s.location_check === 'ok' ? '📍 đúng vị trí' : '⚠ xa điểm giao'}</span>
    <br><small class="muted">cách ${fmt(s.distance_to_stop_m)} m (±${fmt(l.accuracy_m)} m) · <a href="https://www.google.com/maps/search/?api=1&query=${l.latitude},${l.longitude}" target="_blank" rel="noopener">xem</a></small>`;
}
function renderDispatch(b) {
  if (!b) { $('#dispatch').innerHTML = empty('📭', 'Chưa có phương án nào được phát hành.'); return; }
  $('#dispatch').innerHTML = `<p class="hint" style="margin-top:0">Phát hành bởi <b>${esc(b.published_by)}</b> lúc ${new Date(b.published_at).toLocaleString('vi-VN')} · ${b.counts.delivered} đã giao · ${b.counts.failed} thất bại · ${b.counts.pending} còn lại</p>
    <div class="tbl-wrap"><table><thead><tr><th>Xe</th><th>#</th><th>Đơn</th><th>Dự kiến</th><th>Khung giờ</th><th>Trạng thái</th><th>Thực tế</th><th>Xác nhận vị trí</th><th>Lý do / ghi chú</th></tr></thead><tbody>${
      b.routes.flatMap(r => r.stops.map((s, i) => `<tr><td>${i === 0 ? `<a href="#" class="oid" data-vehicle="${esc(r.vehicle_id)}"><span class="dot" style="background:${colorFor(r.vehicle_id)}"></span> ${esc(r.vehicle_id)}</a><br><small class="muted">${r.driver ? esc(r.driver.full_name) : 'chưa gán'}</small>` : ''}</td>
        <td>${i + 1}</td><td><a href="#" class="oid" data-order="${esc(s.order_id)}">${esc(s.order_id)}</a></td><td>${s.arrival}</td><td>${esc(s.window)}</td>
        <td><span class="badge ${s.status}">${STATUS_LABEL[s.status]}</span>${s.on_time === false ? ' <span class="badge bad">trễ</span>' : ''}</td>
        <td>${esc(s.actual_time || '')}</td><td>${locationCell(s)}</td><td>${esc(s.reason_label || '')} ${esc(s.note || '')}</td></tr>`)).join('')
    }</tbody></table></div>`;
}

// ---------------------------------------------------------------- Orders
let ORDERS = [];
function reportHtml(r) {
  let h = '';
  if (r.errors?.length) h += alertBox('err', `<div><b>${r.errors.length} dòng lỗi — chưa lưu dữ liệu nào.</b> Sửa file rồi nhập lại:<ul>${r.errors.slice(0, 30).map(e => `<li>Dòng ${e.line} ${esc(e.order_id || e.vehicle_id || '')}: ${e.errors.map(esc).join('; ')}</li>`).join('')}</ul></div>`);
  else if (r.imported != null) h += alertBox('ok', `✓ Đã lưu ${r.imported} dòng (tổng ${r.total}).`);
  if (r.warnings?.length) h += alertBox('warn', `<div><b>${r.warnings.length} cảnh báo</b><ul>${r.warnings.slice(0, 10).map(w => `<li>Dòng ${w.line} ${esc(w.order_id || w.vehicle_id || '')}: ${esc(w.message)}</li>`).join('')}</ul></div>`);
  return h;
}
async function loadOrders() {
  if (!can('admin', 'dispatcher', 'ops_manager')) return [];
  ORDERS = (await api('/api/orders')).body;
  renderOrders();
  return ORDERS;
}
function renderOrders() {
  const q = $('#orders-search').value.trim().toLowerCase();
  const rows = q ? ORDERS.filter(o => [o.order_id, o.customer_name, o.address, o.phone, o.note].some(x => String(x || '').toLowerCase().includes(q))) : ORDERS;
  $('#orders-count').textContent = `Đơn hàng (${rows.length}${q ? `/${ORDERS.length}` : ''})`;
  $('#orders-table').innerHTML = rows.length ? `<div class="tbl-wrap"><table><thead><tr><th>Mã đơn</th><th>Khách hàng</th><th>Địa chỉ</th><th class="num">kg</th><th class="num">m³</th><th>Khung giờ</th><th class="num">Dừng</th><th>Ghi chú</th><th></th></tr></thead><tbody>${
    rows.map(o => `<tr><td><a href="#" class="oid" data-order="${esc(o.order_id)}">${esc(o.order_id)}</a>${o.priority ? ' <span class="badge warn">ưu tiên</span>' : ''}</td><td>${esc(o.customer_name)}<br><small class="muted">${esc(o.phone)}</small></td>
      <td>${esc(o.address)}<br><small class="muted">${o.latitude}, ${o.longitude}</small></td><td class="num">${o.weight_kg}</td><td class="num">${o.volume_m3}</td>
      <td>${o.tw_start != null || o.tw_end != null ? `${t2(o.tw_start)}–${t2(o.tw_end)}` : '<span class="muted">cả ngày</span>'}</td><td class="num">${o.service_time_min}′</td><td><small>${esc(o.note)}</small></td>
      <td>${can('admin', 'dispatcher') ? `<button class="secondary sm" data-edit-order="${esc(o.order_id)}">Sửa</button> <button class="danger sm" data-del-order="${esc(o.order_id)}">Xóa</button>` : ''}</td></tr>`).join('')
  }</tbody></table></div>` : empty('📦', q ? 'Không có đơn khớp từ khóa.' : 'Chưa có đơn hàng. Nhập file CSV/XLSX hoặc thêm thủ công.');
}
$('#orders-search').oninput = renderOrders;
$('#orders-table').onclick = async e => {
  if (e.target.dataset.editOrder) { editOrder(e.target.dataset.editOrder); return; }
  const id = e.target.dataset.delOrder;
  if (id && confirm(`Xóa đơn ${id}?`)) { await api(`/api/orders/${encodeURIComponent(id)}`, { method: 'DELETE' }); toast(`Đã xóa ${id}`); loadOrders(); }
};
$('#btn-orders-import').onclick = e => busy(e.target, async () => {
  const f = $('#orders-file').files[0]; if (!f) throw new Error('Chọn file CSV/XLSX trước');
  const fd = new FormData(); fd.append('file', f);
  const { body } = await api(`/api/orders/import?mode=${$('#orders-mode').value}`, { method: 'POST', body: fd });
  $('#orders-report').innerHTML = reportHtml(body); loadOrders();
});
$('#btn-orders-clear').onclick = async () => { if (confirm('Xóa TẤT CẢ đơn hàng?')) { await api('/api/orders', { method: 'DELETE' }); toast('Đã xóa tất cả đơn'); loadOrders(); } };
let EDITING_ORDER = null;  // order_id while the form edits an existing order (F-02: tạo/sửa/xóa)
$('#order-form').onsubmit = async e => {
  e.preventDefault();
  const data = JSON.stringify(Object.fromEntries(new FormData(e.target)));
  const { body } = EDITING_ORDER
    ? await api(`/api/orders/${encodeURIComponent(EDITING_ORDER)}`, { method: 'PUT', body: data })
    : await api('/api/orders', { method: 'POST', body: data });
  $('#orders-report').innerHTML = reportHtml(body);
  if (!body.errors?.length) { toast(`${EDITING_ORDER ? 'Đã cập nhật đơn' : 'Đã thêm đơn'} ${$('#of-id').value}`, 'ok'); await loadOrders(); resetOrderForm(); }
};
function editOrder(id) {
  const o = ORDERS.find(x => x.order_id === id);
  if (!o) return;
  resetOrderForm();
  EDITING_ORDER = id;
  const f = $('#order-form').elements;
  Object.entries({ order_id: o.order_id, address: o.address, customer_name: o.customer_name, phone: o.phone, latitude: o.latitude, longitude: o.longitude,
    weight_kg: o.weight_kg, volume_m3: o.volume_m3, delivery_window_start: t2(o.tw_start), delivery_window_end: t2(o.tw_end),
    service_time_min: o.service_time_min, priority: o.priority ? 1 : 0, note: o.note }).forEach(([k, v]) => { f[k].value = v ?? ''; });
  $('#of-id').readOnly = true;
  $('#order-add-title').textContent = 'Sửa đơn hàng';
  $('#of-submit').textContent = 'Cập nhật đơn';
  $('#order-add').open = true;
  ensureOrderMap();
  setTimeout(() => { orderMap?.invalidateSize(); $('#of-lat').dispatchEvent(new Event('change')); }, 60);
  $('#order-add').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ---- Order form: address search, map pin, auto-filled fields (all editable) ----
let orderMap, orderPin, addrTimer, addrItems = [], addrIdx = -1, addrSeq = 0;
function nextOrderId() {
  const ids = ORDERS.map(o => o.order_id), counts = {};
  ids.forEach(id => { const m = id.match(/^([A-Za-z]+)-?(\d+)$/); if (m) counts[m[1]] = (counts[m[1]] || 0) + 1; });
  const prefix = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'DH';
  const nums = ids.map(id => id.match(new RegExp(`^${prefix}-?(\\d+)$`))).filter(Boolean);
  const width = nums.length ? Math.max(...nums.map(m => m[1].length)) : 3;
  let n = nums.length ? Math.max(...nums.map(m => Number(m[1]))) + 1 : 1;
  while (ids.includes(`${prefix}${String(n).padStart(width, '0')}`)) n++;
  return `${prefix}${String(n).padStart(width, '0')}`;
}
function markAuto(el) { el.classList.add('autofilled'); el.addEventListener('input', () => el.classList.remove('autofilled'), { once: true }); }
function fillIfEmpty(sel, value) { const el = $(sel); if (!el.value && value != null && value !== '') { el.value = value; markAuto(el); } }
function applyOrderDefaults() {
  const d = CFG.order_defaults || {};
  fillIfEmpty('#of-id', nextOrderId());
  fillIfEmpty('#of-ws', d.window_start);
  fillIfEmpty('#of-we', d.window_end);
  fillIfEmpty('#of-svc', d.service_time_min);
}
function setOrderPoint(lat, lng, { pan = true } = {}) {
  $('#of-lat').value = Number(lat).toFixed(6); $('#of-lng').value = Number(lng).toFixed(6);
  markAuto($('#of-lat')); markAuto($('#of-lng'));
  if (!orderMap) return;
  orderPin.setLatLng([lat, lng]).setOpacity(1);
  if (pan) orderMap.setView([lat, lng], Math.max(orderMap.getZoom(), 16));
}
function ensureOrderMap() {
  if (orderMap || !$('#order-map')) return;
  const dep = [Number($('#depot-lat').value) || 10.78, Number($('#depot-lng').value) || 106.70];
  orderMap = L.map('order-map').setView(dep, 13);
  baseTiles(orderMap);
  L.marker(dep, { icon: depotIcon() }).addTo(orderMap);
  orderPin = L.marker(dep, { draggable: true, opacity: 0, zIndexOffset: 1000, icon: L.divIcon({ className: '', iconSize: null, html: '<div class="veh-marker" style="--c:#dc2626">📍 Giao</div>' }) }).addTo(orderMap);
  const pick = async ll => {
    setOrderPoint(ll.lat, ll.lng, { pan: false });
    try {
      const { body: r } = await api(`/api/geocode/reverse?lat=${ll.lat}&lng=${ll.lng}`);
      if (r) { $('#of-address').value = r.label; markAuto($('#of-address')); $('#addr-note').textContent = 'Địa chỉ cập nhật theo vị trí ghim — sửa lại số nhà nếu cần.'; }
    } catch { $('#addr-note').textContent = 'Không tra được địa chỉ cho điểm này — nhập địa chỉ thủ công.'; }
    applyOrderDefaults();
  };
  orderMap.on('click', e => pick(e.latlng));
  orderPin.on('dragend', () => pick(orderPin.getLatLng()));
}
function closeAddrList() { $('#addr-list').hidden = true; $('#of-address').setAttribute('aria-expanded', 'false'); addrIdx = -1; }
function renderAddrList(html) { $('#addr-list').innerHTML = html; $('#addr-list').hidden = false; $('#of-address').setAttribute('aria-expanded', 'true'); }
function chooseAddr(i) {
  const a = addrItems[i]; if (!a) return;
  $('#of-address').value = a.label;
  $('#addr-note').textContent = `${a.district ? a.district + ' · ' : ''}${a.latitude}, ${a.longitude} — kiểm tra lại số nhà.`;
  closeAddrList();
  setOrderPoint(a.latitude, a.longitude);
  applyOrderDefaults();
}
$('#of-address').addEventListener('input', () => {
  clearTimeout(addrTimer);
  const q = $('#of-address').value.trim();
  if (q.length < 3) { closeAddrList(); return; }
  addrTimer = setTimeout(async () => {
    const seq = ++addrSeq;
    renderAddrList('<li class="msg">Đang tìm…</li>');
    try {
      const { body } = await api(`/api/geocode/search?q=${encodeURIComponent(q)}`);
      if (seq !== addrSeq) return;  // a newer query is in flight
      addrItems = body; addrIdx = -1;
      renderAddrList(body.length ? body.map((a, i) => `<li role="option" data-i="${i}"><span>${esc(a.name || a.label)}</span><small>${esc(a.label)}</small></li>`).join('')
        : '<li class="msg">Không tìm thấy — thử bỏ số nhà, hoặc bấm vào bản đồ để chọn vị trí.</li>');
    } catch (err) { if (seq === addrSeq) renderAddrList(`<li class="msg">${esc(err.message)}</li>`); }
  }, 350);
});
$('#of-address').addEventListener('keydown', e => {
  if ($('#addr-list').hidden || !addrItems.length) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    addrIdx = (addrIdx + (e.key === 'ArrowDown' ? 1 : -1) + addrItems.length) % addrItems.length;
    $$('#addr-list li[data-i]').forEach((li, i) => li.setAttribute('aria-selected', String(i === addrIdx)));
  } else if (e.key === 'Enter' && addrIdx >= 0) { e.preventDefault(); chooseAddr(addrIdx); }
  else if (e.key === 'Escape') closeAddrList();
});
$('#addr-list').addEventListener('mousedown', e => { const li = e.target.closest('li[data-i]'); if (li) { e.preventDefault(); chooseAddr(Number(li.dataset.i)); } });
$('#of-address').addEventListener('blur', () => setTimeout(closeAddrList, 150));
['#of-lat', '#of-lng'].forEach(s => $(s).addEventListener('change', () => {
  const pair = $(s).value.match(/(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)/);
  if (pair) { $('#of-lat').value = pair[1]; $('#of-lng').value = pair[2]; }
  const lat = Number($('#of-lat').value), lng = Number($('#of-lng').value);
  if (lat && lng && orderMap) { orderPin.setLatLng([lat, lng]).setOpacity(1); orderMap.setView([lat, lng], 16); }
}));
function resetOrderForm() {
  $('#order-form').reset();
  EDITING_ORDER = null;
  $('#of-id').readOnly = false;
  $('#order-add-title').textContent = 'Thêm đơn hàng';
  $('#of-submit').textContent = 'Lưu đơn';
  $$('#order-form .autofilled').forEach(el => el.classList.remove('autofilled'));
  $('#addr-note').textContent = '';
  if (orderPin) orderPin.setOpacity(0);
  fillIfEmpty('#of-id', nextOrderId());
}
$('#of-reset').onclick = resetOrderForm;
$('#order-add').addEventListener('toggle', () => {
  if (!$('#order-add').open) return;
  ensureOrderMap(); setTimeout(() => orderMap?.invalidateSize(), 60);
  fillIfEmpty('#of-id', nextOrderId());
});

// ---------------------------------------------------------------- Vehicles
function fuelOptions(type, selected) {
  const vt = CFG.vehicle_types[type]; if (!vt) return '';
  return [...vt.allowed.map(f => [f, '']), ...vt.simulation_allowed.map(f => [f, ' (mô phỏng)'])]
    .map(([f, s]) => `<option value="${f}" ${f === selected ? 'selected' : ''}>${esc(CFG.fuels[f].label)}${s}</option>`).join('');
}
async function loadVehicles() {
  const { body: vs } = await api('/api/vehicles');
  $('#vehicles-count').textContent = `Đội xe (${vs.length} xe · ${vs.filter(v => v.available).length} sẵn sàng)`;
  $('#vehicles-table').innerHTML = vs.length ? `<div class="tbl-wrap"><table><thead><tr><th>Xe</th><th>Tài xế</th><th>Nhiên liệu</th><th class="num">Tải trọng</th><th class="num">Thể tích</th><th class="num">VND/km</th><th class="num">Cố định</th><th class="num">Tiêu hao</th><th class="num">Giá NL</th><th>Ca</th><th>Trạng thái</th><th></th></tr></thead><tbody>${
    vs.map(v => { const fu = CFG.fuels[v.fuel_blend_code]; return `<tr><td><a href="#" class="oid" data-vehicle="${esc(v.vehicle_id)}"><span class="dot" style="background:${colorFor(v.vehicle_id)}"></span> ${esc(v.vehicle_id)}</a><br><small class="muted">${esc(CFG.vehicle_types[v.vehicle_type]?.label)}</small></td>
      <td>${v.driver ? esc(v.driver) : '<span class="badge warn">chưa gán</span>'}</td>
      <td>${esc(fu?.label)} ${fu && !fu.official ? '<span class="badge sim">mô phỏng</span>' : ''}</td><td class="num">${v.capacity_weight_kg} kg</td><td class="num">${v.capacity_volume_m3 ?? '—'} m³</td>
      <td class="num">${fmt(v.cost_per_km)}</td><td class="num">${fmt(v.fixed_cost_vnd)}</td><td class="num">${v.consumption_rate ?? '<span class="badge warn">thiếu</span>'} ${fu?.kind === 'electric' ? 'kWh' : 'L'}</td>
      <td class="num" title="${esc(v.fuel_price == null ? fu?.price_source || '' : 'Giá nhập riêng cho xe')}">${fmt(v.fuel_price ?? fu?.price_vnd)}${v.fuel_price == null ? `<br><small class="muted">mặc định${fu?.price_date ? ` · ${fu.price_date.split('-').reverse().join('/')}` : ''}</small>` : ''}</td><td>${t2(v.start_time)}–${t2(v.end_time)}</td>
      <td>${v.available ? '<span class="badge ok">sẵn sàng</span>' : '<span class="badge bad">nghỉ</span>'}</td>
      <td>${can('admin', 'fleet_manager') ? `<button class="danger sm" data-del-veh="${esc(v.vehicle_id)}">Xóa</button>` : ''}</td></tr>`; }).join('')
  }</tbody></table></div>` : empty('🚚', 'Chưa có xe nào.');
  return vs;
}
$('#vehicles-table').onclick = async e => {
  const id = e.target.dataset.delVeh;
  if (id && confirm(`Xóa xe ${id}?`)) { await api(`/api/vehicles/${encodeURIComponent(id)}`, { method: 'DELETE' }); toast(`Đã xóa ${id}`); loadVehicles(); }
};
$('#btn-vehicles-import').onclick = e => busy(e.target, async () => {
  const f = $('#vehicles-file').files[0]; if (!f) throw new Error('Chọn file CSV/XLSX trước');
  const fd = new FormData(); fd.append('file', f);
  const { body } = await api(`/api/vehicles/import?mode=${$('#vehicles-mode').value}`, { method: 'POST', body: fd });
  $('#vehicles-report').innerHTML = reportHtml(body); loadVehicles();
});
$('#vf-type').onchange = () => { $('#vf-fuel').innerHTML = fuelOptions($('#vf-type').value); };
$('#vehicle-form').onsubmit = async e => {
  e.preventDefault();
  const fd = new FormData(e.target), data = Object.fromEntries(fd);
  data.available = fd.has('available'); data.confirm_simulation_fuel = fd.has('confirm_simulation_fuel');
  const exists = (await api('/api/vehicles')).body.some(v => v.vehicle_id === data.vehicle_id);
  const { body } = exists
    ? await api(`/api/vehicles/${encodeURIComponent(data.vehicle_id)}`, { method: 'PUT', body: JSON.stringify(data) })
    : await api('/api/vehicles', { method: 'POST', body: JSON.stringify(data) });
  $('#vehicles-report').innerHTML = reportHtml(body);
  if (!body.errors?.length) { toast(exists ? 'Đã cập nhật xe' : 'Đã thêm xe', 'ok'); loadVehicles(); }
};

// ---------------------------------------------------------------- Fuel scenarios
function renderFuelEditor() {
  if (!RUN) { $('#fuel-editor').innerHTML = empty('⛽', 'Chạy tối ưu (hoặc mở một lần tối ưu trong Lịch sử) trước.'); return; }
  const used = new Set(RUN.optimized.routes.map(r => r.vehicle_id));
  $('#fuel-editor').innerHTML = `<div class="tbl-wrap"><table><thead><tr><th>Xe</th><th>Hiện tại</th><th>Nhiên liệu mới</th><th>Tiêu hao /100km</th><th>Giá</th><th>Hệ số tùy chỉnh</th><th>Xác nhận mô phỏng</th></tr></thead><tbody>${
    RUN.input.vehicles.filter(v => v.available).map(v => `<tr data-vid="${esc(v.vehicle_id)}"><td><span class="dot" style="background:${colorFor(v.vehicle_id)}"></span> <b>${esc(v.vehicle_id)}</b>${used.has(v.vehicle_id) ? '' : ' <span class="badge">không dùng</span>'}</td>
      <td>${esc(v.fuel_blend_code)} · ${v.consumption_rate ?? '?'}</td>
      <td><select data-k="fuel_blend_code">${fuelOptions(v.vehicle_type, v.fuel_blend_code)}</select></td>
      <td><input data-k="consumption_rate" style="width:90px" placeholder="${v.consumption_rate ?? ''}"></td>
      <td><input data-k="fuel_price" style="width:100px" placeholder="${v.fuel_price ?? CFG.fuels[v.fuel_blend_code]?.price_vnd ?? ''}"></td>
      <td><input data-k="emission_factor_value" style="width:90px"></td>
      <td><input type="checkbox" data-k="confirm_simulation_fuel"></td></tr>`).join('')
  }</tbody></table></div>`;
}
$('#btn-scenario').onclick = e => busy(e.target, async () => {
  if (!RUN) throw new Error('Chạy tối ưu trước');
  const overrides = {};
  $$('#fuel-editor tr[data-vid]').forEach(tr => {
    const v = RUN.input.vehicles.find(x => x.vehicle_id === tr.dataset.vid), o = {};
    tr.querySelectorAll('[data-k]').forEach(el => {
      const k = el.dataset.k;
      if (el.type === 'checkbox') { if (el.checked) o[k] = true; }
      else if (el.value !== '' && !(k === 'fuel_blend_code' && el.value === v.fuel_blend_code)) o[k] = k === 'fuel_blend_code' ? el.value : Number(el.value);
    });
    if (Object.keys(o).some(k => k !== 'confirm_simulation_fuel')) overrides[v.vehicle_id] = o;
  });
  if (!Object.keys(overrides).length) throw new Error('Chưa thay đổi xe nào');
  e.target.innerHTML = '⏳ Đang chạy…';
  const { status, body } = await api(`/api/optimization/${RUN.id}/fuel-scenario`, { method: 'POST', body: JSON.stringify({ overrides, mode: $('#sc-mode').value, name: $('#sc-name').value }) });
  if (status === 422) { $('#scenario-result').innerHTML = alertBox('err', body.errors.map(x => `<b>${esc(x.vehicle_id)}</b>: ${esc(x.error)}`).join('<br>')); return; }
  RUN.scenarios.push(body);
  const t = body.result.totals;
  $('#scenario-result').innerHTML = `<div class="card"><div class="card-h"><h3>${esc(body.name)}</h3><span class="right badge info">${body.mode === 'reoptimize' ? 'Tối ưu lại tuyến' : 'Cùng tuyến'}</span></div>
    ${alertBox('info', esc(body.basis_note))}
    <div class="tbl-wrap" style="margin-top:10px"><table><thead><tr><th>Chỉ số</th><th class="num">Phương án hiện tại</th><th class="num">Kịch bản</th><th class="num">Thay đổi</th></tr></thead><tbody>${
      body.comparison.rows.map(r => `<tr><td>${METRIC_LABEL[r.metric] || r.metric}</td><td class="num">${fmt(r.reference, 3)}</td><td class="num">${fmt(r.candidate, 3)}</td><td class="num">${r.change_pct == null ? '—' : deltaHtml(r.change_pct)}</td></tr>`).join('')
    }<tr><td>CO₂ hóa thạch / sinh học (kg)</td><td colspan="3">${fmt(t.co2_fossil_kg, 3)} / ${fmt(t.co2_biogenic_kg, 3)} <small class="muted">(CO₂ sinh học từ ethanol báo cáo riêng)</small></td></tr></tbody></table></div>
    ${t.warnings.map(w => alertBox('warn', `⚠ ${esc(w)}`)).join('')}</div>`;
  toast('Đã chạy kịch bản', 'ok');
});

// ---------------------------------------------------------------- History
async function loadHistory() {
  const { body: runs } = await api('/api/optimization');
  $('#history').innerHTML = runs.length ? `<div class="tbl-wrap"><table><thead><tr><th>Thời điểm</th><th>Người chạy</th><th class="num">Đơn</th><th class="num">Xe</th><th class="num">km</th><th class="num">Chi phí</th><th class="num">CO₂ (kg)</th><th></th></tr></thead><tbody>${
    runs.map(r => `<tr><td>${new Date(r.created_at).toLocaleString('vi-VN')} ${r.published ? '<span class="badge ok">đang phát hành</span>' : ''}</td><td>${esc(r.created_by || '')}</td>
      <td class="num">${r.totals.orders_assigned}/${r.totals.orders_total}</td><td class="num">${r.totals.vehicles_used}</td>
      <td class="num">${fmt(r.totals.distance_km, 1)}</td><td class="num">${fmt(r.totals.total_cost_vnd)}</td><td class="num">${fmt(r.totals.co2_direct_kg, 2)}</td>
      <td style="white-space:nowrap"><button class="sm" data-open="${r.id}">Mở</button> <button class="secondary sm" data-dl="/api/reports/${r.id}?format=xlsx">⬇ XLSX</button> <button class="secondary sm" data-dl="/api/reports/${r.id}?format=csv">⬇ CSV</button></td></tr>`).join('')
  }</tbody></table></div>` : empty('🗂', 'Chưa có lần tối ưu nào.');
}
$('#history').onclick = async e => {
  if (e.target.dataset.dl) return busy(e.target, () => Auth.download(e.target.dataset.dl));
  if (!e.target.dataset.open) return;
  renderRun((await api(`/api/optimization/${e.target.dataset.open}`)).body);
  go('plan');
};

// ---------------------------------------------------------------- Admin
async function loadAdmin() {
  const [{ body: users }, { body: roles }, { body: vehicles }, { body: datasets }] = await Promise.all([api('/api/admin/users'), api('/api/admin/roles'), api('/api/vehicles'), api('/api/sample/datasets')]);
  const roleOpts = sel => Object.entries(roles).map(([k, l]) => `<option value="${k}" ${k === sel ? 'selected' : ''}>${esc(l)}</option>`).join('');
  const vehOpts = sel => '<option value="">—</option>' + vehicles.map(v => `<option value="${esc(v.vehicle_id)}" ${v.vehicle_id === sel ? 'selected' : ''}>${esc(v.vehicle_id)}</option>`).join('');
  $('#uf-role').innerHTML = roleOpts('dispatcher');
  $('#uf-vehicle').innerHTML = vehOpts('');
  $('#dataset').innerHTML = Object.entries(datasets).map(([k, l]) => `<option value="${k}" ${k === 'hcm' ? 'selected' : ''}>${esc(l)}</option>`).join('');
  $('#users').innerHTML = `<div class="tbl-wrap"><table><thead><tr><th>Tài khoản</th><th>Họ tên</th><th>Vai trò</th><th>Xe (tài xế)</th><th>Trạng thái</th><th>Đăng nhập gần nhất</th><th></th></tr></thead><tbody>${
    users.map(u => `<tr data-user="${esc(u.username)}"><td><div style="display:flex;gap:8px;align-items:center"><div class="avatar" style="width:28px;height:28px;font-size:12px;background:${colorFor(u.username)}">${esc(initial(u.full_name || u.username))}</div><b>${esc(u.username)}</b></div>${u.must_change_password ? '<span class="badge warn">chờ đổi MK</span>' : ''}</td>
      <td><input data-f="full_name" value="${esc(u.full_name)}"></td>
      <td><select data-f="role">${roleOpts(u.role)}</select></td>
      <td><select data-f="vehicle_id">${vehOpts(u.vehicle_id)}</select></td>
      <td><select data-f="active"><option value="true" ${u.active ? 'selected' : ''}>Hoạt động</option><option value="false" ${u.active ? '' : 'selected'}>Đã khóa</option></select></td>
      <td><small>${u.last_login_at ? new Date(u.last_login_at).toLocaleString('vi-VN') : '—'}</small></td>
      <td style="white-space:nowrap"><button class="sm" data-save>Lưu</button> <button class="secondary sm" data-reset>Đặt lại MK</button></td></tr>`).join('')
  }</tbody></table></div>`;
  renderConfigEditor(); loadConfigHistory(); loadAudit();
}
$('#admin-seg').onclick = e => {
  const b = e.target.closest('[data-sub]'); if (!b) return;
  $$('#admin-seg button').forEach(x => x.classList.toggle('active', x === b));
  $$('#page-admin .sub').forEach(s => s.classList.toggle('active', s.id === `sub-${b.dataset.sub}`));
};
$('#users').onclick = async e => {
  const tr = e.target.closest('tr[data-user]'); if (!tr) return;
  const username = tr.dataset.user; let data;
  if (e.target.hasAttribute('data-save')) {
    data = {}; tr.querySelectorAll('[data-f]').forEach(el => { data[el.dataset.f] = el.dataset.f === 'active' ? el.value === 'true' : el.value; });
  } else if (e.target.hasAttribute('data-reset')) {
    const pw = prompt(`Mật khẩu tạm mới cho ${username} (≥ 8 ký tự). Người dùng sẽ phải đổi khi đăng nhập:`); if (!pw) return;
    data = { password: pw };
  } else return;
  busy(e.target, async () => { await api(`/api/admin/users/${encodeURIComponent(username)}`, { method: 'PUT', body: JSON.stringify(data) }); toast(`Đã cập nhật ${username}`, 'ok'); loadAdmin(); });
};
$('#user-form').onsubmit = async e => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  try {
    await api('/api/admin/users', { method: 'POST', body: JSON.stringify(data) });
    $('#user-msg').innerHTML = alertBox('ok', `✓ Đã tạo <b>${esc(data.username)}</b>. Gửi mật khẩu tạm qua kênh riêng.`);
    e.target.reset(); loadAdmin();
  } catch (err) { $('#user-msg').innerHTML = alertBox('err', esc(err.message)); }
};
$('#btn-sample').onclick = e => busy(e.target, async () => {
  if (!confirm('Thay toàn bộ kho, đơn hàng và đội xe hiện có bằng dữ liệu minh họa?')) return;
  const { body } = await api(`/api/sample/load?dataset=${$('#dataset').value}`, { method: 'POST' });
  await refreshDepot();
  toast(`Đã nạp ${body.orders.total} đơn, ${body.vehicles.total} xe`, 'ok');
});

function renderConfigEditor() {
  const input = (path, val, type = 'number', w = 110) => `<input data-path="${path}" data-orig="${esc(val)}" type="${type}" step="any" value="${esc(val ?? '')}" style="width:${w}px">`;
  const boolSel = (path, val) => `<select data-path="${path}" data-orig="${val}" data-bool><option value="true" ${val ? 'selected' : ''}>có</option><option value="false" ${val ? '' : 'selected'}>không</option></select>`;
  const dw = CFG.default_weights || {}, dc = CFG.delivery_check || {}, tr = CFG.tracking || {};
  $('#config-editor').innerHTML = `
    <div class="card-h"><h3>Hệ số phát thải nền</h3><span class="right hint">Phiên bản <code>${esc(CFG.version)}</code>${CFG.updated_by ? ` · sửa bởi ${esc(CFG.updated_by)}` : ''}</span></div>
    <div class="tbl-wrap"><table><thead><tr><th>Khóa</th><th>Giá trị</th><th>Đơn vị</th><th>Nguồn</th><th>Năm</th><th>Khu vực</th></tr></thead><tbody>${
      Object.entries(CFG.base_factors).map(([k, f]) => `<tr><td><b>${k}</b></td><td>${input(`base_factors.${k}.value`, f.value)}</td><td>${esc(f.unit)}</td>
        <td>${input(`base_factors.${k}.source`, f.source, 'text', 340)}</td><td>${input(`base_factors.${k}.year`, f.year, 'number', 80)}</td><td>${input(`base_factors.${k}.geography`, f.geography, 'text', 130)}</td></tr>`).join('')}</tbody></table></div>
    <h3 style="margin:18px 0 10px">Nhiên liệu: giá mặc định &amp; trạng thái</h3>
    <div class="tbl-wrap"><table><thead><tr><th>Mã</th><th>Tên</th><th>Giá mặc định</th><th>Nguồn giá</th><th>Ngày áp dụng</th><th>Tỷ lệ ethanol (0–1)</th><th>Trạng thái</th><th>Chính thức</th></tr></thead><tbody>${
      Object.entries(CFG.fuels).map(([k, f]) => `<tr><td><b>${k}</b></td><td>${esc(f.label)}</td><td>${input(`fuels.${k}.price_vnd`, f.price_vnd)} <small class="muted">${esc(f.price_unit)}</small></td>
        <td>${input(`fuels.${k}.price_source`, f.price_source, 'text', 240)}</td><td>${input(`fuels.${k}.price_date`, f.price_date, 'text', 110)}</td>
        <td>${f.ethanol_share_volume != null ? input(`fuels.${k}.ethanol_share_volume`, f.ethanol_share_volume, 'number', 80) : '—'}</td>
        <td><select data-path="fuels.${k}.status" data-orig="${f.status}">${['supported', 'simulation', 'unverified'].map(s => `<option ${s === f.status ? 'selected' : ''}>${s}</option>`).join('')}</select></td>
        <td>${boolSel(`fuels.${k}.official`, f.official)}</td></tr>`).join('')}</tbody></table></div>
    <div class="grid cols-2" style="margin-top:18px">
      <div><h3 style="margin-bottom:10px">Tốc độ trung bình theo loại xe</h3><div class="tbl-wrap"><table><tbody>${
        Object.entries(CFG.vehicle_types).map(([k, v]) => `<tr><td>${esc(v.label)}</td><td>${input(`vehicle_types.${k}.speed_kmh`, v.speed_kmh, 'number', 90)} km/h</td></tr>`).join('')}</tbody></table></div></div>
      <div><h3 style="margin-bottom:10px">Tối ưu, định tuyến &amp; theo dõi</h3><div class="tbl-wrap"><table><tbody>
        <tr><td>Giá CO₂ quy đổi (VND/kg)</td><td>${input('default_weights.co2_vnd_per_kg', dw.co2_vnd_per_kg ?? 0)}</td></tr>
        <tr><td>Chi phí thời gian (VND/phút)</td><td>${input('default_weights.time_vnd_per_min', dw.time_vnd_per_min ?? 0)}</td></tr>
        <tr><td>Thời gian giải mặc định (giây)</td><td>${input('default_weights.time_limit_s', dw.time_limit_s ?? 5)}</td></tr>
        <tr><td>Hệ số đường vòng (khi không có OSRM)</td><td>${input('routing.detour_factor', CFG.routing.detour_factor)}</td></tr>
        <tr><td>Ngưỡng xác nhận vị trí giao (m)</td><td>${input('delivery_check.max_distance_m', dc.max_distance_m ?? 300)}</td></tr>
        <tr><td>Chu kỳ gửi vị trí tài xế (giây)</td><td>${input('tracking.ping_interval_s', tr.ping_interval_s ?? 20)}</td></tr>
        <tr><td>Tốc độ giờ cao điểm (0–1 × tốc độ thường)</td><td>${input('traffic.peak_speed_factor', CFG.traffic?.peak_speed_factor ?? 0.6)}</td></tr>
        <tr><td>Đơn mới: giao từ (HH:MM)</td><td>${input('order_defaults.window_start', CFG.order_defaults?.window_start ?? '08:00', 'text', 90)}</td></tr>
        <tr><td>Đơn mới: giao đến (HH:MM)</td><td>${input('order_defaults.window_end', CFG.order_defaults?.window_end ?? '17:00', 'text', 90)}</td></tr>
        <tr><td>Đơn mới: thời gian dừng (phút)</td><td>${input('order_defaults.service_time_min', CFG.order_defaults?.service_time_min ?? 5)}</td></tr>
        <tr><td>Coi là mất tín hiệu sau (giây)</td><td>${input('tracking.stale_after_s', tr.stale_after_s ?? 300)}</td></tr>
        <tr><td>Gắn nhãn “Dữ liệu minh họa”</td><td>${boolSel('illustrative', CFG.illustrative)}</td></tr>
      </tbody></table></div></div>
    </div>`;
}
$('#btn-cfg-save').onclick = e => busy(e.target, async () => {
  const changes = {};
  $$('#config-editor [data-path]').forEach(el => {
    if (String(el.value) === String(el.dataset.orig)) return;
    changes[el.dataset.path] = el.hasAttribute('data-bool') ? el.value === 'true' : el.type === 'number' ? Number(el.value) : el.value;
  });
  if (!Object.keys(changes).length) { $('#cfg-msg').innerHTML = alertBox('warn', 'Chưa có thay đổi nào.'); return; }
  try {
    const { body } = await api('/api/admin/config', { method: 'PUT', body: JSON.stringify({ changes, reason: $('#cfg-reason').value }) });
    CFG = body.config; $('#cfg-reason').value = '';
    $('#cfg-msg').innerHTML = alertBox('ok', `✓ Đã lưu phiên bản <code>${esc(body.change.version)}</code> (${body.change.changes.length} thay đổi).`);
    renderConfigEditor(); loadConfigHistory(); applyDefaults(); updateBanner();
  } catch (err) { $('#cfg-msg').innerHTML = alertBox('err', esc(err.message)); }
});
async function loadConfigHistory() {
  const { body: h } = await api('/api/admin/config/history');
  $('#config-history').innerHTML = h.length ? `<div class="tbl-wrap"><table><thead><tr><th>Phiên bản</th><th>Thời điểm</th><th>Người sửa</th><th>Lý do</th><th>Thay đổi</th></tr></thead><tbody>${
    h.map(x => `<tr><td><code>${esc(x.version)}</code></td><td>${new Date(x.at).toLocaleString('vi-VN')}</td><td>${esc(x.user)}</td><td>${esc(x.reason)}</td>
      <td><small>${x.changes.map(c => `${esc(c.path)}: ${esc(c.old)} → <b>${esc(c.new)}</b>`).join('<br>')}</small></td></tr>`).join('')
  }</tbody></table></div>` : empty('📄', 'Chưa có thay đổi — đang dùng cấu hình mặc định.');
}
const ACTION_LABEL = { login: 'Đăng nhập', login_failed: 'Đăng nhập sai', run_optimization: 'Chạy tối ưu', publish_plan: 'Phát hành tuyến', delivery_outcome: 'Báo kết quả giao',
  update_config: 'Sửa cấu hình', create_user: 'Tạo tài khoản', update_user: 'Sửa tài khoản', load_sample: 'Nạp dữ liệu mẫu', location_sharing_on: 'Bắt đầu chia sẻ vị trí',
  location_sharing_off: 'Dừng chia sẻ vị trí', fuel_scenario: 'Chạy kịch bản', change_password: 'Đổi mật khẩu' };
async function loadAudit() {
  const { body: a } = await api('/api/admin/audit?limit=300');
  $('#audit').innerHTML = `<div class="tbl-wrap"><table><thead><tr><th>Thời điểm</th><th>Người dùng</th><th>Hành động</th><th>Chi tiết</th></tr></thead><tbody>${
    a.map(x => `<tr><td style="white-space:nowrap">${new Date(x.at).toLocaleString('vi-VN')}</td><td>${esc(x.user || 'hệ thống')}</td><td>${esc(ACTION_LABEL[x.action] || x.action)}</td><td><small class="muted">${esc(x.detail ? JSON.stringify(x.detail) : '')}</small></td></tr>`).join('')
  }</tbody></table></div>`;
}

// ---------------------------------------------------------------- Method
function renderMethod() {
  const b = CFG.base_factors;
  $('#method').innerHTML = `<p class="hint">Phiên bản cấu hình: <code>${esc(CFG.version)}</code></p>
    <h3>Phạm vi phát thải</h3><p>${esc(CFG.scope_note)}</p>
    <h3>Công thức</h3><ul>
      <li>Nhiên liệu (L) = km × tiêu hao (L/100km) / 100 · CO₂ (kg) = L × EF · Chi phí = L × giá</li>
      <li>Điện (kWh) = km × tiêu hao (kWh/100km) / 100 · CO₂ gián tiếp = kWh × EF lưới · CO₂ ống xả = 0</li>
      <li>Xăng pha ethanol: EF ≈ (1 − x)·EF<sub>xăng</sub> + x·EF<sub>ethanol</sub>, x = tỷ lệ thể tích. Phần ethanol là CO₂ sinh học, báo cáo riêng.</li>
      <li>Chi phí = km × chi phí vận hành/km + chi phí cố định mỗi xe dùng + chi phí năng lượng.</li>
      <li>Hàm mục tiêu OR-Tools = chi phí + giá CO₂ quy đổi × kg CO₂ trực tiếp (+ chi phí thời gian nếu cấu hình).</li></ul>
    <h3>Hệ số nền</h3><div class="tbl-wrap"><table><thead><tr><th>Khóa</th><th>Giá trị</th><th>Nguồn</th><th>Năm</th></tr></thead><tbody>${
      Object.entries(b).map(([k, f]) => `<tr><td>${k}</td><td>${f.value} ${esc(f.unit)}</td><td>${esc(f.source)}</td><td>${f.year}</td></tr>`).join('')}</tbody></table></div>
    <h3>Giá nhiên liệu</h3><div class="tbl-wrap"><table><thead><tr><th>Mã</th><th>Tên</th><th class="num">Giá</th><th>Nguồn giá</th><th>Ngày áp dụng</th></tr></thead><tbody>${
      Object.entries(CFG.fuels).map(([k, f]) => `<tr><td>${k}</td><td>${esc(f.label)}</td><td class="num">${f.price_vnd == null ? '<span class="badge warn">chưa có giá</span>' : `${fmt(f.price_vnd)} ${esc(f.price_unit)}`}</td><td><small>${esc(f.price_source || '')}</small></td><td>${esc(f.price_date || '—')}</td></tr>`).join('')}</tbody></table></div>
    <h3>Định tuyến &amp; baseline</h3><p>Khoảng cách ước tính = đường chim bay × ${CFG.routing.detour_factor} (ước tính; IT có thể nối dịch vụ bản đồ đường thực OSRM qua biến môi trường <code>OSRM_URL</code>). Baseline: lấy đơn theo thứ tự gốc, xếp vào xe đầu tiên còn chỗ (first-fit), không sắp xếp lại.</p>
    <h3>Theo dõi vị trí</h3><p>Tài xế chủ động bấm <b>Bắt đầu ca</b> mới chia sẻ vị trí; điện thoại gửi mỗi ${CFG.tracking?.ping_interval_s ?? 20} giây khi trang tài xế đang mở. Trình duyệt không cho theo dõi khi tắt màn hình/đóng trang — cần app di động nếu muốn theo dõi nền.</p>
    <h3>AI / ML</h3><p>Chưa có mô hình huấn luyện trên dữ liệu thật. Dữ liệu giao hàng thực tế (giờ đến, đúng/trễ, lý do thất bại, vệt GPS) đang được thu thập để làm nhãn cho giai đoạn ML.</p>`;
}

// ---------------------------------------------------------------- Boot
function applyDefaults() {
  const dw = CFG.default_weights || {};
  $('#w-co2').value = dw.co2_vnd_per_kg ?? 0;
  $('#time-limit').value = dw.time_limit_s ?? 5;
}
function updateBanner() {
  // Global banner removed at the owner's request; scope and illustrative labels remain on results and the Method page.
  $('#banner').hidden = true;
}
async function refreshDepot() {
  const { body: d } = await api('/api/depot');
  if (d) { $('#depot-name').value = d.name; $('#depot-lat').value = d.latitude; $('#depot-lng').value = d.longitude; }
  return d;
}
$('#btn-logout').onclick = () => Auth.logout();
$('#btn-pw').onclick = () => Auth.changePassword();

(async () => {
  ME = await Auth.ensureUser();
  if (ME.role === 'driver') { location.replace('/driver.html'); return; }
  $('#who-name').textContent = ME.full_name;
  $('#who-role').textContent = ME.role_label;
  $('#avatar').textContent = initial(ME.full_name || ME.username);
  CFG = (await api('/api/config')).body;
  applyRoles(); buildMenu(); applyDefaults(); updateBanner();
  $('#vf-type').innerHTML = Object.entries(CFG.vehicle_types).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join('');
  $('#vf-fuel').innerHTML = fuelOptions($('#vf-type').value);
  await refreshDepot();
  const { body: runs } = await api('/api/optimization');
  const home = { fleet_manager: 'vehicles' }[ME.role] || 'overview';
  go(recall('gr_page') || home);
  if (runs.length) {
    const pub = runs.find(r => r.published) || runs[0];
    renderRun((await api(`/api/optimization/${pub.id}`)).body);
  }
})();
