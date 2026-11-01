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
PAGES = [('home', None), ('ocr', 'đối soát ocr'), ('chat', 'tuyết vương ai')]


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


def shoot(page, path, width):
    """Streamlit scrolls inside its main container, so grow the viewport to the content first."""
    height = page.evaluate("""() => Math.max(...['[data-testid=\"stMain\"]', '[data-testid=\"stAppViewContainer\"]', 'section.main']
        .map(s => document.querySelector(s)?.scrollHeight || 0), document.body.scrollHeight)""")
    page.set_viewport_size({'width': width, 'height': min(max(int(height), 900), 6000)})
    page.wait_for_timeout(1200)
    page.screenshot(path=str(path), full_page=True)
    page.set_viewport_size({'width': width, 'height': 900})


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONPATH': str(ROOT), 'APP_DEMO_MODE': 'true'}
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
                shoot(page, out / f'login{suffix}.png', width)
                page.get_by_text('Tài khoản dùng thử').first.click()
                page.wait_for_timeout(800)
                page.get_by_role('button', name='Quản Lý (Admin)').first.click()
                settle(page, 5000)
                for name, nav in PAGES:
                    if nav:
                        page.evaluate("t => [...document.querySelectorAll('.st-key-main_navigation label')]"
                                      ".find(l => l.textContent.toLowerCase().includes(t))?.click()", nav)
                        settle(page, 5000)
                    shoot(page, out / f'{name}{suffix}.png', width)
                page.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'ui_screenshots')
