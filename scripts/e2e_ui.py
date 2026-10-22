"""UI walkthrough with screenshots: admin → dispatcher → driver (simulated GPS) → live map."""
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "e2e-shots"


def accounts() -> dict:
    """Credentials come from the git-ignored TEST_ACCOUNTS.md table, never from this file."""
    rows = re.findall(r"^\|[^|]*\| `([^`]+)` \| `([^`]+)` \|[^|]*\|([^|]*)\|", (ROOT / "TEST_ACCOUNTS.md").read_text(encoding="utf-8"), re.M)
    return {u: (pw, v.strip()) for u, pw, v in rows}


ACC = accounts()
PW = {u: pw for u, (pw, _) in ACC.items()}
DRIVER_OF = {v: u for u, (_, v) in ACC.items() if v}
OUT.mkdir(exist_ok=True)
errors = []


def watch(page, tag):
    page.on("console", lambda m: m.type == "error" and errors.append(f"[{tag}] console: {m.text}"))
    page.on("pageerror", lambda e: errors.append(f"[{tag}] pageerror: {e}"))
    page.on("dialog", lambda d: d.accept())


def login(page, user, pw):
    page.fill("#login-form [name=username]", user)
    page.fill("#login-form [name=password]", pw)
    page.click("#login-form button")


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ---- Admin: load HCM dataset ----
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="vi-VN")
    page = ctx.new_page(); watch(page, "admin")
    page.goto(BASE + "/")
    login(page, "admin", PW["admin"])
    page.wait_for_selector("#menu [data-page=admin]")
    page.click("#menu [data-page=admin]")
    page.click("#admin-seg [data-sub=data]")
    page.select_option("#dataset", "hcm")
    page.click("#btn-sample")
    page.wait_for_timeout(1500)
    page.click("#menu [data-page=overview]")
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT / "1_overview_admin.png", full_page=True)
    ctx.close()

    # ---- Dispatcher: optimise + publish ----
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="vi-VN")
    page = ctx.new_page(); watch(page, "dispatcher")
    page.goto(BASE + "/")
    login(page, "dieuphoi01", PW["dieuphoi01"])
    page.wait_for_selector("#menu [data-page=plan]")
    page.click("#menu [data-page=plan]")
    page.fill("#time-limit", "5")
    page.click("#btn-run")
    page.wait_for_selector("#plan-body:not([hidden])", timeout=60000)
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT / "2_plan.png", full_page=True)
    page.click("#plan-seg [data-v=compare]")
    page.wait_for_timeout(300)
    page.locator("#plan-v-compare").screenshot(path=OUT / "2b_compare.png")
    page.click("#btn-publish")
    page.wait_for_timeout(1500)
    routes = page.eval_on_selector_all("#plan-v-routes .id", "els => els.map(e => e.textContent)")
    print("routes:", routes)
    page.click("#menu [data-page=orders]")
    page.wait_for_timeout(800)
    page.screenshot(path=OUT / "3_orders.png")

    # ---- Driver (phone): start shift, move, deliver ----
    vid = next(v for v in routes if v in DRIVER_OF)
    print("driver vehicle:", vid)
    dctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                               locale="vi-VN", permissions=["geolocation"], geolocation={"latitude": 10.8015, "longitude": 106.6527, "accuracy": 15})
    d = dctx.new_page(); watch(d, "driver")
    d.goto(BASE + "/driver.html")
    login(d, DRIVER_OF[vid], PW[DRIVER_OF[vid]])
    d.wait_for_selector("#next > *")
    d.wait_for_timeout(1200)
    d.screenshot(path=OUT / "4_driver_start.png")
    d.click("#btn-share")
    d.wait_for_timeout(1500)
    # Simulate driving toward the first stop.
    first = d.evaluate("ROUTE.stops[0]")
    for k in range(1, 6):
        lat = 10.8015 + (first["latitude"] - 10.8015) * k / 5
        lng = 106.6527 + (first["longitude"] - 106.6527) * k / 5
        dctx.set_geolocation({"latitude": lat, "longitude": lng, "accuracy": 12})
        d.wait_for_timeout(5500)
    d.evaluate("flush()")
    d.wait_for_timeout(1000)
    d.screenshot(path=OUT / "5_driver_moving.png")
    d.click(".next [data-act=delivered]")
    d.wait_for_timeout(2500)
    d.screenshot(path=OUT / "6_driver_after_delivery.png")
    second = d.evaluate("ROUTE.stops.find(s => s.status === 'pending')")
    if second:
        d.click(".next [data-act=fail-open]")
        d.select_option(".next [data-reason]", "customer_absent")
        d.click(".next [data-act=failed]")
        d.wait_for_timeout(2000)

    # ---- Dispatcher: live map ----
    page.click("#menu [data-page=live]")
    page.wait_for_timeout(3000)
    page.screenshot(path=OUT / "7_live.png", full_page=True)
    page.click("#menu [data-page=overview]")
    page.wait_for_timeout(2000)
    page.screenshot(path=OUT / "8_overview_dispatcher.png", full_page=True)

    # ---- Mobile staff layout ----
    m = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, locale="vi-VN").new_page(); watch(m, "mobile-staff")
    m.goto(BASE + "/")
    login(m, "vanhanh01", PW["vanhanh01"])
    m.wait_for_timeout(2500)
    m.screenshot(path=OUT / "9_mobile_ops.png")
    browser.close()

print("ERRORS:" if errors else "no console errors")
for e in errors:
    print(" ", e)
