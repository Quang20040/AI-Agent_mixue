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
    # Remembered login: quick login, then a reload (new websocket session) is still signed in; token not in the URL.
    page.locator('[data-testid="stExpander"] summary').filter(has_text='Tài khoản dùng thử').first.click()
    page.locator('.st-key-quick_login_manager button').click()
    page.wait_for_selector('.st-key-main_navigation', timeout=90000)
    assert 's=' not in page.url, page.url
    assert any(c['name'] == 'mixue_session' for c in page.context.cookies()), 'no session cookie'
    page.reload(wait_until='domcontentloaded')
    page.wait_for_selector('.st-key-main_navigation', timeout=90000)
    print('remembered login survives a reload')
    # Admin-only AI engineering dashboard renders every tab (screenshots kept as CI artifacts).
    import os
    shots = os.environ.get('SMOKE_SHOTS')
    if shots:
        os.makedirs(shots, exist_ok=True)
    page.set_viewport_size({'width': 1440, 'height': 1500})
    nav = page.locator('[data-testid="stSidebar"] .st-key-main_navigation')
    try:
        nav.get_by_text('Kỹ thuật AI', exact=True).first.click(timeout=15000)
    except Exception:
        print('navigation options:', nav.inner_text()[:600])
        page.screenshot(path='smoke-shots/nav_fail.png' if shots else '/tmp/nav_fail.png', full_page=True)
        raise
    page.wait_for_selector('text=Guardrail chặn', timeout=60000)
    page.wait_for_selector('text=Chặn đúng câu tấn công', timeout=60000)
    for i, tab in enumerate(['Guardrail', 'Tool calling', 'Human-in-the-loop', 'RAG', 'Vision OCR', 'Tracing', 'Benchmark', 'Bộ nhớ']):
        page.locator('[role=tab]').filter(has_text=tab).first.click()
        page.wait_for_timeout(1200)
        if shots:
            os.makedirs(shots, exist_ok=True)
            page.screenshot(path=f'{shots}/ai_tech_{i}.png', full_page=True)
            if os.environ.get('SMOKE_SHOTS_LOG'):
                import base64
                data = page.screenshot(type='jpeg', quality=55, full_page=True)
                print(f'SHOT{i}:' + base64.b64encode(data).decode())
    assert not page.locator('[data-testid="stException"]').count(), 'exception on the AI page'
    print('AI engineering dashboard ok')
    # Weekly schedule: the AI drafts next week, the manager sees the editable draft.
    nav.get_by_text('Lịch làm tuần', exact=True).first.click(timeout=15000)
    page.locator('.st-key-sched_generate button').click(timeout=30000)
    page.wait_for_selector('.st-key-sched_draft', timeout=60000)
    assert not page.locator('[data-testid="stException"]').count(), 'exception on the schedule page'
    if shots:
        page.screenshot(path=f'{shots}/schedule.png', full_page=True)
        if os.environ.get('SMOKE_SHOTS_LOG'):
            import base64
            print('SHOT9:' + base64.b64encode(page.screenshot(type='jpeg', quality=55, full_page=True)).decode())
    print('schedule draft ok')
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
    try:
        page.wait_for_selector('details.trace', timeout=60000)
    except Exception:
        print('last bubble:', page.locator('.msg.bot .bubble').last.inner_text()[:500])
        raise
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
