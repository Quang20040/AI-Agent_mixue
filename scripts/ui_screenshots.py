"""Chụp ảnh giao diện thật (Streamlit + Chromium) để so với thiết kế canvas.

Dùng trong workflow `ui-screenshots.yml`; chạy tay: `python scripts/ui_screenshots.py out_dir`.
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8599
PAGES = [('home', None), ('ocr', '📸 Chốt ca & OCR'), ('chat', '💬 Tuyết Vương AI')]


def wait_server(url, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url + '/_stcore/health', timeout=3)
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError('Streamlit did not start')


def settle(page, ms=2500):
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(ms)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONPATH': str(ROOT)}
    server = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'src/dashboard/app.py', '--server.headless', 'true',
                               '--server.port', str(PORT), '--browser.gatherUsageStats', 'false'], cwd=ROOT, env=env)
    try:
        url = f'http://localhost:{PORT}'
        wait_server(url)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width, suffix in ((1440, ''), (390, '_mobile')):
                page = browser.new_page(viewport={'width': width, 'height': 900}, device_scale_factor=1)
                page.goto(url)
                settle(page, 4000)
                page.screenshot(path=str(out / f'login{suffix}.png'), full_page=True)
                page.get_by_role('button', name='Quản Lý (Admin)').first.click()
                settle(page, 5000)
                for name, nav in PAGES:
                    if nav:
                        target = page.locator('.st-key-main_navigation label', has_text=nav.split(' ', 1)[1]).first
                        if width < 600 or not target.is_visible():
                            page.goto(url)  # mobile: navigation lives behind the collapsed sidebar
                            settle(page, 3000)
                            page.evaluate("t => [...document.querySelectorAll('.st-key-main_navigation label')].find(l => l.textContent.includes(t))?.click()",
                                          nav.split(' ', 1)[1])
                        else:
                            target.click()
                        settle(page, 5000)
                    page.screenshot(path=str(out / f'{name}{suffix}.png'), full_page=True)
                page.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'ui_screenshots')
