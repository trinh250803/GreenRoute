'use strict';
/* Analytics charts, order/vehicle detail drawer and the AI assistant panel.
   Uses helpers defined in app.js ($, esc, fmt, api, toast, colorFor, can, STATUS_LABEL). */

// Validated reference palette (dataviz skill): categorical slots in fixed order, chart ink.
const VIZ = {
  s1: '#2a78d6', s2: '#eb6834', s3: '#1baf7a', s4: '#eda100', s8: '#e34948',
  ink: '#0b0b0b', ink2: '#52514e', muted: '#898781', grid: '#e1e0d9', axis: '#c3c2b7', surface: '#ffffff',
};
const T = s => (typeof I18N !== 'undefined' ? I18N.t(s) : s);
const charts = {};

// ---------------------------------------------------------------- Charts
function initChartDefaults() {
  if (!window.Chart || initChartDefaults.done) return;
  initChartDefaults.done = true;
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = VIZ.ink2;
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = '#142019';
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.maintainAspectRatio = false;
}
const nf = (v, d = 0) => Number(v ?? 0).toLocaleString(typeof I18N !== 'undefined' && I18N.get() === 'en' ? 'en-US' : 'vi-VN', { maximumFractionDigits: d });
function axes({ horizontal = false, stacked = false, unit = '', max, count = false } = {}) {
  // Counts (orders, stops) get integer ticks only.
  const value = { stacked, beginAtZero: true, max, grid: { color: VIZ.grid, drawTicks: false }, border: { display: false },
    ticks: { color: VIZ.muted, padding: 6, precision: count ? 0 : undefined, callback: v => nf(v) + unit } };
  const cat = { stacked, grid: { display: false }, border: { color: VIZ.axis }, ticks: { color: VIZ.ink2, autoSkip: false } };
  return horizontal ? { x: value, y: cat } : { x: cat, y: value };
}
// Mark spec: thin bars, 4px rounded data end, 2px surface gap between fills.
const barStyle = color => ({ backgroundColor: color, borderColor: VIZ.surface, borderWidth: 2, borderSkipped: 'start', borderRadius: 4, maxBarThickness: 18 });
function draw(id, config) {
  initChartDefaults();
  charts[id]?.destroy();
  const el = document.getElementById(id);
  if (!el || !window.Chart) return;
  charts[id] = new Chart(el, config);
}
function legend(show) { return { display: show, position: 'top', align: 'start' }; }
function tip(fmtLabel) { return { callbacks: { label: c => `${c.dataset.label ? c.dataset.label + ': ' : ''}${fmtLabel(c.parsed[c.chart.options.indexAxis === 'y' ? 'x' : 'y'])}` } }; }

function chartCard(id, title, height = 260, note = '') {
  return `<div class="card"><div class="card-h"><h3>${title}</h3>${note ? `<span class="right hint">${note}</span>` : ''}</div><div style="position:relative;height:${height}px"><canvas id="${id}" role="img" aria-label="${title}"></canvas></div></div>`;
}
function statTile(label, value, sub = '', accent = '--brand') {
  return `<div class="kpi" style="--accent:var(${accent})"><div class="l">${label}</div><div class="v">${value}</div><div class="d muted">${sub}</div></div>`;
}

