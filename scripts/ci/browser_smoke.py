"""CI: the Streamlit UI (websocket) and the web frontend both work on the one ASGI server."""
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip('/')
errors = []
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(BASE + '/', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_selector('[data-testid="stApp"]', timeout=90000)
    page.wait_for_selector('[data-testid="stTextInput"], input[type="password"]', timeout=90000)  # login form rendered over the websocket
    print('streamlit login page ok')
    page.goto(BASE + '/ui/', wait_until='domcontentloaded')
    page.fill('input[name=u]', 'quanly')
    page.fill('input[name=p]', '123')
    page.click('button[type=submit]')
    page.wait_for_selector('.side .nav', timeout=30000)
    page.goto(BASE + '/ui/#/chat')
    page.wait_for_selector('#q')
    page.fill('#q', 'công thức trà sữa trân châu')
    page.click('#send')
    t = time.time()
    page.wait_for_selector('details.trace', timeout=60000)
    steps = page.locator('details.trace li').count()
    print(f'chat answered in {time.time() - t:.1f}s with {steps} trace steps')
    assert steps >= 2, steps
    page.goto(BASE + '/ui/#/sop')
    page.fill('input[name=q]', 'trân châu luộc mấy phút')
    page.click('#sf button')
    page.wait_for_selector('#hits .card b', timeout=30000)
    print('sop search ok')
    browser.close()
if errors:
    sys.exit(f'page errors: {errors[:3]}')
