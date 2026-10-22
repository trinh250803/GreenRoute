'use strict';
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LABEL = { pending: 'Chưa giao', delivered: 'Đã giao', failed: 'Thất bại' };
let REASONS = {};

/** One GPS fix for the report. Never blocks the report: on failure the reason is sent instead. */
function getLocation() {
  return new Promise(resolve => {
    if (!navigator.geolocation) return resolve({ location_error: 'Thiết bị không hỗ trợ định vị' });
    if (!window.isSecureContext) return resolve({ location_error: 'Trang không chạy HTTPS — trình duyệt chặn định vị' });
    navigator.geolocation.getCurrentPosition(
      p => resolve({ location: { latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy_m: p.coords.accuracy } }),
      err => resolve({ location_error: { 1: 'Tài xế không cho phép định vị', 2: 'Không xác định được vị trí', 3: 'Hết thời gian lấy định vị' }[err.code] || err.message }),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 });
  });
}
const CHECK = { ok: '📍 Đúng vị trí', far: '⚠ Xa điểm giao', missing: '❔ Không có định vị' };

const nowHHMM = () => { const d = new Date(); return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
const mapsUrl = s => `https://www.google.com/maps/dir/?api=1&destination=${s.latitude},${s.longitude}`;

async function load() {
  const { body } = await Auth.api('/api/driver/route');
  const r = body.route;
  if (!r) { $('#d-sum').textContent = ''; $('#d-body').innerHTML = `<div class="warn" style="margin:16px">${esc(body.message)}</div>`; return; }
  REASONS = body.fail_reasons;
  const done = r.stops.filter(s => s.status !== 'pending').length;
  $('#d-title').textContent = `🚚 Xe ${r.vehicle_id}`;
  $('#d-sum').innerHTML = `Xuất phát ${esc(r.start)} từ ${esc(r.depot.name)} · ${r.stops.length} điểm · ${r.distance_km} km · <b>${done}/${r.stops.length}</b> đã xử lý`;
  const next = r.stops.findIndex(s => s.status === 'pending');
  $('#d-body').innerHTML = r.stops.map((s, i) => `
    <div class="stop ${s.status}" data-id="${esc(s.order_id)}" ${i === next ? 'id="next-stop"' : ''}>
      <h3><span>${i + 1}. ${esc(s.order_id)}</span><span class="badge ${s.status}">${LABEL[s.status]}</span></h3>
      <div>${esc(s.address)}</div>
      <div class="meta">Dự kiến đến ${esc(s.arrival)}${s.window ? ` · Khung giờ <b>${esc(s.window)}</b>` : ''} · ${s.weight_kg} kg · dừng ~${s.service_time_min} phút</div>
      ${s.status !== 'pending' ? `<div class="meta">Ghi nhận ${esc(s.actual_time || '')}${s.reason_label ? ` · ${esc(s.reason_label)}` : ''}${s.note ? ` · ${esc(s.note)}` : ''}</div>
        <div class="meta">${CHECK[s.location_check] || ''}${s.distance_to_stop_m != null ? ` · cách điểm giao ${s.distance_to_stop_m} m` : ''}${s.location_error ? ` · ${esc(s.location_error)}` : ''}</div>
        <div class="actions"><button class="secondary" data-act="undo">Hoàn tác</button></div>` : `
      <div class="actions">
        <a href="${mapsUrl(s)}" target="_blank" rel="noopener">🧭 Chỉ đường</a>
        <button data-act="delivered">✅ Đã giao</button>
        <button class="danger" data-act="fail-open">✖ Thất bại</button>
      </div>
      <div class="fail-box" hidden>
        <select data-reason><option value="">— Chọn lý do —</option>${Object.entries(REASONS).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join('')}</select>
        <input data-note placeholder="Ghi chú (không bắt buộc)" maxlength="500">
        <button class="danger" data-act="failed">Xác nhận giao thất bại</button>
      </div>`}
    </div>`).join('');
}

$('#d-body').onclick = async e => {
  const act = e.target.dataset.act; if (!act) return;
  const card = e.target.closest('.stop'), id = card.dataset.id;
  if (act === 'fail-open') { card.querySelector('.fail-box').hidden = false; return; }
  let payload;
  if (act === 'delivered') payload = { status: 'delivered', local_time: nowHHMM() };
  else if (act === 'undo') { if (!confirm('Hoàn tác trạng thái đơn này?')) return; payload = { status: 'pending' }; }
  else {
    const reason = card.querySelector('[data-reason]').value;
    if (!reason) { alert('Chọn lý do giao thất bại'); return; }
    payload = { status: 'failed', reason, note: card.querySelector('[data-note]').value, local_time: nowHHMM() };
  }
  e.target.disabled = true;
  try {
    if (payload.status !== 'pending') {
      e.target.textContent = '📍 Đang lấy vị trí…';
      Object.assign(payload, await getLocation());
    }
    await Auth.api(`/api/driver/stops/${encodeURIComponent(id)}`, { method: 'POST', body: JSON.stringify(payload) });
    await load();
    document.getElementById('next-stop')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } catch (err) { alert(err.message); e.target.disabled = false; }
};

$('#btn-refresh').onclick = () => load().catch(err => alert(err.message));
$('#btn-logout').onclick = () => Auth.logout();

(async () => {
  const me = await Auth.ensureUser();
  if (me.role !== 'driver') { location.replace('/'); return; }
  await load();
})();