async function loadAnalytics() {
  const box = $('#ov-analytics');
  if (!box) return;
  const { body: a } = await api('/api/analytics');
  if (!a) { box.innerHTML = `<div class="card">${empty('📊', T('Chưa có dữ liệu phân tích — hãy chạy tối ưu.'))}</div>`; return; }
  const e = a.efficiency, d = a.deliveries, tr = a.traffic, lc = d.location_check || {};
  const fuelLabel = f => CFG.fuels[f]?.label || f;
  const vh = Math.max(220, a.by_vehicle.length * 30 + 60);
  box.innerHTML = `
    <div class="card-h" style="margin:8px 0 0"><h3 style="font-size:17px">📊 Phân tích</h3><span class="right hint">${a.run.published ? 'Phương án đang phát hành' : 'Phương án mới nhất'} · ${new Date(a.run.created_at).toLocaleString('vi-VN')}</span></div>
    <div class="kpis">
      ${statTile('🛣 km / đơn', nf(e.km_per_order, 2), 'Hiệu quả', '--violet')}
      ${statTile('📍 Điểm / xe', nf(e.stops_per_vehicle, 1), '', '--blue')}
      ${statTile('⚖ Tải trung bình', `${nf(e.avg_utilization_pct, 1)}%`, '', '--brand')}
      ${statTile('🚚 Xe dùng / xe sẵn sàng', `${nf(e.fleet_used_pct, 0)}%`, '', '--amber')}
      ${statTile('⚡ Tỷ lệ km xe điện', `${nf(e.ev_share_km_pct, 1)}%`, '', '--brand')}
      ${statTile('📦 Khối lượng TB / đơn', `${nf(e.avg_parcel_kg, 1)} kg`, '', '--blue')}
    </div>
    <div class="card" style="border-left:4px solid var(--amber)">
      <div class="card-h"><h3>🚦 Giờ cao điểm (ước tính)</h3><span class="right hint">${esc(CFG.traffic?.note || '')}</span></div>
      <div class="kpis">
        ${statTile('chặng đi giờ cao điểm', nf(tr.peak_legs), (CFG.traffic?.peak_windows || []).map(w => w.join('–')).join(' · '), '--amber')}
        ${statTile('phút trễ thêm (ước tính)', `+${nf(tr.peak_delay_min)}′`, '', '--amber')}
        ${statTile('đơn có nguy cơ trễ khung giờ', nf(tr.late_risk), '', '--red')}
      </div>
    </div>
    <div class="grid cols-2">
      ${chartCard('ch-cost', 'Chi phí theo xe', vh)}
      ${chartCard('ch-compare', 'Thay đổi so với baseline (%)', vh, T('Xanh = tốt hơn · Đỏ = kém hơn'))}
      ${chartCard('ch-hour', 'Lịch ghé theo giờ', 260)}
      ${chartCard('ch-co2', 'Phát thải theo nhiên liệu', 260)}
      ${chartCard('ch-district', 'Đơn theo quận', Math.max(240, a.by_district.length * 26 + 40))}
      ${chartCard('ch-util', 'Mức sử dụng tải trọng theo xe', vh)}
      ${chartCard('ch-window', 'Đơn theo khung giờ giao', 240)}
      <div class="card"><div class="card-h"><h3>Kết quả giao hàng</h3></div>
        <div class="kpis" style="grid-template-columns:repeat(auto-fit,minmax(120px,1fr))">
          ${statTile('Đã xử lý', nf(d.done), `${nf(d.delivered)} ${T('Đã giao').toLowerCase()} · ${nf(d.failed)} ${T('Thất bại').toLowerCase()}`, '--blue')}
          ${statTile('Đúng giờ', d.on_time_pct == null ? '—' : `${nf(d.on_time_pct, 1)}%`, '', '--brand')}
          ${statTile('Đúng vị trí', nf(lc.ok || 0), `${T('Xa điểm giao')}: ${nf(lc.far || 0)} · ${T('Không có định vị')}: ${nf(lc.missing || 0)}`, '--violet')}
        </div>
        <h3 style="margin:14px 0 8px">Lý do giao thất bại</h3>
        ${d.fail_reasons.length ? `<div style="position:relative;height:${d.fail_reasons.length * 30 + 40}px"><canvas id="ch-fail"></canvas></div>` : `<p class="hint">${T('Chưa có đơn thất bại.')}</p>`}
      </div>
    </div>`;

  const vids = a.by_vehicle.map(v => v.vehicle_id);
  draw('ch-cost', { type: 'bar', data: { labels: vids, datasets: [
      { label: T('Chi phí vận hành'), data: a.by_vehicle.map(v => v.operating_cost_vnd), ...barStyle(VIZ.s1) },
      { label: T('Chi phí năng lượng'), data: a.by_vehicle.map(v => v.energy_cost_vnd ?? 0), ...barStyle(VIZ.s2) }] },
    options: { indexAxis: 'y', scales: axes({ horizontal: true, stacked: true }), plugins: { legend: legend(true), tooltip: tip(v => `${nf(v)} ₫`) } } });

  const rows = a.comparison.rows.filter(r => r.change_pct != null && !['co2_grid_indirect_kg'].includes(r.metric));
  draw('ch-compare', { type: 'bar', data: { labels: rows.map(r => T(METRIC_LABEL[r.metric] || r.metric)), datasets: [{
      label: '', data: rows.map(r => r.change_pct), ...barStyle(VIZ.s1),
      // Diverging pair: blue = improvement (lower), red = regression (higher).
      backgroundColor: rows.map(r => (r.change_pct <= 0 ? VIZ.s1 : VIZ.s8)), borderSkipped: false }] },
    options: { indexAxis: 'y', scales: { ...axes({ horizontal: true, unit: '%' }), x: { ...axes({ horizontal: true, unit: '%' }).x, beginAtZero: false } },
      plugins: { legend: legend(false), tooltip: tip(v => `${v > 0 ? '+' : ''}${nf(v, 1)}%`) } } });

  const hrs = a.arrivals_by_hour;
  draw('ch-hour', { type: 'bar', data: { labels: hrs.map(h => `${String(h.hour).padStart(2, '0')}h`), datasets: [
      { label: T('Giờ thường'), data: hrs.map(h => h.stops - h.peak), ...barStyle(VIZ.s1) },
      { label: T('Giờ cao điểm'), data: hrs.map(h => h.peak), ...barStyle(VIZ.s2) }] },
    options: { scales: axes({ stacked: true, count: true }), plugins: { legend: legend(true), tooltip: tip(v => `${nf(v)} ${T('điểm')}`) } } });

  draw('ch-co2', { type: 'bar', data: { labels: a.by_fuel.map(f => T(fuelLabel(f.fuel))), datasets: [
      { label: T('CO₂ trực tiếp'), data: a.by_fuel.map(f => f.co2_direct_kg), ...barStyle(VIZ.s1) },
      { label: T('CO₂ gián tiếp (điện lưới)'), data: a.by_fuel.map(f => f.co2_grid_indirect_kg), ...barStyle(VIZ.s2) }] },
    options: { scales: axes({ unit: ' kg' }), plugins: { legend: legend(true), tooltip: tip(v => `${nf(v, 2)} kg`) } } });

  draw('ch-district', { type: 'bar', data: { labels: a.by_district.map(x => x.district), datasets: [
      { label: T('Đơn'), data: a.by_district.map(x => x.orders), ...barStyle(VIZ.s1) }] },
    options: { indexAxis: 'y', scales: axes({ horizontal: true, count: true }), plugins: { legend: legend(false), tooltip: tip(v => `${nf(v)} ${T('đơn')}`) } } });

  draw('ch-util', { type: 'bar', data: { labels: vids, datasets: [{ label: '', data: a.by_vehicle.map(v => v.utilization_pct), ...barStyle(VIZ.s1) }] },
    options: { indexAxis: 'y', scales: axes({ horizontal: true, unit: '%', max: 100 }), plugins: { legend: legend(false), tooltip: tip(v => `${nf(v, 1)}%`) } } });

  draw('ch-window', { type: 'bar', data: { labels: a.by_window.map(w => T(w.bucket)), datasets: [{ label: '', data: a.by_window.map(w => w.orders), ...barStyle(VIZ.s1) }] },
    options: { scales: axes({ count: true }), plugins: { legend: legend(false), tooltip: tip(v => `${nf(v)} ${T('đơn')}`) } } });

  if (d.fail_reasons.length) draw('ch-fail', { type: 'bar', data: { labels: d.fail_reasons.map(r => T(r.reason)), datasets: [{ label: '', data: d.fail_reasons.map(r => r.count), ...barStyle(VIZ.s1) }] },
    options: { indexAxis: 'y', scales: axes({ horizontal: true, count: true }), plugins: { legend: legend(false), tooltip: tip(v => `${nf(v)} ${T('đơn')}`) } } });
}
window.addEventListener('langchange', () => { if (PAGE === 'overview') loadAnalytics().catch(() => {}); });

