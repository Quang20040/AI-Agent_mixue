"""Page-switch timing + stylesheet check on the live app (desktop and phone viewport)."""
import json
import sys
import time

from playwright.sync_api import sync_playwright

sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'ui_check']
import qa_live as q  # noqa: E402

PAGES = ['Chốt ca', 'Doanh thu', 'Dự báo', 'Chuẩn bị', 'Đặt hàng', 'Công thức', 'Quản lý nhân viên', 'Trang chủ']


def switch(page, label, frames):
    """Click a menu entry; seconds until the rerun finished, and websocket bytes received meanwhile."""
    frames.clear()
    t = time.time()
    page.evaluate("t => {const l=[...document.querySelectorAll('.st-key-main_navigation label')]"
                  ".find(l => l.textContent.toLowerCase().includes(t.toLowerCase())); if (l) l.click()}", label)
    seen_running = False
    while time.time() - t < 60:
        state = page.evaluate(q.STATE)
        if state in ('running', 'rerunRequested'):
            seen_running = True
        elif seen_running or time.time() - t > 2:
            break
        page.wait_for_timeout(30)
    return round(time.time() - t, 2), sum(frames)


def run(browser, width, height, tag):
    page = q.new_page(browser, width=width, height=height, label=tag)
    frames = []
    page.on('websocket', lambda ws: ws.on('framereceived', lambda payload: frames.append(len(payload))))
    t = time.time()
    q.quick_login(page, 'quick_login_manager')
    out = {'login_s': round(time.time() - t, 2), 'pages': {}}
    for rnd in range(2):
        for label in PAGES:
            seconds, size = switch(page, label, frames)
            q.idle(page, 300)
            out['pages'].setdefault(label, []).append([seconds, round(size / 1024, 1)])
            if rnd == 1 and label in ('Chốt ca', 'Doanh thu', 'Trang chủ'):
                q.shot(page, f'{tag}_{label}')
    out['css_links'] = page.evaluate("[...document.head.querySelectorAll('link[data-mixue-css]')].map(l => [l.href, l.sheet ? l.sheet.cssRules.length : -1])")
    out['inline_brand_css'] = page.evaluate("[...document.querySelectorAll('style')].filter(s => s.textContent.length > 50000).length")
    out['gsap_loaded'] = page.evaluate("!!window.gsap")
    out['animating'] = page.evaluate("document.getAnimations().length")
    out['console_errors'] = [e for e in q.console_errors if e['ctx'] == tag][:10]
    return out


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        res = {'desktop': run(browser, 1440, 900, 'desktop'), 'phone': run(browser, 390, 844, 'phone')}
        browser.close()
    (q.OUT / 'ui_check.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False)[:3000])


if __name__ == '__main__':
    main()
