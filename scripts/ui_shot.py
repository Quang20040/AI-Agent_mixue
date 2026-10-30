"""Screenshot helper: python scripts/ui_shot.py <nav_index 0-based> <out.png> [username] [password]"""
import sys
from playwright.sync_api import sync_playwright

nav_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
out = sys.argv[2] if len(sys.argv) > 2 else "output/ui_home.png"
user = sys.argv[3] if len(sys.argv) > 3 else "chucuahang"
pwd = sys.argv[4] if len(sys.argv) > 4 else "123"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto("http://localhost:8599")
    pg.wait_for_selector("input[type=password]", timeout=30000)
    pg.locator("input[type=text]").first.fill(user)
    pg.locator("input[type=password]").first.fill(pwd)
    pg.keyboard.press("Enter")
    pg.wait_for_selector("[data-testid=stSidebar] [role=radiogroup]", timeout=30000)
    pg.wait_for_timeout(2500)
    if nav_index:
        pg.locator("[data-testid=stSidebar] [data-testid=stRadioOption]").nth(nav_index).click()
        pg.wait_for_timeout(4000)
    pg.screenshot(path=out, full_page=False)
    b.close()