// ---------------------------------------------------------------- Detail drawer
let drawerMap = null;
function openDrawer(title, html) {
  $('#drawer-title').textContent = title;
  $('#drawer-body').innerHTML = html;
  $('#drawer').hidden = false; $('#drawer-backdrop').hidden = false;
  $('#drawer').scrollTop = 0;
}
function closeDrawer() { $('#drawer').hidden = true; $('#drawer-backdrop').hidden = true; if (drawerMap) { drawerMap.remove(); drawerMap = null; } }
const kv = rows => `<dl class="kv">${rows.filter(r => r && r[1] !== undefined && r[1] !== null && r[1] !== '').map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`;
const section = (t, body) => `<section class="dsec"><h4>${t}</h4>${body}</section>`;
const orderLink = id => `<a href="#" class="oid" data-order="${esc(id)}">${esc(id)}</a>`;
const vehLink = id => `<a href="#" class="oid" data-vehicle="${esc(id)}"><span class="dot" style="background:${colorFor(id)}"></span> ${esc(id)}</a>`;
function historyList(h) {
  return h.length ? `<ul class="timeline">${h.map(x => `<li><b>${esc(ACTION_LABEL[x.action] || x.action)}</b> · ${esc(x.user || 'hệ thống')}<br><small class="muted">${new Date(x.at).toLocaleString('vi-VN')}${x.detail?.status ? ` · ${esc(x.detail.status)}` : ''}</small></li>`).join('')}</ul>` : `<p class="hint">${T('Không có lịch sử thao tác.')}</p>`;
}
function miniMap(points) {
  setTimeout(() => {
    const el = document.getElementById('drawer-map'); if (!el || !points.length) return;
    drawerMap = L.map(el, { zoomControl: false, attributionControl: false });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(drawerMap);
    points.forEach(p => (p.line ? L.polyline(p.line, { color: p.color, weight: 3, opacity: .7 }) : L.marker(p.ll, { icon: p.icon })).addTo(drawerMap));
    const all = points.flatMap(p => (p.line ? p.line : [p.ll]));
    drawerMap.fitBounds(all, { padding: [24, 24], maxZoom: 16 });
  }, 30);
}

