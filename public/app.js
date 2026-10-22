'use strict';
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 0) => (v == null ? '<span class="tag">thiếu dữ liệu</span>' : Number(v).toLocaleString('vi-VN', { maximumFractionDigits: d }));
const COLORS = ['#1f8a4c', '#2563eb', '#d97706', '#9333ea', '#dc2626', '#0891b2', '#65a30d', '#db2777', '#4b5563', '#7c3aed'];
const METRIC_LABEL = {
  distance_km: 'Quãng đường (km)', duration_min: 'Tổng thời gian (phút)', total_cost_vnd: 'Tổng chi phí (VND)',
  energy_cost_vnd: 'Chi phí năng lượng (VND)', co2_direct_kg: 'CO₂ trực tiếp (kg)', co2_grid_indirect_kg: 'CO₂ gián tiếp điện lưới (kg)',
  co2_per_km: 'CO₂/km (kg)', vehicles_used: 'Số xe dùng', orders_unassigned: 'Đơn chưa phân công',
};

let CFG = null, RUN = null, ME = null, map, layers;
const api = Auth.api;
const can = (...roles) => roles.includes(ME?.role);
const busy = async (btn, fn) => { btn.disabled = true; try { await fn(); } catch (e) { alert(e.message); } finally { btn.disabled = false; } };

// ---------- Tabs ----------
document.querySelectorAll('header nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('header nav button, .tab').forEach(x => x.classList.remove('active'));
  b.classList.add('active'); $(`#tab-${b.dataset.tab}`).classList.add('active');
  if (b.dataset.tab === 'dashboard') setTimeout(() => map.invalidateSize(), 50);
  if (b.dataset.tab === 'history') loadHistory();
  if (b.dataset.tab === 'dispatch') loadDispatch();
  if (b.dataset.tab === 'admin') loadAdmin();
});
document.querySelectorAll('.subnav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('.subnav button, .sub').forEach(x => x.classList.remove('active'));
  b.classList.add('active'); $(`#sub-${b.dataset.sub}`).classList.add('active');
});

/** Hide controls the current role cannot use. The API enforces the same rules. */
function applyRoles() {
  document.querySelectorAll('[data-roles]').forEach(el => {
    if (el.dataset.roles.split(',').includes(ME.role)) el.removeAttribute('data-hidden-role');
    else el.setAttribute('data-hidden-role', '');
  });
}

