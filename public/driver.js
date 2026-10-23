'use strict';
/* GreenRoute driver app: my route, live location sharing, delivery outcomes with GPS check. */
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LABEL = { pending: 'Chưa giao', delivered: 'Đã giao', failed: 'Thất bại' };
const CHECK = { ok: '📍 Đúng vị trí', far: '⚠ Xa điểm giao', missing: '❔ Không có định vị' };
const BUFFER_KEY = 'gr_loc_buffer';
const INTENT_KEY = 'gr_share_intent';  // the driver started a shift and has not ended it (survives reloads/server restarts)
const intent = { get: () => { try { return localStorage.getItem(INTENT_KEY) === '1'; } catch { return false; } },
                 set: on => { try { on ? localStorage.setItem(INTENT_KEY, '1') : localStorage.removeItem(INTENT_KEY); } catch { /* ignore */ } } };

let ROUTE = null, REASONS = {}, TRACK = { sharing: false, ping_interval_s: 20 }, TAB = 'todo';
let map, layers, meMarker, meCircle, watchId = null, lastFix = null, sendTimer = null, wakeLock = null, followMe = true, sentSinceStart = false, resuming = false;

function toast(msg, type = '') {
  const el = Object.assign(document.createElement('div'), { className: `toast ${type}`, textContent: msg });
  $('#toasts').appendChild(el); setTimeout(() => el.remove(), 4000);
}
const nowHHMM = () => { const d = new Date(); return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
const navUrl = s => `https://www.google.com/maps/dir/?api=1&destination=${s.latitude},${s.longitude}`;

// ---------------------------------------------------------------- Location buffer (survives brief offline periods)
function readBuffer() { try { return JSON.parse(localStorage.getItem(BUFFER_KEY) || '[]'); } catch { return []; } }
function writeBuffer(b) { try { localStorage.setItem(BUFFER_KEY, JSON.stringify(b.slice(-500))); } catch { /* ignore */ } }

async function flush() {
  const buf = readBuffer();
  if (!buf.length || !TRACK.sharing) return;
  try {
    await Auth.api('/api/driver/location', { method: 'POST', body: JSON.stringify({ points: buf }) });
    writeBuffer([]);
    sentSinceStart = true;
    renderShare();
  } catch (e) {
    // The server forgot the shift (restart on the free host): resume it instead of making the driver restart it.
    if (/Chưa bật chia sẻ/.test(e.message)) { if (intent.get()) resumeSharing(); else { stopWatch(); TRACK.sharing = false; renderShare(); } }
    // Network errors: keep the buffer and retry next tick.
  }
}

function onFix(p) {
  lastFix = { latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy_m: p.coords.accuracy,
    speed_mps: p.coords.speed, heading: p.coords.heading, ts: p.timestamp || Date.now() };
  drawMe();
  if (TRACK.sharing) {
    const buf = readBuffer(), prev = buf[buf.length - 1];
    // Keep at most one point per 5 s to save battery and data.
    if (!prev || lastFix.ts - prev.ts >= 5000) writeBuffer([...buf, lastFix]);
    if (!sentSinceStart) flush();  // first position goes out immediately, not after the first interval
  }
}
function onFixError(err) {
  const msg = { 1: 'Bạn chưa cho phép truy cập vị trí. Vào cài đặt trình duyệt → Quyền vị trí → Cho phép.', 2: 'Không xác định được vị trí (bật GPS).', 3: 'Lấy vị trí quá lâu, đang thử lại…' }[err.code] || err.message;
  toast(msg, 'err');
  if (err.code === 1) { setSharing(false); }
}
function startWatch() {
  if (watchId != null || !navigator.geolocation) return;
  watchId = navigator.geolocation.watchPosition(onFix, onFixError, { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 });
  // A coarse (network/cached) fix usually arrives in 1–2 s; the precise GPS fix replaces it when ready.
  if (!lastFix) navigator.geolocation.getCurrentPosition(p => { if (!lastFix) onFix(p); }, () => {}, { enableHighAccuracy: false, maximumAge: 120000, timeout: 10000 });
  clearInterval(sendTimer);
  sendTimer = setInterval(flush, (TRACK.ping_interval_s || 20) * 1000);
  requestWakeLock();
}
function stopWatch() {
  if (watchId != null) navigator.geolocation.clearWatch(watchId);
  watchId = null; clearInterval(sendTimer);
  try { wakeLock?.release(); } catch { /* ignore */ } wakeLock = null;
}
async function requestWakeLock() {
  try { if ('wakeLock' in navigator && TRACK.sharing) wakeLock = await navigator.wakeLock.request('screen'); } catch { /* not supported */ }
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && TRACK.sharing) { requestWakeLock(); flush(); } });
window.addEventListener('online', () => { if (TRACK.sharing) flush(); });