async function openOrder(id) {
  if (!can('admin', 'dispatcher', 'ops_manager')) return;
  const { body: d } = await api(`/api/orders/${encodeURIComponent(id)}/detail`);
  const o = d.order, a = d.assignment, dv = d.delivery;
  const status = dv?.status || (a ? 'pending' : null);
  openDrawer(`${T('Chi tiết đơn hàng')} ${o.order_id}`, `
    <div class="dhead"><div class="big">${esc(o.customer_name || o.order_id)}</div>
      <div>${status ? `<span class="badge ${status}">${STATUS_LABEL[status]}</span>` : ''} ${o.priority ? '<span class="badge warn">ưu tiên</span>' : ''} ${d.unassigned ? '<span class="badge bad">Chưa phân công</span>' : ''}</div></div>
    <div id="drawer-map" class="map" style="height:200px;margin:12px 0"></div>
    ${section('Thông tin đơn', kv([['Mã đơn', `<code>${esc(o.order_id)}</code>`], ['Khách hàng', esc(o.customer_name)], ['Số điện thoại', o.phone ? `<a href="tel:${esc(o.phone)}">${esc(o.phone)}</a>` : ''],
      ['Địa chỉ', esc(o.address)], ['Quận', esc(o.district)], ['Tọa độ', `${o.latitude}, ${o.longitude}`], ['Khối lượng (kg)', o.weight_kg], ['Thể tích (m³)', o.volume_m3],
      ['Khung giờ', o.window || T('Cả ngày')], ['Thời gian dừng (phút)', o.service_time_min], ['Ghi chú', esc(o.note)]]))}
    ${section('Phân công', a ? kv([['Xe', vehLink(a.vehicle_id)], ['Tài xế', a.driver ? esc(a.driver.full_name) : `<span class="bad">${T('chưa gán tài xế')}</span>`],
        ['Thứ tự', `${a.sequence} / ${a.of}`], ['Đến dự kiến', a.arrival], ['Chờ', a.wait_min ? `${a.wait_min}′` : ''], ['Chặng', `${a.leg_km} km`],
        ['Giờ cao điểm', a.peak ? `<span class="badge warn">🚦 +${a.peak_delay_min}′</span>` : '—'], ['Dự kiến nếu kẹt giờ cao điểm', a.est_arrival_peak + (a.late_risk ? ` <span class="badge bad">${T('nguy cơ trễ')}</span>` : '')]])
      : d.unassigned ? alertBox('warn', `<div><code>${esc(d.unassigned.code)}</code><br>${esc(d.unassigned.message)}</div>`) : `<p class="hint">—</p>`)}
    ${section('Giao hàng', dv ? kv([['Trạng thái', `<span class="badge ${dv.status}">${STATUS_LABEL[dv.status]}</span>`], ['Thực tế', esc(dv.actual_time)], ['Dự kiến', esc(dv.planned_arrival)],
        ['Đúng giờ', dv.on_time == null ? '' : dv.on_time ? '✓' : `<span class="bad">${T('trễ')}</span>`], ['Xác nhận vị trí', locationCell(dv)], ['Lý do', esc(dv.reason_label)], ['Ghi chú', esc(dv.note)],
        ['Người ghi nhận', `${esc(dv.recorded_by)} · ${new Date(dv.recorded_at).toLocaleString('vi-VN')}`]]) : `<p class="hint">${T('Chưa có kết quả giao')}</p>`)}
    ${section('Lịch sử', historyList(d.history))}`);
  const dep = RUN?.depot;
  miniMap([...(dep ? [{ ll: [dep.latitude, dep.longitude], icon: depotIcon() }] : []),
    { ll: [o.latitude, o.longitude], icon: stopIcon(a ? a.sequence : '!', a ? colorFor(a.vehicle_id) : '#dc2626', dv?.status) },
    ...(dv?.location ? [{ ll: [dv.location.latitude, dv.location.longitude], icon: L.divIcon({ className: '', iconSize: [18, 18], iconAnchor: [9, 9], html: '<div class="me-dot"></div>' }) }] : [])]);
}