// ---------- Map ----------
function initMap() {
  map = L.map('map').setView([10.7769, 106.7009], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
  layers = L.layerGroup().addTo(map);
}

function drawMap(depot, orders, result) {
  layers.clearLayers();
  const bounds = [];
  if (depot) {
    L.marker([depot.latitude, depot.longitude], { title: depot.name }).bindPopup(`<b>Kho:</b> ${esc(depot.name)}`).addTo(layers);
    bounds.push([depot.latitude, depot.longitude]);
  }
  const assigned = new Set();
  result?.routes.forEach((r, i) => {
    const color = COLORS[i % COLORS.length];
    const pts = [[depot.latitude, depot.longitude], ...r.stops.map(s => [s.latitude, s.longitude]), [depot.latitude, depot.longitude]];
    L.polyline(pts, { color, weight: 4, opacity: .8, dashArray: r.fuel_blend_code === 'electricity' ? '6 6' : null })
      .bindTooltip(`${esc(r.vehicle_id)} · ${r.distance_km} km`).addTo(layers);
    r.stops.forEach((s, k) => {
      assigned.add(s.order_id);
      L.circleMarker([s.latitude, s.longitude], { radius: 9, color, fillColor: color, fillOpacity: .9, weight: 1 })
        .bindTooltip(String(k + 1), { permanent: true, direction: 'center', className: 'num' })
        .bindPopup(`<b>${esc(s.order_id)}</b><br>Xe: ${esc(r.vehicle_id)} (điểm ${k + 1})<br>Đến: ${s.arrival}${s.window ? `<br>Khung giờ: ${s.window}` : ''}`).addTo(layers);
    });
  });
  orders.forEach(o => {
    bounds.push([o.latitude, o.longitude]);
    if (!assigned.has(o.order_id)) L.circleMarker([o.latitude, o.longitude], { radius: 6, color: result ? '#c0392b' : '#555', fillOpacity: .5 })
      .bindPopup(`<b>${esc(o.order_id)}</b><br>${result ? 'CHƯA PHÂN CÔNG' : 'Chưa tối ưu'}`).addTo(layers);
  });
  if (bounds.length) map.fitBounds(bounds, { padding: [20, 20] });
}

// ---------- Dashboard ----------
function deltaHtml(p, lowerIsBetter = true) {
  if (p == null) return '';
  const good = lowerIsBetter ? p < 0 : p > 0;
  return `<span class="${p === 0 ? '' : good ? 'good' : 'bad'}">${p > 0 ? '+' : ''}${p}% vs baseline</span>`;
}

function renderRun(run) {
  RUN = run;
  $('#btn-publish').disabled = !run.optimized.routes.length;
  $('#publish-msg').innerHTML = '';
  const t = run.optimized.totals, cmp = Object.fromEntries(run.comparison.rows.map(r => [r.metric, r.change_pct]));
  $('#kpis').innerHTML = [
    ['Đơn đã phân công', `${t.orders_assigned}/${t.orders_total}`, `${t.assignment_rate_pct}%`],
    ['Số xe dùng', t.vehicles_used, deltaHtml(cmp.vehicles_used)],
    ['Tổng km', fmt(t.distance_km, 1), deltaHtml(cmp.distance_km)],
    ['Thời gian (phút)', fmt(t.duration_min), deltaHtml(cmp.duration_min)],
    ['Tổng chi phí (VND)', fmt(t.total_cost_vnd), deltaHtml(cmp.total_cost_vnd)],
    ['CO₂ trực tiếp (kg)', fmt(t.co2_direct_kg, 2), deltaHtml(cmp.co2_direct_kg)],
    ['CO₂ gián tiếp điện (kg)', fmt(t.co2_grid_indirect_kg, 2), '<span class="tag">báo cáo riêng</span>'],
  ].map(([l, v, d]) => `<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join('');

  $('#comparison').innerHTML = `<table><tr><th>Chỉ số</th><th>Baseline</th><th>Tối ưu</th><th>Thay đổi</th></tr>${
    run.comparison.rows.map(r => `<tr><td>${METRIC_LABEL[r.metric] || r.metric}</td><td>${fmt(r.reference, 2)}</td><td>${fmt(r.candidate, 2)}</td><td>${r.change_pct == null ? '—' : deltaHtml(r.change_pct).replace(' vs baseline', '')}</td></tr>`).join('')
  }</table><p class="hint">Baseline: ${esc(run.baseline.meta.algorithm)}. Cùng tập đơn, đội xe, ma trận khoảng cách và ràng buộc. ${run.comparison.worse.length ? `<b class="bad">Chỉ số xấu hơn: ${run.comparison.worse.map(m => METRIC_LABEL[m] || m).join(', ')}</b>` : ''}</p>
  <p class="hint">Bộ giải: ${esc(run.optimized.meta.algorithm)} · ${run.optimized.meta.time_ms} ms · trạng thái <b>${run.optimized.meta.status}</b></p>`;

  $('#unassigned').innerHTML = run.optimized.unassigned.length
    ? `<table><tr><th>Đơn</th><th>Mã lỗi</th><th>Lý do</th></tr>${run.optimized.unassigned.map(u => `<tr><td>${esc(u.order_id)}</td><td><code>${u.code}</code></td><td>${esc(u.message)}</td></tr>`).join('')}</table>`
    : '<div class="ok">Tất cả đơn đã được phân công.</div>';

  $('#routes').innerHTML = `<div class="tbl-wrap"><table><tr><th>Xe</th><th>Nhiên liệu</th><th>Thứ tự giao</th><th>km</th><th>Thời gian</th><th>Tải</th><th>Năng lượng</th><th>Chi phí VND</th><th>CO₂ trực tiếp</th><th>Hệ số (nguồn, năm)</th></tr>${
    run.optimized.routes.map((r, i) => `<tr>
      <td><span class="swatch" style="background:${COLORS[i % COLORS.length]}"></span>${esc(r.vehicle_id)}<br><span class="tag">${esc(CFG.vehicle_types[r.vehicle_type]?.label)}</span></td>
      <td>${esc(r.fuel_blend_code)}</td>
      <td>${r.stops.map(s => `${esc(s.order_id)}<small>@${s.arrival}</small>`).join(' → ')}</td>
      <td>${fmt(r.distance_km, 2)}</td><td>${r.start}–${r.end}</td>
      <td>${r.load_weight_kg}/${r.capacity_weight_kg} kg (${r.utilization_weight_pct}%)</td>
      <td>${fmt(r.energy_amount, 2)} ${r.energy_unit || ''}</td>
      <td>${fmt(r.operating_cost_vnd + (r.energy_cost_vnd ?? 0))}</td>
      <td>${fmt(r.co2_direct_kg, 3)}${r.co2_grid_indirect_kg ? `<br><small>+${fmt(r.co2_grid_indirect_kg, 3)} gián tiếp</small>` : ''}</td>
      <td><small>${r.factor ? `${r.factor.value.toFixed(3)} ${esc(r.factor.unit)}<br>${esc(r.factor.source)}, ${r.factor.year ?? '?'}${r.factor.official ? '' : ' <span class="tag sim">mô phỏng</span>'}` : '—'}</small></td>
    </tr>`).join('')
  }</table></div>`;

  const warns = [...(run.optimized.totals.warnings || [])];
  if (run.assumptions.routing_fallback) warns.unshift(run.assumptions.routing_fallback);
  $('#run-warnings').innerHTML = warns.map(w => `<div class="warn">⚠ ${esc(w)}</div>`).join('') +
    `<div class="warn">ℹ ${esc(run.assumptions.scope_note)}<br>ℹ ${esc(run.assumptions.routing_note)}</div>`;
  drawMap(run.depot, run.input.orders, run.optimized);
  renderFuelEditor();
}

// ---------- Orders ----------
function reportHtml(r) {
  let h = '';
  if (r.errors?.length) h += `<div class="err"><b>${r.errors.length} dòng lỗi — chưa nhập dữ liệu nào. Sửa và nhập lại:</b><ul>${r.errors.map(e => `<li>Dòng ${e.line} ${esc(e.order_id || e.vehicle_id || '')}: ${e.errors.map(esc).join('; ')}</li>`).join('')}</ul></div>`;
  else if (r.imported != null) h += `<div class="ok">Đã lưu ${r.imported} dòng (tổng ${r.total}).</div>`;
  if (r.warnings?.length) h += `<div class="warn"><b>${r.warnings.length} cảnh báo:</b><ul>${r.warnings.slice(0, 20).map(w => `<li>Dòng ${w.line} ${esc(w.order_id || w.vehicle_id || '')}: ${esc(w.message)}</li>`).join('')}</ul></div>`;
  return h;
}
const t2 = m => (m == null ? '' : `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`);

async function loadOrders() {
  if (!can('admin', 'dispatcher', 'ops_manager')) return [];
  const { body: orders } = await api('/api/orders');
  $('#orders-table').innerHTML = `<p>${orders.length} đơn</p><div class="tbl-wrap"><table><tr><th>order_id</th><th>Địa chỉ</th><th>Tọa độ</th><th>kg</th><th>m³</th><th>Khung giờ</th><th>Phục vụ (ph)</th><th>Ưu tiên</th><th></th></tr>${
    orders.map(o => `<tr><td>${esc(o.order_id)}</td><td>${esc(o.address)}</td><td>${o.latitude}, ${o.longitude}</td><td>${o.weight_kg}</td><td>${o.volume_m3}</td><td>${t2(o.tw_start)}${o.tw_start != null || o.tw_end != null ? '–' : ''}${t2(o.tw_end)}</td><td>${o.service_time_min}</td><td>${o.priority}</td><td>${can('admin', 'dispatcher') ? `<button class="danger" data-del-order="${esc(o.order_id)}">Xóa</button>` : ''}</td></tr>`).join('')
  }</table></div>`;
  return orders;
}
$('#orders-table').onclick = async e => {
  const id = e.target.dataset.delOrder;
  if (id && confirm(`Xóa đơn ${id}?`)) { await api(`/api/orders/${encodeURIComponent(id)}`, { method: 'DELETE' }); loadOrders(); }
};
$('#btn-orders-import').onclick = e => busy(e.target, async () => {
  const f = $('#orders-file').files[0]; if (!f) return alert('Chọn file');
  const fd = new FormData(); fd.append('file', f);
  const { body } = await api(`/api/orders/import?mode=${$('#orders-mode').value}`, { method: 'POST', body: fd });
  $('#orders-report').innerHTML = reportHtml(body); loadOrders();
});
$('#btn-orders-clear').onclick = async () => { if (confirm('Xóa tất cả đơn?')) { await api('/api/orders', { method: 'DELETE' }); loadOrders(); } };
$('#order-form').onsubmit = async e => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  const { body } = await api('/api/orders', { method: 'POST', body: JSON.stringify(data) });
  $('#orders-report').innerHTML = reportHtml(body);
  if (!body.errors?.length) { e.target.reset(); loadOrders(); }
};

// ---------- Vehicles ----------
function fuelOptions(type, selected) {
  const vt = CFG.vehicle_types[type]; if (!vt) return '';
  return [...vt.allowed.map(f => [f, '']), ...vt.simulation_allowed.map(f => [f, ' (mô phỏng)'])]
    .map(([f, s]) => `<option value="${f}" ${f === selected ? 'selected' : ''}>${esc(CFG.fuels[f].label)}${s}</option>`).join('');
}
async function loadVehicles() {
  const { body: vs } = await api('/api/vehicles');
  $('#vehicles-table').innerHTML = `<div class="tbl-wrap"><table><tr><th>Xe</th><th>Tài xế</th><th>Loại</th><th>Nhiên liệu</th><th>Tải trọng</th><th>Thể tích</th><th>VND/km</th><th>Cố định</th><th>Tiêu hao /100km</th><th>Giá</th><th>Ca</th><th>Sẵn sàng</th><th></th></tr>${
    vs.map(v => { const fu = CFG.fuels[v.fuel_blend_code]; return `<tr><td>${esc(v.vehicle_id)}</td><td>${v.driver ? esc(v.driver) : '<span class="tag">chưa gán</span>'}</td><td>${esc(CFG.vehicle_types[v.vehicle_type]?.label)}</td>
      <td>${esc(fu?.label)} ${fu && !fu.official ? '<span class="tag sim">mô phỏng</span>' : ''}</td><td>${v.capacity_weight_kg} kg</td><td>${v.capacity_volume_m3 ?? '—'} m³</td>
      <td>${fmt(v.cost_per_km)}</td><td>${fmt(v.fixed_cost_vnd)}</td><td>${v.consumption_rate ?? '<span class="tag">thiếu</span>'} ${fu?.kind === 'electric' ? 'kWh' : 'L'}</td>
      <td>${fmt(v.fuel_price ?? fu?.price_vnd)} ${v.fuel_price == null ? '<span class="tag">mặc định</span>' : ''}</td><td>${t2(v.start_time)}–${t2(v.end_time)}</td>
      <td>${v.available ? '✅' : '⛔'}</td><td>${can('admin', 'fleet_manager') ? `<button class="danger" data-del-veh="${esc(v.vehicle_id)}">Xóa</button>` : ''}</td></tr>`; }).join('')
  }</table></div>`;
  return vs;
}
$('#vehicles-table').onclick = async e => {
  const id = e.target.dataset.delVeh;
  if (id && confirm(`Xóa xe ${id}?`)) { await api(`/api/vehicles/${encodeURIComponent(id)}`, { method: 'DELETE' }); loadVehicles(); }
};
$('#btn-vehicles-import').onclick = e => busy(e.target, async () => {
  const f = $('#vehicles-file').files[0]; if (!f) return alert('Chọn file');
  const fd = new FormData(); fd.append('file', f);
  const { body } = await api(`/api/vehicles/import?mode=${$('#vehicles-mode').value}`, { method: 'POST', body: fd });
  $('#vehicles-report').innerHTML = reportHtml(body); loadVehicles();
});
$('#vf-type').onchange = () => { $('#vf-fuel').innerHTML = fuelOptions($('#vf-type').value); };
$('#vehicle-form').onsubmit = async e => {
  e.preventDefault();
  const fd = new FormData(e.target), data = Object.fromEntries(fd);
  data.available = fd.has('available'); data.confirm_simulation_fuel = fd.has('confirm_simulation_fuel');
  const { body: existing } = await api('/api/vehicles');
  const isUpdate = existing.some(v => v.vehicle_id === data.vehicle_id);
  const { body } = isUpdate
    ? await api(`/api/vehicles/${encodeURIComponent(data.vehicle_id)}`, { method: 'PUT', body: JSON.stringify(data) })
    : await api('/api/vehicles', { method: 'POST', body: JSON.stringify(data) });
  $('#vehicles-report').innerHTML = reportHtml(body);
  if (!body.errors?.length) loadVehicles();
};

// ---------- Fuel scenarios ----------
function renderFuelEditor() {
  if (!RUN) { $('#fuel-editor').innerHTML = '<div class="warn">Chạy tối ưu trước.</div>'; return; }
  $('#fuel-editor').innerHTML = `<table><tr><th>Xe</th><th>Hiện tại</th><th>Nhiên liệu mới</th><th>Tiêu hao /100km</th><th>Giá</th><th>Hệ số tùy chỉnh</th><th>Xác nhận mô phỏng</th></tr>${
    RUN.input.vehicles.filter(v => v.available).map(v => `<tr data-vid="${esc(v.vehicle_id)}"><td>${esc(v.vehicle_id)}</td><td>${esc(v.fuel_blend_code)} · ${v.consumption_rate ?? '?'}</td>
      <td><select data-k="fuel_blend_code">${fuelOptions(v.vehicle_type, v.fuel_blend_code)}</select></td>
      <td><input data-k="consumption_rate" size="6" placeholder="${v.consumption_rate ?? ''}"></td>
      <td><input data-k="fuel_price" size="8" placeholder="${v.fuel_price ?? CFG.fuels[v.fuel_blend_code]?.price_vnd ?? ''}"></td>
      <td><input data-k="emission_factor_value" size="6"></td>
      <td><input type="checkbox" data-k="confirm_simulation_fuel"></td></tr>`).join('')
  }</table>`;
}
$('#btn-scenario').onclick = e => busy(e.target, async () => {
  if (!RUN) return alert('Chạy tối ưu trước');
  const overrides = {};
  document.querySelectorAll('#fuel-editor tr[data-vid]').forEach(tr => {
    const v = RUN.input.vehicles.find(x => x.vehicle_id === tr.dataset.vid), o = {};
    tr.querySelectorAll('[data-k]').forEach(el => {
      const k = el.dataset.k;
      if (el.type === 'checkbox') { if (el.checked) o[k] = true; }
      else if (el.value !== '' && !(k === 'fuel_blend_code' && el.value === v.fuel_blend_code)) o[k] = k === 'fuel_blend_code' ? el.value : Number(el.value);
    });
    if (Object.keys(o).some(k => k !== 'confirm_simulation_fuel')) overrides[v.vehicle_id] = o;
  });
  const { status, body } = await api(`/api/optimization/${RUN.id}/fuel-scenario`, { method: 'POST', body: JSON.stringify({ overrides, mode: $('#sc-mode').value, name: $('#sc-name').value }) });
  if (status === 422) { $('#scenario-result').innerHTML = `<div class="err">${body.errors.map(x => `${esc(x.vehicle_id)}: ${esc(x.error)}`).join('<br>')}</div>`; return; }
  RUN.scenarios.push(body);
  const t = body.result.totals;
  $('#scenario-result').innerHTML = `<h3>${esc(body.name)}</h3><div class="ok">${esc(body.basis_note)}</div>
    <table><tr><th>Chỉ số</th><th>Phương án tối ưu hiện tại</th><th>Kịch bản</th><th>Thay đổi</th></tr>${
      body.comparison.rows.map(r => `<tr><td>${METRIC_LABEL[r.metric] || r.metric}</td><td>${fmt(r.reference, 3)}</td><td>${fmt(r.candidate, 3)}</td><td>${r.change_pct == null ? '—' : deltaHtml(r.change_pct).replace(' vs baseline', '')}</td></tr>`).join('')
    }<tr><td>CO₂ hóa thạch / sinh học (kg)</td><td colspan="3">${fmt(t.co2_fossil_kg, 3)} / ${fmt(t.co2_biogenic_kg, 3)} (CO₂ sinh học từ ethanol báo cáo riêng)</td></tr>
    <tr><td>CO₂ / đơn (kg)</td><td colspan="3">${fmt(t.co2_per_order, 4)}</td></tr></table>
    ${t.warnings.map(w => `<div class="warn">⚠ ${esc(w)}</div>`).join('')}`;
});

// ---------- History ----------
async function loadHistory() {
  const { body: runs } = await api('/api/optimization');
  $('#history').innerHTML = runs.length ? `<table><tr><th>Thời điểm</th><th>Người chạy</th><th>Đơn</th><th>Xe</th><th>km</th><th>Chi phí</th><th>CO₂</th><th></th></tr>${
    runs.map(r => `<tr><td>${new Date(r.created_at).toLocaleString('vi-VN')} ${r.published ? '<span class="badge delivered">đang phát hành</span>' : ''}</td><td>${esc(r.created_by || '')}</td>
      <td>${r.totals.orders_assigned}/${r.totals.orders_total}</td><td>${r.totals.vehicles_used}</td>
      <td>${fmt(r.totals.distance_km, 1)}</td><td>${fmt(r.totals.total_cost_vnd)}</td><td>${fmt(r.totals.co2_direct_kg, 2)}</td>
      <td><button class="secondary" data-open="${r.id}">Mở</button> <button class="secondary" data-dl="/api/reports/${r.id}?format=xlsx">XLSX</button> <button class="secondary" data-dl="/api/reports/${r.id}?format=csv">CSV</button></td></tr>`).join('')
  }</table>` : '<p class="hint">Chưa có lần tối ưu nào.</p>';
}
$('#history').onclick = async e => {
  if (e.target.dataset.dl) return busy(e.target, () => Auth.download(e.target.dataset.dl));
  if (!e.target.dataset.open) return;
  const { body } = await api(`/api/optimization/${e.target.dataset.open}`);
  renderRun(body); document.querySelector('nav button[data-tab=dashboard]').click();
};

// ---------- Method ----------
function renderMethod() {
  const b = CFG.base_factors;
  $('#method').innerHTML = `<div class="method">
    <div class="warn">${esc(CFG.illustrative_note)} · Phiên bản cấu hình: <code>${esc(CFG.version)}</code></div>
    <h3>Phạm vi phát thải</h3><p>${esc(CFG.scope_note)}</p>
    <h3>Công thức</h3><ul>
      <li>Nhiên liệu (L) = km × tiêu hao (L/100km) / 100 · CO₂ (kg) = L × EF · Chi phí = L × giá</li>
      <li>Điện (kWh) = km × tiêu hao (kWh/100km) / 100 · CO₂ gián tiếp = kWh × EF lưới · CO₂ ống xả = 0</li>
      <li>Xăng pha ethanol: EF_blend ≈ (1 − x)·EF_xăng + x·EF_ethanol (x = tỷ lệ thể tích). Phần ethanol là CO₂ sinh học, báo cáo riêng; không coi vòng đời = 0.</li>
      <li>Chi phí tổng = km × cost_per_km (vận hành ngoài năng lượng) + chi phí cố định/xe sử dụng + chi phí năng lượng.</li>
      <li>Hàm mục tiêu bộ giải = chi phí tổng + giá CO₂ quy đổi × kg CO₂ trực tiếp (trọng số chờ chủ dự án duyệt; mặc định 0).</li></ul>
    <h3>Hệ số nền</h3><table><tr><th>Khóa</th><th>Giá trị</th><th>Nguồn</th><th>Năm</th><th>Khu vực</th></tr>${
      Object.entries(b).map(([k, f]) => `<tr><td>${k}</td><td>${f.value} ${esc(f.unit)}</td><td>${esc(f.source)}</td><td>${f.year}</td><td>${esc(f.geography)}</td></tr>`).join('')}</table>
    <h3>Cấu hình nhiên liệu</h3><table><tr><th>Mã</th><th>Tên</th><th>Ethanol</th><th>Trạng thái</th><th>Giá mặc định</th></tr>${
      Object.entries(CFG.fuels).map(([k, f]) => `<tr><td>${k}</td><td>${esc(f.label)}</td><td>${f.ethanol_share_volume != null ? (f.ethanol_share_volume * 100) + '%' : '—'}</td><td>${f.status}${f.official ? '' : ' <span class="tag sim">không chính thức</span>'}</td><td>${fmt(f.price_vnd)} ${f.price_unit}</td></tr>`).join('')}</table>
    <h3>Định tuyến</h3><p>${esc(CFG.routing.note)}</p>
    <h3>Baseline</h3><p>Thứ tự đơn gốc trong file; lấp đầy xe theo thứ tự danh sách xe; chuyển xe khi vi phạm tải/khung giờ. Cùng ma trận và ràng buộc với bộ tối ưu.</p>
    <h3>AI / ML</h3><p>Chưa có mô hình được huấn luyện trên dữ liệu thật. API <code>/api/predictions/travel-time</code> trả ước tính heuristic với <code>model_status: not_trained</code>.</p>
  </div>`;
}

// ---------- Boot ----------
async function refreshDepot() {
  const { body: d } = await api('/api/depot');
  if (d) { $('#depot-name').value = d.name; $('#depot-lat').value = d.latitude; $('#depot-lng').value = d.longitude; }
  return d;
}
$('#btn-depot').onclick = e => busy(e.target, async () => {
  await api('/api/depot', { method: 'PUT', body: JSON.stringify({ name: $('#depot-name').value, latitude: $('#depot-lat').value, longitude: $('#depot-lng').value }) });
  drawMap(await refreshDepot(), await loadOrders(), null);
});
$('#btn-sample').onclick = e => busy(e.target, async () => {
  if (!confirm('Thay toàn bộ kho/đơn/xe hiện có bằng dữ liệu minh họa?')) return;
  await api('/api/sample/load', { method: 'POST' });
  const d = await refreshDepot(), o = await loadOrders(); await loadVehicles();
  drawMap(d, o, null);
});
$('#btn-run').onclick = e => busy(e.target, async () => {
  const { body } = await api('/api/optimization/run', { method: 'POST', body: JSON.stringify({ weights: { co2_vnd_per_kg: Number($('#w-co2').value) || 0 }, time_limit_s: Number($('#time-limit').value) || 5 }) });
  renderRun(body);
});

// ---------- Publish & delivery tracking ----------
$('#btn-publish').onclick = e => busy(e.target, async () => {
  if (!RUN || !confirm('Phát hành phương án này cho tài xế? Phương án đang phát hành trước đó (nếu có) sẽ bị thay thế.')) return;
  const { body } = await api(`/api/optimization/${RUN.id}/publish`, { method: 'POST' });
  $('#publish-msg').innerHTML = `<div class="ok">Đã phát hành lúc ${new Date(body.published_at).toLocaleTimeString('vi-VN')}.</div>` +
    (body.vehicles_without_driver.length ? `<div class="warn">⚠ Xe chưa gán tài xế (tài xế sẽ không thấy tuyến): <b>${body.vehicles_without_driver.map(esc).join(', ')}</b>. Gán trong Quản trị → Tài khoản.</div>` : '');
});

const STATUS_LABEL = { pending: 'Chưa giao', delivered: 'Đã giao', failed: 'Thất bại' };
function locationCell(s) {
  if (!s.location_check) return '';
  if (s.location_check === 'missing') return `<span class="badge pending">không có định vị</span><br><small>${esc(s.location_error || '')}</small>`;
  const l = s.location;
  return `<span class="badge ${s.location_check === 'ok' ? 'delivered' : 'failed'}">${s.location_check === 'ok' ? 'đúng vị trí' : 'xa điểm giao'}</span>
    <br><small>cách ${fmt(s.distance_to_stop_m)} m (±${fmt(l.accuracy_m)} m, ngưỡng ${s.location_threshold_m} m) ·
    <a href="https://www.google.com/maps/search/?api=1&query=${l.latitude},${l.longitude}" target="_blank" rel="noopener">xem</a></small>`;
}
async function loadDispatch() {
  const { body: b } = await api('/api/dispatch');
  if (!b) { $('#dispatch').innerHTML = '<div class="warn">Chưa có phương án nào được phát hành. Điều phối viên chạy tối ưu rồi bấm “Phát hành cho tài xế”.</div>'; return; }
  const total = b.counts.pending + b.counts.delivered + b.counts.failed;
  $('#dispatch').innerHTML = `<p>Phát hành bởi <b>${esc(b.published_by)}</b> lúc ${new Date(b.published_at).toLocaleString('vi-VN')}</p>
    <div class="kpis">${['delivered', 'failed', 'pending'].map(k => `<div class="kpi"><div class="l">${STATUS_LABEL[k]}</div><div class="v">${b.counts[k]}/${total}</div></div>`).join('')}</div>
    ${b.routes.map(r => `<h3>${esc(r.vehicle_id)} — ${r.driver ? esc(r.driver.full_name) + ` (${esc(r.driver.username)})` : '<span class="bad">chưa gán tài xế</span>'}</h3>
      <table><tr><th>#</th><th>Đơn</th><th>Dự kiến</th><th>Khung giờ</th><th>Trạng thái</th><th>Thực tế</th><th>Xác nhận vị trí</th><th>Lý do / ghi chú</th><th>Cập nhật</th></tr>${
        r.stops.map((s, i) => `<tr><td>${i + 1}</td><td>${esc(s.order_id)}</td><td>${s.arrival}</td><td>${esc(s.window)}</td>
          <td><span class="badge ${s.status}">${STATUS_LABEL[s.status]}</span>${s.on_time === false ? ' <span class="badge failed">trễ</span>' : ''}</td>
          <td>${esc(s.actual_time || '')}</td><td>${locationCell(s)}</td><td>${esc(s.reason_label || '')} ${esc(s.note || '')}</td>
          <td><small>${s.recorded_at ? `${esc(s.recorded_by)} · ${new Date(s.recorded_at).toLocaleTimeString('vi-VN')}` : ''}</small></td></tr>`).join('')
      }</table>`).join('')}`;
}
$('#btn-dispatch-refresh').onclick = e => busy(e.target, loadDispatch);
setInterval(() => { if ($('#tab-dispatch').classList.contains('active')) loadDispatch().catch(() => {}); }, 30000);

// ---------- Admin ----------
let ROLE_LABELS = {};
async function loadAdmin() {
  const [{ body: users }, { body: roles }, { body: vehicles }] = await Promise.all([api('/api/admin/users'), api('/api/admin/roles'), api('/api/vehicles')]);
  ROLE_LABELS = roles;
  const roleOpts = sel => Object.entries(roles).map(([k, l]) => `<option value="${k}" ${k === sel ? 'selected' : ''}>${esc(l)}</option>`).join('');
  const vehOpts = sel => `<option value="">—</option>` + vehicles.map(v => `<option value="${esc(v.vehicle_id)}" ${v.vehicle_id === sel ? 'selected' : ''}>${esc(v.vehicle_id)}</option>`).join('');
  $('#uf-role').innerHTML = roleOpts('dispatcher');
  $('#uf-vehicle').innerHTML = `<option value="">— Xe (cho tài xế) —</option>` + vehicles.map(v => `<option value="${esc(v.vehicle_id)}">${esc(v.vehicle_id)}</option>`).join('');
  $('#users').innerHTML = `<table><tr><th>Tài khoản</th><th>Họ tên</th><th>Vai trò</th><th>Xe (tài xế)</th><th>Trạng thái</th><th>Đăng nhập gần nhất</th><th></th></tr>${
    users.map(u => `<tr data-user="${esc(u.username)}"><td>${esc(u.username)}${u.must_change_password ? ' <span class="tag">chờ đổi MK</span>' : ''}</td>
      <td><input data-f="full_name" value="${esc(u.full_name)}"></td>
      <td><select data-f="role">${roleOpts(u.role)}</select></td>
      <td><select data-f="vehicle_id">${vehOpts(u.vehicle_id)}</select></td>
      <td><select data-f="active"><option value="true" ${u.active ? 'selected' : ''}>Hoạt động</option><option value="false" ${u.active ? '' : 'selected'}>Đã khóa</option></select></td>
      <td><small>${u.last_login_at ? new Date(u.last_login_at).toLocaleString('vi-VN') : '—'}</small></td>
      <td><button class="secondary" data-save>Lưu</button> <button class="secondary" data-reset>Đặt lại MK</button></td></tr>`).join('')
  }</table>`;
  renderConfigEditor();
  loadConfigHistory();
  loadAudit();
}
$('#users').onclick = async e => {
  const tr = e.target.closest('tr[data-user]'); if (!tr) return;
  const username = tr.dataset.user;
  let data;
  if (e.target.hasAttribute('data-save')) {
    data = {};
    tr.querySelectorAll('[data-f]').forEach(el => { data[el.dataset.f] = el.dataset.f === 'active' ? el.value === 'true' : el.value; });
  } else if (e.target.hasAttribute('data-reset')) {
    const pw = prompt(`Mật khẩu tạm mới cho ${username} (≥ 8 ký tự). Người dùng sẽ phải đổi khi đăng nhập:`);
    if (!pw) return;
    data = { password: pw };
  } else return;
  busy(e.target, async () => {
    await api(`/api/admin/users/${encodeURIComponent(username)}`, { method: 'PUT', body: JSON.stringify(data) });
    $('#user-msg').innerHTML = `<div class="ok">Đã cập nhật ${esc(username)}.</div>`;
    loadAdmin(); loadVehicles();
  });
};
$('#user-form').onsubmit = async e => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  try {
    await api('/api/admin/users', { method: 'POST', body: JSON.stringify(data) });
    $('#user-msg').innerHTML = `<div class="ok">Đã tạo tài khoản ${esc(data.username)}. Gửi mật khẩu tạm cho người dùng qua kênh riêng.</div>`;
    e.target.reset(); loadAdmin(); loadVehicles();
  } catch (err) { $('#user-msg').innerHTML = `<div class="err">${esc(err.message)}</div>`; }
};

function renderConfigEditor() {
  const input = (path, val, type = 'number', extra = '') => `<input class="cfg-input" data-path="${path}" data-orig="${esc(val)}" type="${type}" step="any" value="${esc(val ?? '')}" ${extra}>`;
  const dw = CFG.default_weights || {};
  $('#config-editor').innerHTML = `
    <h3>Hệ số phát thải nền</h3><table><tr><th>Khóa</th><th>Giá trị</th><th>Đơn vị</th><th>Nguồn</th><th>Năm</th><th>Khu vực</th></tr>${
      Object.entries(CFG.base_factors).map(([k, f]) => `<tr><td>${k}</td><td>${input(`base_factors.${k}.value`, f.value)}</td><td>${esc(f.unit)}</td>
        <td>${input(`base_factors.${k}.source`, f.source, 'text', 'style="width:320px"')}</td><td>${input(`base_factors.${k}.year`, f.year)}</td>
        <td>${input(`base_factors.${k}.geography`, f.geography, 'text')}</td></tr>`).join('')}</table>
    <h3>Nhiên liệu: giá mặc định &amp; trạng thái</h3><table><tr><th>Mã</th><th>Tên</th><th>Giá mặc định</th><th>Tỷ lệ ethanol (0–1)</th><th>Trạng thái</th><th>Chính thức</th></tr>${
      Object.entries(CFG.fuels).map(([k, f]) => `<tr><td>${k}</td><td>${esc(f.label)}</td><td>${input(`fuels.${k}.price_vnd`, f.price_vnd)} ${esc(f.price_unit)}</td>
        <td>${f.ethanol_share_volume != null ? input(`fuels.${k}.ethanol_share_volume`, f.ethanol_share_volume) : '—'}</td>
        <td><select data-path="fuels.${k}.status" data-orig="${f.status}">${['supported', 'simulation', 'unverified'].map(s => `<option ${s === f.status ? 'selected' : ''}>${s}</option>`).join('')}</select></td>
        <td><select data-path="fuels.${k}.official" data-orig="${f.official}" data-bool><option value="true" ${f.official ? 'selected' : ''}>có</option><option value="false" ${f.official ? '' : 'selected'}>không</option></select></td></tr>`).join('')}</table>
    <h3>Loại xe: tốc độ trung bình</h3><table><tr><th>Loại</th><th>km/h</th></tr>${
      Object.entries(CFG.vehicle_types).map(([k, v]) => `<tr><td>${esc(v.label)}</td><td>${input(`vehicle_types.${k}.speed_kmh`, v.speed_kmh)}</td></tr>`).join('')}</table>
    <h3>Trọng số hàm mục tiêu &amp; định tuyến (mục 6.2, cần chủ dự án duyệt)</h3><table>
      <tr><td>Giá CO₂ quy đổi (VND/kg)</td><td>${input('default_weights.co2_vnd_per_kg', dw.co2_vnd_per_kg ?? 0)}</td></tr>
      <tr><td>Chi phí thời gian (VND/phút)</td><td>${input('default_weights.time_vnd_per_min', dw.time_vnd_per_min ?? 0)}</td></tr>
      <tr><td>Giới hạn thời gian giải mặc định (giây)</td><td>${input('default_weights.time_limit_s', dw.time_limit_s ?? 5)}</td></tr>
      <tr><td>Ngưỡng xác nhận vị trí giao hàng (m)</td><td>${input('delivery_check.max_distance_m', CFG.delivery_check?.max_distance_m ?? 300)}</td></tr>
      <tr><td>Hệ số đường vòng (khi không có OSRM)</td><td>${input('routing.detour_factor', CFG.routing.detour_factor)}</td></tr>
      <tr><td>Gắn nhãn "Dữ liệu minh họa"</td><td><select data-path="illustrative" data-orig="${CFG.illustrative}" data-bool><option value="true" ${CFG.illustrative ? 'selected' : ''}>có</option><option value="false" ${CFG.illustrative ? '' : 'selected'}>không</option></select></td></tr>
    </table><p class="hint">Phiên bản hiện tại: <code>${esc(CFG.version)}</code>${CFG.updated_by ? ` · sửa bởi ${esc(CFG.updated_by)}` : ''}</p>`;
}
$('#btn-cfg-save').onclick = e => busy(e.target, async () => {
  const changes = {};
  document.querySelectorAll('#config-editor [data-path]').forEach(el => {
    if (String(el.value) === String(el.dataset.orig)) return;
    changes[el.dataset.path] = el.hasAttribute('data-bool') ? el.value === 'true' : el.type === 'number' ? Number(el.value) : el.value;
  });
  if (!Object.keys(changes).length) { $('#cfg-msg').innerHTML = '<div class="warn">Chưa có thay đổi nào.</div>'; return; }
  try {
    const { body } = await api('/api/admin/config', { method: 'PUT', body: JSON.stringify({ changes, reason: $('#cfg-reason').value }) });
    CFG = body.config; $('#cfg-reason').value = '';
    $('#cfg-msg').innerHTML = `<div class="ok">Đã lưu phiên bản <code>${esc(body.change.version)}</code> (${body.change.changes.length} thay đổi). Áp dụng cho các lần tối ưu mới.</div>`;
    renderConfigEditor(); renderMethod(); loadConfigHistory(); applyDefaults();
  } catch (err) { $('#cfg-msg').innerHTML = `<div class="err">${esc(err.message)}</div>`; }
});
async function loadConfigHistory() {
  const { body: h } = await api('/api/admin/config/history');
  $('#config-history').innerHTML = h.length ? `<table><tr><th>Phiên bản</th><th>Thời điểm</th><th>Người sửa</th><th>Lý do</th><th>Thay đổi</th></tr>${
    h.map(x => `<tr><td><code>${esc(x.version)}</code></td><td>${new Date(x.at).toLocaleString('vi-VN')}</td><td>${esc(x.user)}</td><td>${esc(x.reason)}</td>
      <td><small>${x.changes.map(c => `${esc(c.path)}: ${esc(c.old)} → <b>${esc(c.new)}</b>`).join('<br>')}</small></td></tr>`).join('')
  }</table>` : '<p class="hint">Chưa có thay đổi — đang dùng cấu hình mặc định.</p>';
}
async function loadAudit() {
  const { body: a } = await api('/api/admin/audit?limit=300');
  $('#audit').innerHTML = `<div class="tbl-wrap"><table><tr><th>Thời điểm</th><th>Người dùng</th><th>Hành động</th><th>Chi tiết</th></tr>${
    a.map(x => `<tr><td>${new Date(x.at).toLocaleString('vi-VN')}</td><td>${esc(x.user || 'hệ thống')}</td><td>${esc(x.action)}</td><td><small>${esc(x.detail ? JSON.stringify(x.detail) : '')}</small></td></tr>`).join('')
  }</table></div>`;
}

function applyDefaults() {
  const dw = CFG.default_weights || {};
  $('#w-co2').value = dw.co2_vnd_per_kg ?? 0;
  $('#time-limit').value = dw.time_limit_s ?? 5;
}

$('#btn-logout').onclick = () => Auth.logout();
$('#btn-pw').onclick = () => Auth.changePassword();

(async () => {
  ME = await Auth.ensureUser();
  if (ME.role === 'driver') { location.replace('/driver.html'); return; }
  $('#who').textContent = `${ME.full_name} · ${ME.role_label}`;
  applyRoles();
  initMap();
  CFG = (await api('/api/config')).body;
  if (CFG.illustrative) { $('#banner').hidden = false; $('#banner').textContent = `⚠ ${CFG.illustrative_note} Phạm vi: CO₂ trực tiếp từ nhiên liệu vận hành.`; }
  applyDefaults();
  $('#vf-type').innerHTML = Object.entries(CFG.vehicle_types).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join('');
  $('#vf-fuel').innerHTML = fuelOptions($('#vf-type').value);
  renderMethod(); renderFuelEditor();
  const d = await refreshDepot(), o = await loadOrders(); await loadVehicles();
  drawMap(d, o, null);
  const { body: runs } = await api('/api/optimization');
  if (runs.length) renderRun((await api(`/api/optimization/${runs[0].id}`)).body);
})();
