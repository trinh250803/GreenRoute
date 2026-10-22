"""Login and change-password screenshots cropped to the form.

    python docs/guide/capture_login_crops.py . docs/guide/capture_screenshots.py
"""
import re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(sys.argv[1]); OUT = ROOT / "docs" / "guide" / "img"
PW = dict(re.findall(r"^\|[^|]*\| `([^`]+)` \| `([^`]+)` \|", (ROOT / "TEST_ACCOUNTS.md").read_text(encoding="utf-8"), re.M))
MARK = open(sys.argv[2], encoding="utf-8").read().split('MARK_JS = """')[1].split('"""')[0]
def boxshot(pg, sel, name, marks, pad=40):
    pg.evaluate(MARK, [list(m) for m in marks]); pg.wait_for_timeout(200)
    b = pg.locator(sel).bounding_box()
    pg.screenshot(path=OUT / f"{name}.png", clip={"x": max(0, b["x"] - pad), "y": max(0, b["y"] - pad), "width": b["width"] + 2 * pad, "height": b["height"] + 2 * pad})
    pg.evaluate("document.querySelectorAll('.gm').forEach(e => e.remove())")
with sync_playwright() as p:
    br = p.chromium.launch(); pg = br.new_page(viewport={"width": 1366, "height": 820}, device_scale_factor=2)
    pg.goto("http://127.0.0.1:8000/"); pg.wait_for_selector("#login-form")
    boxshot(pg, "#login-form", "01_login", [("#login-form [name=username]", 1), ("#login-form [name=password]", 2), ("#login-form button", 3)])
    pg.fill("#login-form [name=username]", "admin"); pg.fill("#login-form [name=password]", PW["admin"]); pg.click("#login-form button")
    pg.wait_for_selector("#btn-pw"); pg.click("#btn-pw"); pg.wait_for_timeout(400)
    boxshot(pg, "#pw-form", "03_change_pw", [("#pw-form [name=old_password]", 1), ("#pw-form [name=new_password]", 2), ("#pw-form [name=confirm]", 3), ("#pw-form button", 4)])
    br.close()
print("ok")