async function openVehicle(id) {
  const { body: d } = await api(`/api/vehicles/${encodeURIComponent(id)}/detail`);
  const v = d.vehicle, r = d.route, fu = CFG.fuels[v.fuel_blend_code];
  const done = r ? r.stops.filter(s => s.status && s.status !== 'pending').length : 0;
  openDrawer(`${T('Chi tiết xe')} ${v.vehicle_id}`, `
    <div class="dhead"><div class="big"><span class="dot" style="background:${colorFor(v.vehicle_id)};width:14px;height:14px"></span> ${esc(v.vehicle_id)}</div>
      <div><span class="badge">${esc(CFG.vehicle_types[v.vehicle_type]?.label)}</span> <span class="badge ${v.available ? 'ok' : 'bad'}">${v.available ? 'sẵn sàng' : 'nghỉ'}</span></div></div>
    ${r ? '<div id="drawer-map" class="map" style="height:220px;margin:12px 0"></div>' : ''}
    ${section('Thông số xe', kv([['Tài xế', d.driver ? esc(d.driver.full_name) + ` <small class="muted">(${esc(d.driver.username)})</small>` : `<span class="bad">${T('chưa gán tài xế')}</span>`],
      ['Nhiên liệu', esc(fu?.label)], ['Tải trọng', `${v.capacity_weight_kg} kg`], ['Thể tích', v.capacity_volume_m3 ? `${v.capacity_volume_m3} m³` : ''],
      ['Chi phí vận hành', `${fmt(v.cost_per_km)} ₫/km`], ['Cố định', `${fmt(v.fixed_cost_vnd)} ₫`], ['Tiêu hao', `${v.consumption_rate ?? '—'} ${fu?.kind === 'electric' ? 'kWh' : 'L'}/100km`],
      ['Giá', `${fmt(v.fuel_price ?? fu?.price_vnd)} ${esc(fu?.price_unit || '')}`], ['Ca', `${v.start}–${v.end}`]]))}
    ${section('Theo dõi', kv([['Trạng thái', d.tracking.sharing ? `<span class="badge ok"><span class="live-dot"></span> ${T('Đang chia sẻ vị trí')}</span>` : `<span class="badge">${T('Không chia sẻ')}</span>`],
      ['Cập nhật', d.tracking.last ? new Date(d.tracking.last.ts * 1000).toLocaleTimeString('vi-VN') + ` · ±${d.tracking.last.acc ?? '?'} m` : '—']]))}
    ${section('Tuyến hôm nay', r ? kv([['Quãng đường', `${fmt(r.distance_km, 1)} km`], ['Ca', `${r.start}–${r.end}`], ['Tải trọng', `${r.load_weight_kg} kg (${r.utilization_weight_pct}%)`],
        ['Chi phí vận hành', `${fmt(r.operating_cost_vnd)} ₫`], ['Chi phí năng lượng', `${fmt(r.energy_cost_vnd)} ₫ · ${fmt(r.energy_amount, 2)} ${esc(r.energy_unit || '')}`],
        ['CO₂ trực tiếp', `${fmt(r.co2_direct_kg, 2)} kg`], ['Giờ cao điểm', `${r.peak_legs} chặng · +${r.peak_delay_min}′${r.late_risk ? ` · <span class="bad">${r.late_risk} ${T('nguy cơ trễ')}</span>` : ''}`],
        ['Đã xử lý', `${done} / ${r.stops.length}`]]) +
      `<ol class="stops" style="margin-top:10px">${r.stops.map((s, i) => `<li><span class="i">${i + 1}.</span>${orderLink(s.order_id)} <span class="muted">${s.arrival}${s.window ? ` · ${s.window}` : ''}</span> ${s.status && s.status !== 'pending' ? `<span class="badge ${s.status}">${STATUS_LABEL[s.status]}</span>` : ''}${s.peak ? ' <span title="giờ cao điểm">🚦</span>' : ''}</li>`).join('')}</ol>`
      : `<p class="hint">${T('Không có tuyến trong phương án hiện tại.')}</p>`)}
    ${section('Lịch sử', historyList(d.history))}`);
  if (r && RUN?.depot) {
    const dep = [RUN.depot.latitude, RUN.depot.longitude], c = colorFor(v.vehicle_id);
    miniMap([{ line: [dep, ...r.stops.map(s => [s.latitude, s.longitude]), dep], color: c }, { ll: dep, icon: depotIcon() },
      ...r.stops.map((s, i) => ({ ll: [s.latitude, s.longitude], icon: stopIcon(i + 1, c, s.status) })),
      ...(d.tracking.last ? [{ ll: [d.tracking.last.lat, d.tracking.last.lng], icon: L.divIcon({ className: '', iconSize: null, html: `<div class="veh-marker" style="--c:${c}">🚚</div>` }) }] : [])]);
  }
}
// Capture phase: Leaflet popups stop bubbling, so listen before they do.
document.addEventListener('click', e => {
  const el = e.target.closest('[data-order],[data-vehicle]');
  if (!el || el.closest('#menu')) return;
  if (el.tagName === 'BUTTON' && !el.classList.contains('oid')) return;
  e.preventDefault(); e.stopPropagation();
  const p = el.dataset.order ? openOrder(el.dataset.order) : openVehicle(el.dataset.vehicle);
  p.catch(err => toast(err.message, 'err'));
}, true);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