async function setSharing(on) {
  if (on) {
    if (!window.isSecureContext) return toast('Trang phải chạy HTTPS thì trình duyệt mới cho lấy vị trí.', 'err');
    if (!navigator.geolocation) return toast('Thiết bị không hỗ trợ định vị.', 'err');
  }
  if (!on) await flush();
  const { body } = await Auth.api('/api/driver/sharing', { method: 'POST', body: JSON.stringify({ on }) });
  TRACK = { ...TRACK, ...body };
  intent.set(on);
  if (on) { sentSinceStart = false; startWatch(); if (lastFix) onFix({ coords: { ...lastFix, accuracy: lastFix.accuracy_m, speed: lastFix.speed_mps }, timestamp: Date.now() }); toast('Đã bắt đầu ca — đang chia sẻ vị trí', 'ok'); }
  else { stopWatch(); toast('Đã kết thúc ca — ngừng chia sẻ vị trí'); }
  renderShare();
}
async function resumeSharing() {
  if (resuming) return;
  resuming = true;
  try {
    const { body } = await Auth.api('/api/driver/sharing', { method: 'POST', body: JSON.stringify({ on: true }) });
    TRACK = { ...TRACK, ...body };
    sentSinceStart = false; startWatch(); await flush(); renderShare();
  } catch { /* offline: next tick retries */ } finally { resuming = false; }
}

function renderShare() {
  const pending = readBuffer().length;
  $('#share').innerHTML = TRACK.sharing
    ? `<div class="share on"><span class="live-dot"></span><div class="txt"><b>Đang chia sẻ vị trí</b>${lastFix ? `GPS ±${Math.round(lastFix.accuracy_m)} m` : 'Đang lấy GPS…'} · gửi mỗi ${TRACK.ping_interval_s}s${pending ? ` · ${pending} điểm chờ gửi` : ''}<br><small class="muted">Giữ màn hình mở để không bị gián đoạn.</small></div><button class="secondary sm" id="btn-share">Kết thúc ca</button></div>`
    : `<div class="share off"><div class="txt"><b>Chưa chia sẻ vị trí</b>Bấm để điều phối viên thấy bạn đang ở đâu trong ca làm việc.</div><button id="btn-share">▶ Bắt đầu ca</button></div>`;
  $('#btn-share').onclick = e => { e.target.disabled = true; setSharing(!TRACK.sharing).catch(err => toast(err.message, 'err')).finally(() => { e.target.disabled = false; }); };
}

