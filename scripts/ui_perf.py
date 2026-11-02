"""Time page switches in a real browser: desktop, and a phone-like profile (4× slower CPU, 390 px).

python scripts/ui_perf.py out_dir  → out_dir/perf.md
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8631
URL = f'http://localhost:{PORT}'
PAGES = [('tuyết vương ai', 'ai agent'), ('đối soát ocr', 'ocr'), ('báo cáo', 'kho'), ('dự báo', 'dự báo'),
         ('sơ chế', 'sơ chế'), ('nhập hàng', 'nhập hàng'), ('tem ly', 'công thức'), ('trang chủ', 'trang chủ')]
STATE = "() => document.querySelector('[data-testid=\"stApp\"]')?.getAttribute('data-test-script-state')"


def wait_server():
    for _ in range(120):
        try:
            urllib.request.urlopen(URL + '/_stcore/health', timeout=3)
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError('no server')


def settle(page, quiet_for=0.6, limit=60):
    """Seconds until the script is idle and stays idle for quiet_for seconds (excluded from the result)."""
    start, quiet, last_busy = time.time(), 0.0, time.time()
    while time.time() - start < limit and quiet < quiet_for:
        page.wait_for_timeout(100)
        if page.evaluate(STATE) in ('running', 'rerunRequested'):
            quiet, last_busy = 0.0, time.time()
        else:
            quiet += 0.1
    return last_busy - start


def run(browser, phone):
    ctx = browser.new_context(viewport={'width': 390 if phone else 1440, 'height': 860}, is_mobile=phone, has_touch=phone)
    page = ctx.new_page()
    if phone:
        ctx.new_cdp_session(page).send('Emulation.setCPUThrottlingRate', {'rate': 4})
    t = time.time()
    page.goto(URL)
    settle(page)
    first = time.time() - t
    page.get_by_text('Tài khoản dùng thử').first.click()
    page.wait_for_timeout(500)
    page.locator('.st-key-quick_login_manager button').first.click()
    login = settle(page)
    rows = [('mở trang đăng nhập', first), ('đăng nhập', login)]
    for desktop_name, phone_name in PAGES:
        target = '.st-key-mobile_dock label' if phone else '.st-key-main_navigation label'
        name = phone_name if phone else desktop_name
        t = time.time()
        found = page.evaluate("([sel, t]) => [...document.querySelectorAll(sel)].find(l => l.textContent.toLowerCase().includes(t))?.click() === undefined",
                      [target, name])
        settle(page)
        rows.append((desktop_name, (time.time() - t - 0.6) if found else float('nan')))
    ctx.close()
    return rows


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONPATH': str(ROOT), 'APP_DEMO_MODE': 'true'}
    server = subprocess.Popen([sys.executable, 'scripts/serve.py', '--server.headless', 'true', '--server.port', str(PORT),
                               '--browser.gatherUsageStats', 'false'], cwd=ROOT, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        wait_server()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            desktop, phone = run(browser, False), run(browser, True)
            browser.close()
    finally:
        server.terminate()
        log = server.communicate(timeout=20)[0]
    lines = ['| Bước | Máy tính (giây) | Điện thoại giả lập, CPU ×4 (giây) |', '|---|---|---|']
    lines += [f'| {a} | {da:.2f} | {pb:.2f} |' for (a, da), (_, pb) in zip(desktop, phone)]
    timing = [line for line in log.splitlines() if '[timing]' in line]
    (out / 'perf.md').write_text('# Thời gian chuyển trang\n\n' + '\n'.join(lines) + '\n\n## Server log [timing]\n\n'
                                 + ('\n'.join(timing) or '(không có lượt chạy nào quá 700 ms)') + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'ui_perf')