// ---------------------------------------------------------------- AI assistant
const AI = { history: [], configured: null };
function mdLite(s) {
  return esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^\s*[-•]\s+(.*)$/gm, '<li>$1</li>').replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`).replace(/\n/g, '<br>');
}
function renderChat() {
  const sugg = ['Tóm tắt tình hình giao hàng hôm nay', 'Xe nào chạy xa nhất và vì sao?', 'Vì sao có đơn chưa được phân công?', 'Làm sao giảm CO₂ mà không tăng nhiều chi phí?'];
  $('#ai-msgs').innerHTML = (AI.configured === false ? alertBox('warn', 'Trợ lý AI chưa được cấu hình: quản trị viên cần đặt biến môi trường <code>ANTHROPIC_API_KEY</code> trên server.') : '') +
    (AI.history.length ? AI.history.map(m => `<div class="msg ${m.role}">${m.role === 'assistant' ? mdLite(m.content) : esc(m.content)}</div>`).join('')
      : `<div class="hint" style="padding:6px 2px">${T('Trợ lý chỉ dùng số liệu của phương án đang xem; không gửi tên, SĐT, địa chỉ khách.')}</div>` +
        `<div class="chips">${sugg.map(s => `<button class="secondary sm" data-ask="${esc(s)}">${esc(s)}</button>`).join('')}</div>`);
  $('#ai-msgs').scrollTop = $('#ai-msgs').scrollHeight;
}
async function askAI(q) {
  q = q.trim(); if (!q) return;
  AI.history.push({ role: 'user', content: q });
  renderChat();
  $('#ai-msgs').insertAdjacentHTML('beforeend', `<div class="msg assistant thinking">${T('Đang suy nghĩ…')}</div>`);
  $('#ai-send').disabled = true;
  try {
    const { body } = await api('/api/assistant/ask', { method: 'POST', body: JSON.stringify({ question: q, history: AI.history.slice(0, -1) }) });
    AI.history.push({ role: 'assistant', content: body.answer });
  } catch (err) {
    AI.history.pop();
    toast(err.message, 'err');
    if (/chưa được cấu hình/.test(err.message)) AI.configured = false;
  } finally { $('#ai-send').disabled = false; renderChat(); }
}
async function toggleAI() {
  const p = $('#ai-panel'); p.hidden = !p.hidden;
  if (p.hidden) return;
  if (AI.configured === null) { try { AI.configured = (await api('/api/assistant/status')).body.configured; } catch { AI.configured = null; } }
  renderChat(); $('#ai-input').focus();
}
document.addEventListener('DOMContentLoaded', () => {
  $('#ai-fab').onclick = toggleAI;
  $('#ai-close').onclick = toggleAI;
  $('#ai-clear').onclick = () => { AI.history = []; renderChat(); };
  $('#ai-form').onsubmit = e => { e.preventDefault(); const v = $('#ai-input').value; $('#ai-input').value = ''; askAI(v); };
  $('#ai-msgs').onclick = e => { const b = e.target.closest('[data-ask]'); if (b) askAI(b.dataset.ask); };
  $('#drawer-close').onclick = closeDrawer;
  $('#drawer-backdrop').onclick = closeDrawer;
});