// ---------------------------------------------------------------- Map
function ensureMap() {
  if (map) return;
  map = L.map('d-map', { zoomControl: false, attributionControl: true }).setView([10.78, 106.68], 13);
  baseTiles(map, '&copy; OpenStreetMap');
  layers = L.layerGroup().addTo(map);
  map.on('dragstart', () => { followMe = false; });
}
function pin(n, status, isNext) {
  const bg = status === 'delivered' ? '#16a34a' : status === 'failed' ? '#dc2626' : isNext ? '#15803d' : '#64748b';
  const size = isNext ? 30 : 24;
  return L.divIcon({ className: '', iconSize: null, html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${bg};border:3px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.4);color:#fff;font-size:11px;font-weight:700;display:grid;place-items:center;transform:translate(-50%,-50%)">${status === 'delivered' ? '✓' : status === 'failed' ? '✕' : n}</div>` });
}
function drawRoute() {
  ensureMap(); layers.clearLayers();
  if (!ROUTE) return;
  const d = ROUTE.depot, pts = [[d.latitude, d.longitude], ...ROUTE.stops.map(s => [s.latitude, s.longitude])];
  L.polyline(pts, { color: '#15803d', weight: 4, opacity: .55, dashArray: '6 8' }).addTo(layers);
  L.marker([d.latitude, d.longitude], { icon: L.divIcon({ className: '', iconSize: null, html: '<div class="veh-marker" style="--c:#142019">🏭 Kho</div>' }) }).addTo(layers);
  const next = ROUTE.stops.find(s => s.status === 'pending');
  ROUTE.stops.forEach((s, i) => L.marker([s.latitude, s.longitude], { icon: pin(i + 1, s.status, s === next), zIndexOffset: s === next ? 500 : 0 })
    .bindPopup(`<b>${i + 1}. ${esc(s.order_id)}</b><br>${esc(s.address)}`).addTo(layers));
  if (lastFix && followMe) return drawMe(true);
  map.fitBounds(next ? [[next.latitude, next.longitude], ...(lastFix ? [[lastFix.latitude, lastFix.longitude]] : [[d.latitude, d.longitude]])] : pts, { padding: [40, 40], maxZoom: 16 });
}
function drawMe(center = false) {
  if (!map || !lastFix) return;
  const ll = [lastFix.latitude, lastFix.longitude];
  if (!meMarker) {
    meMarker = L.marker(ll, { zIndexOffset: 1000, icon: L.divIcon({ className: '', iconSize: [18, 18], iconAnchor: [9, 9], html: '<div class="me-dot"></div>' }) }).addTo(map);
    meCircle = L.circle(ll, { radius: lastFix.accuracy_m, color: '#2563eb', weight: 1, fillOpacity: .1 }).addTo(map);
    center = true;
  } else { meMarker.setLatLng(ll); meCircle.setLatLng(ll).setRadius(lastFix.accuracy_m); }
  if (center || followMe) map.setView(ll, Math.max(map.getZoom(), 15));
  if (TRACK.sharing) renderShare();
}
$('#btn-me').onclick = () => {
  followMe = true;
  if (lastFix) return drawMe(true);
  if (!navigator.geolocation) return toast('Thiết bị không hỗ trợ định vị', 'err');
  navigator.geolocation.getCurrentPosition(onFix, onFixError, { enableHighAccuracy: true, timeout: 15000 });
};

// ---------------------------------------------------------------- Route & stops
async function load() {
  const { body } = await Auth.api('/api/driver/route');
  TRACK = { ...TRACK, ...body.tracking };
  if (TRACK.sharing) { intent.set(true); startWatch(); }
  else if (intent.get()) await resumeSharing();  // shift still open on this phone but the server lost it
  renderShare();
  ROUTE = body.route; REASONS = body.fail_reasons || REASONS;
  if (!ROUTE) {
    $('#d-sum').textContent = ''; $('#d-progress').hidden = true;
    $('#next').innerHTML = `<div class="alert info" style="margin:12px 16px 0">${esc(body.message)}</div>`;
    $('#list').innerHTML = ''; drawRoute(); return;
  }
  const done = ROUTE.stops.filter(s => s.status !== 'pending'), ok = ROUTE.stops.filter(s => s.status === 'delivered').length;
  $('#d-title').textContent = `🚚 Xe ${ROUTE.vehicle_id}`;
  $('#d-sum').textContent = `${done.length}/${ROUTE.stops.length} điểm · ${ROUTE.distance_km} km · xuất phát ${ROUTE.start} từ ${ROUTE.depot.name}`;
  $('#d-progress').hidden = false;
  $('#p-ok').style.width = `${ok / ROUTE.stops.length * 100}%`;
  $('#p-bad').style.width = `${(done.length - ok) / ROUTE.stops.length * 100}%`;
  renderNext(); renderList(); drawRoute();
}

function facts(s) {
  return `<div class="facts">${s.window ? `<span class="badge warn">🕒 ${esc(s.window)}</span>` : ''}<span class="badge">Dự kiến ${esc(s.arrival)}</span>
    <span class="badge">${s.weight_kg} kg</span><span class="badge">dừng ~${s.service_time_min}′</span></div>
    ${s.note ? `<div class="alert warn" style="margin-top:8px">📝 ${esc(s.note)}</div>` : ''}`;
}
function actions(s) {
  return `<div class="acts">
      ${s.phone ? `<a class="btn secondary" href="tel:${esc(s.phone)}">📞 Gọi khách</a>` : '<span></span>'}
      <a class="btn secondary" href="${navUrl(s)}" target="_blank" rel="noopener">🧭 Chỉ đường</a>
      <button class="wide" data-act="delivered" data-id="${esc(s.order_id)}">✅ Đã giao</button>
      <button class="danger wide" data-act="fail-open" data-id="${esc(s.order_id)}" style="min-height:44px;font-size:15px">✖ Không giao được</button>
    </div>
    <div class="fail-box" data-fail="${esc(s.order_id)}" hidden>
      <select data-reason><option value="">— Chọn lý do —</option>${Object.entries(REASONS).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join('')}</select>
      <input data-note placeholder="Ghi chú (không bắt buộc)" maxlength="500">
      <button class="danger lg" data-act="failed" data-id="${esc(s.order_id)}">Xác nhận không giao được</button>
    </div>`;
}
function renderNext() {
  const i = ROUTE.stops.findIndex(s => s.status === 'pending');
  if (i < 0) { $('#next').innerHTML = '<div class="alert ok done-all">🎉 <b>Hoàn thành tuyến!</b> Quay về kho và bấm “Kết thúc ca”.</div>'; return; }
  const s = ROUTE.stops[i];
  $('#next').innerHTML = `<div class="next"><div class="lbl">Điểm tiếp theo · ${i + 1}/${ROUTE.stops.length}</div>
    <h2>${esc(s.customer_name || s.order_id)}</h2><div class="muted" style="font-size:13px">${esc(s.order_id)}${s.phone ? ` · ${esc(s.phone)}` : ''}</div>
    <div class="addr" style="margin-top:6px">📍 ${esc(s.address)}</div>${facts(s)}${actions(s)}</div>`;
}
function renderList() {
  const next = ROUTE.stops.find(s => s.status === 'pending');
  const items = ROUTE.stops.map((s, i) => ({ s, i })).filter(({ s }) => (TAB === 'todo' ? s.status === 'pending' && s !== next : s.status !== 'pending'));
  $('#d-seg').innerHTML = `<button class="${TAB === 'todo' ? 'active' : ''}" data-t="todo">Còn lại (${ROUTE.stops.filter(s => s.status === 'pending').length})</button><button class="${TAB === 'done' ? 'active' : ''}" data-t="done">Đã xử lý (${ROUTE.stops.filter(s => s.status !== 'pending').length})</button>`;
  $('#list').innerHTML = items.length ? items.map(({ s, i }) => `<div class="stop ${s.status}">
      <div class="h"><span class="n">${s.status === 'delivered' ? '✓' : s.status === 'failed' ? '✕' : i + 1}</span><b style="flex:1">${esc(s.customer_name || s.order_id)}</b><span class="badge ${s.status}">${LABEL[s.status]}</span></div>
      <div class="meta">${esc(s.order_id)} · ${esc(s.address)}</div>
      ${s.status === 'pending' ? `<div class="meta">Dự kiến ${esc(s.arrival)}${s.window ? ` · khung ${esc(s.window)}` : ''}</div>`
        : `<div class="meta">Ghi nhận ${esc(s.actual_time || '')}${s.reason_label ? ` · ${esc(s.reason_label)}` : ''} · ${CHECK[s.location_check] || ''}${s.distance_to_stop_m != null ? ` (${s.distance_to_stop_m} m)` : ''}</div>
           <div style="margin-top:8px"><button class="secondary sm" data-act="undo" data-id="${esc(s.order_id)}">↩ Hoàn tác</button></div>`}
    </div>`).join('') : `<div class="empty">${TAB === 'todo' ? 'Không còn điểm nào khác.' : 'Chưa xử lý điểm nào.'}</div>`;
}
$('#d-seg').onclick = e => { const b = e.target.closest('[data-t]'); if (!b || !ROUTE) return; TAB = b.dataset.t; renderList(); };

/** One GPS fix for a delivery report: reuse a fresh tracking fix, otherwise ask once. Never blocks the report. */
function fixForReport() {
  if (lastFix && Date.now() - lastFix.ts < 60000) return Promise.resolve({ location: lastFix });
  return new Promise(resolve => {
    if (!navigator.geolocation) return resolve({ location_error: 'Thiết bị không hỗ trợ định vị' });
    if (!window.isSecureContext) return resolve({ location_error: 'Trang không chạy HTTPS — trình duyệt chặn định vị' });
    navigator.geolocation.getCurrentPosition(
      p => { onFix(p); resolve({ location: lastFix }); },
      err => resolve({ location_error: { 1: 'Tài xế không cho phép định vị', 2: 'Không xác định được vị trí', 3: 'Hết thời gian lấy định vị' }[err.code] || err.message }),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 });
  });
}

