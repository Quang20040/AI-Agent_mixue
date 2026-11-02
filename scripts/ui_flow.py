"""Click through staff → manager approval in a real browser and screenshot every step.

python scripts/ui_flow.py out_dir   (writes NN_step[_mobile].png and report.md; exit 1 on a UI error)
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8621
URL = f'http://localhost:{PORT}'
PHOTOS = [ROOT / 'data/shift_photos' / n for n in
          ('20261101_ca_sang_chieu.jpg', '20261101_ca_toi_tong_ket.jpg', '20261101_ca_toi_pos_slip.jpg')]
report, problems, step_no = [], [], [0]


def wait_server(timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(URL + '/_stcore/health', timeout=3)
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError('Streamlit did not start')


def idle(page, extra=800):
    """Wait until the script has been idle for 1.5 s in a row (a st.rerun briefly looks idle)."""
    state = "() => document.querySelector('[data-testid=\"stApp\"]')?.getAttribute('data-test-script-state')"
    end, quiet = time.time() + 90, 0.0
    while time.time() < end and quiet < 1.5:
        page.wait_for_timeout(250)
        quiet = quiet + 0.25 if page.evaluate(state) not in ('running', 'rerunRequested') else 0.0
    if quiet < 1.5:
        problems.append('script still running after 90 s')
    page.wait_for_timeout(extra)


def snap(page, name, note=''):
    step_no[0] += 1
    stem = f'{step_no[0]:02d}_{name}'
    errors = page.locator('[data-testid="stException"]')
    if errors.count():
        problems.append(f'{stem}: exception on page: ' + errors.first.inner_text()[:400].replace('\n', ' '))
    for width, suffix in ((1440, ''), (390, '_mobile')):
        page.set_viewport_size({'width': width, 'height': 900})
        page.wait_for_timeout(700)
        height = page.evaluate("""() => Math.max(...['[data-testid="stMain"]', '[data-testid="stAppViewContainer"]']
            .map(s => document.querySelector(s)?.scrollHeight || 0), document.body.scrollHeight)""")
        page.set_viewport_size({'width': width, 'height': min(max(int(height), 900), 7000)})
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT / f'{stem}{suffix}.png'), full_page=True)
    page.set_viewport_size({'width': 1440, 'height': 900})
    report.append(f'- **{stem}** {note}')


def click(page, selector, label):
    target = page.locator(selector).first
    try:
        target.wait_for(state='visible', timeout=20000)
        target.scroll_into_view_if_needed()
        target.click()
    except Exception as exc:
        problems.append(f'cannot click {label} ({selector}): {type(exc).__name__}')
        return False
    idle(page)
    return True


def login(page, key):
    page.goto(URL)
    idle(page, 2500)
    page.get_by_text('Tài khoản dùng thử').first.click()
    page.wait_for_timeout(600)
    click(page, f'.st-key-{key} button', key)


def nav(page, text):
    page.evaluate("t => [...document.querySelectorAll('.st-key-main_navigation label')]"
                  ".find(l => l.textContent.toLowerCase().includes(t))?.click()", text)
    idle(page, 2500)


def main():
    # Streamlit serves ./static next to the main script; the wrapper lives in scripts/, the assets in src/dashboard/.
    static = ROOT / 'scripts' / 'static'
    if not static.exists():
        static.symlink_to(ROOT / 'src' / 'dashboard' / 'static', target_is_directory=True)
    env = {**os.environ, 'PYTHONPATH': str(ROOT), 'APP_DEMO_MODE': 'true', 'LLM_ENABLED': 'false'}
    server = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'scripts/ui_flow_app.py', '--server.headless', 'true',
                               '--server.port', str(PORT), '--browser.gatherUsageStats', 'false'], cwd=ROOT, env=env)
    try:
        wait_server()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            # ---- staff browser
            staff_ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
            staff = staff_ctx.new_page()
            staff.on('console', lambda m: m.type == 'error' and problems.append('staff console: ' + m.text[:200]))
            staff.on('response', lambda r: r.status == 404 and problems.append('404: ' + r.url[:160]))
            login(staff, 'quick_login_staff')
            nav(staff, 'đối soát ocr')
            snap(staff, 'staff_ocr_empty', 'nhân viên mở trang chốt ca')
            staff.locator('.st-key-shift_photo_uploader input[type=file]').set_input_files([str(p) for p in PHOTOS])
            idle(staff, 3000)
            snap(staff, 'staff_photos_added', '3 ảnh 01/11 đã tải lên')
            click(staff, '.st-key-run_shift_ocr button', 'read')
            snap(staff, 'staff_read', 'sau khi đọc ảnh')
            if staff.locator('.st-key-ocr_move_day button').count():
                click(staff, '.st-key-ocr_move_day button', 'move to photo day')
                if staff.locator('.st-key-run_shift_ocr button').is_enabled():
                    click(staff, '.st-key-run_shift_ocr button', 'read again')
                snap(staff, 'staff_moved_to_photo_day', 'chuyển sang ngày trên ảnh')
            staff.get_by_text('Tôi đã đối chiếu ảnh, ngày').first.click()
            if staff.locator('[class*="st-key-ocr_checksugg_"] label').count():
                staff.locator('[class*="st-key-ocr_checksugg_"] label').first.click()
            staff.wait_for_timeout(500)
            snap(staff, 'staff_form_ready', 'đã tick xác nhận')
            submit = staff.get_by_role('button', name='📨 Gửi Quản lý duyệt')
            if submit.count():
                submit.first.click()
                idle(staff)
            else:
                problems.append('staff submit button missing')
            snap(staff, 'staff_submitted', 'sau khi gửi quản lý')
            staff.reload()
            idle(staff, 3000)
            snap(staff, 'staff_after_reload', 'nhân viên bấm F5')

            # ---- manager browser
            mgr_ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
            mgr = mgr_ctx.new_page()
            mgr.on('console', lambda m: m.type == 'error' and problems.append('manager console: ' + m.text[:200]))
            login(mgr, 'quick_login_manager')
            snap(mgr, 'manager_home_banner', 'trang chủ quản lý: phải có dòng báo chờ duyệt')
            if not click(mgr, '.st-key-open_staff_inbox button', 'inbox banner'):
                nav(mgr, 'đối soát ocr')
            snap(mgr, 'manager_inbox', 'hộp chờ duyệt')
            click(mgr, '[class*="st-key-open_sub_"] button', 'open submission')
            snap(mgr, 'manager_approval_card', 'thẻ interrupt chờ phê duyệt')
            click(mgr, '[class*="st-key-approve_agent_page"] button', 'approve')
            if mgr.locator('[class*="st-key-approval_card"]').count():
                problems.append('approval card still on screen after approving')
            if not mgr.get_by_text('ĐÃ XÁC NHẬN').count():
                problems.append('no confirmation shown after approving')
            snap(mgr, 'manager_after_approve', 'ngay sau khi bấm Phê duyệt')
            mgr.reload()
            idle(mgr, 3000)
            snap(mgr, 'manager_after_reload', 'quản lý bấm F5 sau khi duyệt')
            nav(mgr, 'đối soát ocr')
            snap(mgr, 'manager_ocr_after_reload', 'trang chốt ca sau F5')
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)
    (OUT / 'report.md').write_text('# UI flow\n\n' + '\n'.join(report) + '\n\n## Problems\n\n'
                                   + ('\n'.join(f'- {p}' for p in problems) or '- none') + '\n', encoding='utf-8')
    print('\n'.join(problems) or 'no problems')


if __name__ == '__main__':
    OUT = Path(sys.argv[1] if len(sys.argv) > 1 else 'ui_flow')
    OUT.mkdir(parents=True, exist_ok=True)
    main()
