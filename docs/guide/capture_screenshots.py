"""Screenshots for the role guide, with numbered red markers on the controls the text refers to.

Needs the local server on :8000 and TEST_ACCOUNTS.md. Reloads the HCM sample data, runs and
publishes a plan and plays one driver shift. Then run capture_login_crops.py, build_guide.py, to_docx.ps1.

    python docs/guide/capture_screenshots.py .
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(sys.argv[1])
BASE = "http://127.0.0.1:8000"
OUT = ROOT / "docs" / "guide" / "img"
OUT.mkdir(parents=True, exist_ok=True)
rows = re.findall(r"^\|[^|]*\| `([^`]+)` \| `([^`]+)` \|[^|]*\|([^|]*)\|", (ROOT / "TEST_ACCOUNTS.md").read_text(encoding="utf-8"), re.M)
PW = {u: p for u, p, _ in rows}
DRIVER_OF = {v.strip(): u for u, _, v in rows if v.strip()}
errors = []

MARK_JS = """items => {
  document.querySelectorAll('.gm').forEach(e => e.remove());
  for (const [sel, n] of items) {
    const el = document.querySelector(sel); if (!el) continue;
    const r = el.getBoundingClientRect(); if (!r.width && !r.height) continue;
    const box = document.createElement('div'); box.className = 'gm';
    Object.assign(box.style, {position:'fixed', left:(r.left-4)+'px', top:(r.top-4)+'px', width:(r.width+8)+'px', height:(r.height+8)+'px',
      border:'3px solid #e11d48', borderRadius:'8px', zIndex:99999, pointerEvents:'none'});
    const b = document.createElement('div'); b.className = 'gm'; b.textContent = n;
    Object.assign(b.style, {position:'fixed', left:Math.max(2, r.left-15)+'px', top:Math.max(2, r.top-15)+'px', width:'26px', height:'26px',
      borderRadius:'50%', background:'#e11d48', color:'#fff', font:'700 14px/26px Arial,sans-serif', textAlign:'center',
      zIndex:100000, pointerEvents:'none', boxShadow:'0 0 0 2px #fff'});
    document.body.append(box, b);
  }
}"""


RETRY_TILES = """() => { let bad = 0; document.querySelectorAll('img.leaflet-tile').forEach(img => {
  if (!img.classList.contains('leaflet-tile-loaded')) { bad++; img.src = img.src.split('#')[0] + '#r' + Math.random(); } }); return bad; }"""


def ensure_tiles(page, tries=10):
    """The tile server resets some connections from this machine; re-request failed tiles."""
    for _ in range(tries):
        page.wait_for_timeout(1500)
        if not page.evaluate(RETRY_TILES):
            return


def shot(page, name, marks=(), scroll=None, wait=400):
    if scroll:
        page.locator(scroll).first.scroll_into_view_if_needed()
    page.wait_for_timeout(wait)
    ensure_tiles(page)
    page.evaluate(MARK_JS, [list(m) for m in marks])
    page.screenshot(path=OUT / f"{name}.png")
    page.evaluate("document.querySelectorAll('.gm').forEach(e => e.remove())")
    print("shot", name)


def watch(page, tag):
    page.on("pageerror", lambda e: errors.append(f"[{tag}] {e}"))
    page.on("dialog", lambda d: d.accept())


def login(page, user):
    page.wait_for_selector("#login-form [name=username]")
    page.fill("#login-form [name=username]", user)
    page.fill("#login-form [name=password]", PW[user])
    page.click("#login-form button")


def go(page, pid, wait=900):
    page.click(f"#menu [data-page={pid}]")
    page.wait_for_timeout(wait)


with sync_playwright() as p:
    br = p.chromium.launch()
    desk = dict(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36", viewport={"width": 1366, "height": 820}, locale="vi-VN")

    # ---------------- Admin ----------------
    ctx = br.new_context(**desk); pg = ctx.new_page(); watch(pg, "admin")
    pg.goto(BASE + "/")
    pg.wait_for_selector("#login-form")
    0 and shot(pg, "01_login", [("#login-form [name=username]", 1), ("#login-form [name=password]", 2), ("#login-form button", 3)])
    login(pg, "admin")
    pg.wait_for_selector("#menu [data-page=admin]")
    go(pg, "admin")
    pg.click("#admin-seg [data-sub=data]")
    pg.select_option("#dataset", "hcm")
    shot(pg, "13_admin_data", [("#dataset", 1), ("#btn-sample", 2)])
    pg.click("#btn-sample"); pg.wait_for_timeout(1500)
    go(pg, "overview", 1500)
    shot(pg, "02_layout", [("#env-banner", 1), ("#menu", 2), (".lang-switch", 3), ("#btn-pw", 4), ("#btn-logout", 5)])
    pg.click("#btn-pw"); pg.wait_for_timeout(400)
    0 and shot(pg, "03_change_pw", [("#pw-form [name=old_password]", 1), ("#pw-form [name=new_password]", 2), ("#pw-form [name=confirm]", 3), ("#pw-form button", 4)])
    pg.reload(); pg.wait_for_selector("#menu [data-page=admin]")
    go(pg, "admin")
    pg.click("#admin-seg [data-sub=users]"); pg.wait_for_timeout(500)
    shot(pg, "10_admin_users", [("#user-form", 1), ("#users", 2)])
    pg.fill("#user-form [name=username]", "taixe13")
    pg.fill("#user-form [name=full_name]", "Nguyễn Văn Mới")
    pg.select_option("#uf-role", "driver"); pg.wait_for_timeout(300)
    shot(pg, "11_admin_user_form", [("#user-form [name=username]", 1), ("#uf-role", 2), ("#uf-vehicle", 3), ("#user-form [name=password]", 4), ("#user-form button", 5)])
    pg.reload(); pg.wait_for_selector("#menu [data-page=admin]")
    go(pg, "admin")
    pg.click("#admin-seg [data-sub=config]"); pg.wait_for_timeout(600)
    shot(pg, "12_admin_config", [("#config-editor", 1), ("#cfg-reason", 2), ("#btn-cfg-save", 3)])
    shot(pg, "12b_admin_config_save", [("#cfg-reason", 2), ("#btn-cfg-save", 3)], scroll="#btn-cfg-save")
    pg.click("#admin-seg [data-sub=audit]"); pg.wait_for_timeout(600)
    shot(pg, "14_admin_audit", [("#audit", 1)])
    ctx.close()

    # ---------------- Fleet manager ----------------
    ctx = br.new_context(**desk); pg = ctx.new_page(); watch(pg, "fleet")
    pg.goto(BASE + "/"); login(pg, "doixe01")
    pg.wait_for_selector("#vehicles-table table"); pg.wait_for_timeout(600)
    shot(pg, "20_vehicles", [("#vehicles-file", 1), ("#vehicles-mode", 2), ("#btn-vehicles-import", 3), ("#page-vehicles details summary", 4), ("#vehicles-table table", 5)])
    pg.click("#page-vehicles details summary"); pg.wait_for_timeout(300)
    shot(pg, "21_vehicle_form", [("#vehicle-form [name=vehicle_id]", 1), ("#vf-type", 2), ("#vf-fuel", 3), ("#vehicle-form [name=cost_per_km]", 4),
                                 ("#vehicle-form [name=consumption_rate]", 5), ("#vehicle-form [name=available]", 6), ("#vehicle-form button", 7)], scroll="#vehicle-form")
    pg.click("#page-vehicles details summary")
    pg.locator("#vehicles-table a[data-vehicle]").first.click()
    pg.wait_for_selector("#drawer:not([hidden]) .dsec"); pg.wait_for_timeout(1200)
    shot(pg, "22_vehicle_drawer", [("#drawer", 1)])
    ctx.close()

    # ---------------- Dispatcher ----------------
    ctx = br.new_context(**desk); pg = ctx.new_page(); watch(pg, "dispatcher")
    pg.goto(BASE + "/"); login(pg, "dieuphoi01")
    pg.wait_for_selector("#menu [data-page=orders]")
    go(pg, "orders")
    shot(pg, "30_orders", [("#orders-search", 1), ("#orders-file", 2), ("#orders-mode", 3), ("#btn-orders-import", 4), ("#order-add summary", 5),
                           ("#orders-table [data-edit-order]", 6), ("#orders-table a.oid", 7)])
    pg.click("#order-add summary"); pg.wait_for_timeout(800)
    pg.fill("#of-address", "118 Bạch Đằng Bình Thạnh")
    pg.wait_for_selector("#addr-list li[data-i]", timeout=20000)
    shot(pg, "31_order_address", [("#of-address", 1), ("#addr-list", 2)], scroll="#order-add")
    pg.click("#addr-list li[data-i]"); pg.wait_for_timeout(2500)
    pg.fill("#order-form [name=customer_name]", "Khách mẫu"); pg.fill("#order-form [name=weight_kg]", "2.5")
    shot(pg, "32_order_form", [("#of-id", 1), ("#of-lat", 2), ("#of-ws", 3), ("#of-svc", 4), ("#order-map", 5), ("#of-submit", 6)], scroll="#order-add", wait=1200)
    pg.click("#of-reset")
    pg.locator("#orders-table [data-edit-order]").first.click(); pg.wait_for_timeout(1500)
    shot(pg, "33_order_edit", [("#order-add-title", 1), ("#of-id", 2), ("#of-submit", 3)], scroll="#order-add")
    pg.click("#of-reset")
    pg.locator("#orders-table a.oid").first.click()
    pg.wait_for_selector("#drawer:not([hidden]) .dsec"); pg.wait_for_timeout(1500)
    shot(pg, "34_order_drawer", [("#drawer", 1)])
    pg.keyboard.press("Escape")

    go(pg, "plan")
    pg.fill("#time-limit", "5")
    pg.evaluate("window.scrollTo(0, 0)"); pg.wait_for_timeout(300)
    shot(pg, "35_plan_setup", [("#depot-name", 1), ("#btn-depot-pick", 2), ("#btn-depot", 3), ("#time-limit", 4), ("#btn-run", 5)])
    pg.click("#btn-run")
    pg.wait_for_timeout(500)
    pg.wait_for_function("() => !document.querySelector('#btn-run').disabled && !/đang tính/i.test(document.querySelector('#btn-run').textContent)", timeout=90000)
    pg.wait_for_timeout(3500)
    shot(pg, "36_plan_result", [("#kpis", 1), ("#map", 2), ("#plan-seg", 3), ("#btn-publish", 4)])
    pg.locator("#plan-v-routes details summary").first.click(); pg.wait_for_timeout(300)
    shot(pg, "36b_plan_route", [("#plan-v-routes .item", 1)], scroll="#plan-v-routes .item")
    pg.click("#plan-seg [data-v=compare]"); pg.wait_for_timeout(500)
    shot(pg, "37_plan_compare", [("#plan-v-compare", 1)], scroll="#plan-seg")
    pg.click("#plan-seg [data-v=unassigned]"); pg.wait_for_timeout(500)
    shot(pg, "38_plan_unassigned", [("#plan-v-unassigned", 1)], scroll="#plan-seg")
    pg.evaluate("window.scrollTo(0,0)")
    pg.click("#btn-publish"); pg.wait_for_timeout(1500)
    shot(pg, "39_published", [("#btn-publish", 1), ("#publish-msg", 2)])
    routes = pg.eval_on_selector_all("#plan-v-routes .id", "els => els.map(e => e.textContent)")

    # ---------------- Driver (phone) ----------------
    vid = next(v for v in routes if v in DRIVER_OF and v.startswith("MOTO")) if any(v.startswith("MOTO") and v in DRIVER_OF for v in routes) else next(v for v in routes if v in DRIVER_OF)
    start = {"latitude": 10.80316, "longitude": 106.70768, "accuracy": 12}
    dctx = br.new_context(user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36", viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="vi-VN",
                          permissions=["geolocation"], geolocation=start)
    d = dctx.new_page(); watch(d, "driver")
    d.goto(BASE + "/driver.html")
    d.wait_for_selector("#login-form")
    shot(d, "50_driver_login", [("#login-form [name=username]", 1), ("#login-form [name=password]", 2), ("#login-form button", 3)])
    login(d, DRIVER_OF[vid])
    d.wait_for_selector("#next > *"); d.wait_for_timeout(1000)
    if "Kết thúc" in d.inner_text("#btn-share"):  # shift left open by an earlier run
        d.click("#btn-share"); d.wait_for_timeout(1500)
    d.wait_for_timeout(1000)
    shot(d, "51_driver_start", [("#btn-share", 1), ("#d-map", 2)])
    d.click("#btn-share"); d.wait_for_timeout(1500)
    first = d.evaluate("ROUTE.stops[0]")
    for k in range(1, 5):
        dctx.set_geolocation({"latitude": start["latitude"] + (first["latitude"] - start["latitude"]) * k / 4,
                              "longitude": start["longitude"] + (first["longitude"] - start["longitude"]) * k / 4, "accuracy": 10})
        d.wait_for_timeout(5500)
    d.evaluate("flush()"); d.wait_for_timeout(1500)
    shot(d, "52_driver_sharing", [(".share", 1), ("#d-map", 2), ("#btn-me", 3)])
    shot(d, "53_driver_next", [("#next a[href^='tel']", 1), ("#next a[href*='google']", 2), ("#next [data-act=delivered]", 3), ("#next [data-act=fail-open]", 4)], scroll="#next")
    d.click("#next [data-act=delivered]"); d.wait_for_timeout(2500)
    d.click("#next [data-act=fail-open]"); d.wait_for_timeout(500)
    d.select_option("#next [data-reason]", "customer_absent")
    shot(d, "54_driver_fail", [("#next [data-reason]", 1), ("#next [data-act=failed]", 2)], scroll="#next [data-act=failed]")
    d.click("#next [data-act=failed]"); d.wait_for_timeout(2000)
    d.click("#d-seg [data-t=done]"); d.wait_for_timeout(600)
    shot(d, "55_driver_done", [("#d-seg", 1), ("#list [data-act=undo]", 2)], scroll="#d-seg")

    go(pg, "live", 3500)
    shot(pg, "40_live", [("#live-map", 1), ("#live-counts", 2), ("#live-list", 3)])
    ctx.close(); dctx.close()

    # ---------------- Ops manager ----------------
    ctx = br.new_context(**desk); pg = ctx.new_page(); watch(pg, "ops")
    pg.goto(BASE + "/"); login(pg, "vanhanh01")
    pg.wait_for_selector("#ov-steps > *"); pg.wait_for_timeout(1500)
    shot(pg, "60_overview", [("#ov-steps", 1), ("#ov-kpis", 2), ("#ov-progress", 3), ("#ov-alerts", 4)])
    pg.wait_for_selector("#ch-cost", timeout=20000)
    pg.evaluate("document.querySelector('#ov-analytics').scrollIntoView({block: 'start'})"); pg.wait_for_timeout(2500)
    shot(pg, "61_analytics", [])
    go(pg, "fuel", 1200)
    vid_used = pg.eval_on_selector_all("#fuel-editor tr[data-vid]", "trs => trs.find(t => !t.querySelector('.badge') && /E5/.test(t.cells[1].textContent))?.dataset.vid")
    row = f"#fuel-editor tr[data-vid='{vid_used}']"
    pg.locator(f"{row} [data-k=fuel_blend_code]").first.select_option("E10")
    shot(pg, "62_fuel", [(f"{row} [data-k=fuel_blend_code]", 1), (f"{row} [data-k=consumption_rate]", 2), ("#sc-mode", 3), ("#btn-scenario", 4)])
    pg.click("#btn-scenario"); pg.wait_for_selector("#scenario-result .card", timeout=60000); pg.wait_for_timeout(600)
    shot(pg, "63_fuel_result", [("#scenario-result .card", 1)], scroll="#scenario-result")
    go(pg, "history", 1200)
    shot(pg, "64_history", [("#history", 1)])
    go(pg, "method", 800)
    shot(pg, "66_method", [])
    go(pg, "overview", 1200)
    pg.click("#ai-fab"); pg.wait_for_timeout(800)
    shot(pg, "65_ai", [("#ai-msgs [data-ask]", 1), ("#ai-input", 2)])
    pg.click("#ai-close")
    pg.click(".lang-switch [data-lang=en]"); pg.wait_for_timeout(1500)
    shot(pg, "67_lang_en", [(".lang-switch", 1)])
    pg.click(".lang-switch [data-lang=vi]")
    ctx.close()
    br.close()

print("ERRORS:", errors)