document.addEventListener('click', async e => {
  const btn = e.target.closest('[data-act]'); if (!btn) return;
  const act = btn.dataset.act, id = btn.dataset.id;
  if (act === 'fail-open') { document.querySelector(`[data-fail="${CSS.escape(id)}"]`).hidden = false; return; }
  let payload;
  if (act === 'delivered') payload = { status: 'delivered', local_time: nowHHMM() };
  else if (act === 'undo') { if (!confirm('Hoàn tác trạng thái đơn này?')) return; payload = { status: 'pending' }; }
  else if (act === 'failed') {
    const box = document.querySelector(`[data-fail="${CSS.escape(id)}"]`), reason = box.querySelector('[data-reason]').value;
    if (!reason) return toast('Chọn lý do không giao được', 'err');
    payload = { status: 'failed', reason, note: box.querySelector('[data-note]').value, local_time: nowHHMM() };
  } else return;
  const label = btn.innerHTML; btn.disabled = true;
  try {
    if (payload.status !== 'pending') { btn.innerHTML = '📍 Đang xác nhận vị trí…'; Object.assign(payload, await fixForReport()); }
    const { body } = await Auth.api(`/api/driver/stops/${encodeURIComponent(id)}`, { method: 'POST', body: JSON.stringify(payload) });
    if (payload.status === 'delivered') toast(`Đã giao ${id} · ${CHECK[body.location_check] || ''}${body.distance_to_stop_m != null ? ` (${body.distance_to_stop_m} m)` : ''}`, body.location_check === 'far' ? 'err' : 'ok');
    else if (payload.status === 'failed') toast(`Đã ghi nhận không giao được ${id}`);
    await load();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (err) { toast(err.message, 'err'); btn.disabled = false; btn.innerHTML = label; }
});

$('#btn-refresh').onclick = () => load().then(() => toast('Đã cập nhật')).catch(err => toast(err.message, 'err'));
$('#btn-logout').onclick = async () => {
  if (TRACK.sharing && !confirm('Bạn đang trong ca. Thoát sẽ ngừng chia sẻ vị trí. Tiếp tục?')) return;
  if (TRACK.sharing) await setSharing(false).catch(() => {});
  Auth.logout();
};

(async () => {
  const me = await Auth.ensureUser();
  if (me.role !== 'driver') { location.replace('/'); return; }
  ensureMap();
  await load();
  // Pick up re-published plans, but never while the driver is filling in a failure reason.
  setInterval(() => {
    const busyForm = [...document.querySelectorAll('[data-fail]')].some(b => !b.hidden) || document.activeElement?.matches('input,select');
    if (!busyForm) load().catch(() => {});
  }, 60000);
})();
