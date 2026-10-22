'use strict';
/* Shared login/session helper for the staff app (index.html) and the driver app (driver.html). */
const Auth = (() => {
  const KEY = 'greenroute_token';
  let token = null;
  try { token = localStorage.getItem(KEY); } catch { /* storage blocked: session lasts until reload */ }
  const setToken = t => { token = t; try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch { /* ignore */ } };
  const el = id => document.getElementById(id);

  async function api(url, opts = {}) {
    const headers = { ...(opts.headers || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (opts.body && !(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    const res = await fetch(url, { ...opts, headers });
    const body = res.status === 204 ? null : await res.json().catch(() => null);
    if (res.status === 401) { setToken(null); location.reload(); throw new Error('Phiên đăng nhập hết hạn'); }
    if (!res.ok && res.status !== 422) throw new Error(body?.error || `HTTP ${res.status}`);
    return { status: res.status, body };
  }

  async function download(url) {
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`Tải file lỗi (HTTP ${res.status})`);
    const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '')?.[1] || 'greenroute-report';
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(await res.blob()), download: name });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function showForm(which) {
    el('login-screen').hidden = false;
    el('login-form').hidden = which !== 'login';
    el('pw-form').hidden = which !== 'pw';
  }

  function loginOnce() {
    showForm('login');
    return new Promise(resolve => {
      el('login-form').onsubmit = async e => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target));
        const res = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) { el('login-error').hidden = false; el('login-error').textContent = body.error || 'Đăng nhập lỗi'; return; }
        el('login-error').hidden = true; e.target.reset();
        setToken(body.token); resolve();
      };
    });
  }

  function changePasswordOnce(cancellable = false) {
    showForm('pw');
    return new Promise(resolve => {
      const f = el('pw-form');
      if (cancellable && !f.querySelector('.cancel')) {
        const c = Object.assign(document.createElement('button'), { type: 'button', className: 'secondary cancel', textContent: 'Hủy' });
        c.onclick = () => { el('login-screen').hidden = true; resolve(false); };
        f.insertBefore(c, el('pw-error'));
      }
      f.onsubmit = async e => {
        e.preventDefault();
        const d = Object.fromEntries(new FormData(e.target));
        const err = m => { el('pw-error').hidden = false; el('pw-error').textContent = m; };
        if (d.new_password !== d.confirm) return err('Mật khẩu nhập lại không khớp');
        const res = await fetch('/api/auth/change-password', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ old_password: d.old_password, new_password: d.new_password }) });
        const out = await res.json().catch(() => ({}));
        if (!res.ok) return err(out.error || 'Đổi mật khẩu lỗi');
        if (out.token) setToken(out.token);  // server signs out other devices and hands back a fresh token
        el('pw-error').hidden = true; e.target.reset(); el('login-screen').hidden = true; resolve(true);
      };
    });
  }

  /** Resolves with the logged-in user once they are authenticated and their password is final. */
  async function ensureUser() {
    for (;;) {
      if (token) {
        const res = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } });
        if (res.ok) {
          const u = await res.json();
          if (!u.must_change_password) { el('login-screen').hidden = true; return u; }
          await changePasswordOnce();
          continue;
        }
        setToken(null);
      }
      await loginOnce();
    }
  }

  async function logout() {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch { /* already gone */ }
    setToken(null); location.reload();
  }

  // Environment banner text comes from the server (ENV_BANNER); empty in production.
  fetch('/api/health').then(r => r.json()).then(h => {
    const b = el('env-banner'); if (!b) return;
    if (h.env_banner) { b.textContent = `⚠ ${h.env_banner}`; b.hidden = false; }
    else { b.hidden = true; document.documentElement.style.setProperty('--envbar', '0px'); }
  }).catch(() => {});

  return { api, download, ensureUser, logout, changePassword: () => changePasswordOnce(true) };
})();
