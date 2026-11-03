"""Screenshots of the deployed site for the written report (one PNG per screen, desktop + a few mobile).

python scripts/report_shots.py https://example.onrender.com out_dir

Read-only except: three chat questions, one OCR read of the 01/11 sample photos (never submitted),
one forecast and one advisory prep calculation.
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_live as q  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else 'report_shots')
OUT.mkdir(parents=True, exist_ok=True)
q.OUT = OUT
done = []


def snap(page, name, full=True):
    try:
        q.idle(page, 1200)
        page.screenshot(path=str(OUT / f'{name}.png'), full_page=full, timeout=60000)
        done.append(name)
        print('shot', name, flush=True)
    except Exception as exc:  # noqa: BLE001
        print('FAILED', name, type(exc).__name__, exc, flush=True)


def step(fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        print('step failed', fn.__name__, type(exc).__name__, str(exc)[:200], flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Login screen (desktop + mobile)
        for width, height, suffix in ((1440, 900, ''), (390, 844, '_mobile')):
            page = q.new_page(browser, width, height, 'login')
            q.open_site(page)
            snap(page, f'01_login{suffix}', full=False)
            page.locator('[data-testid="stExpander"] summary').filter(has_text='Tài khoản dùng thử').first.click()
            page.wait_for_timeout(800)
            snap(page, f'02_login_demo{suffix}', full=False)
            page.context.close()

        mgr = q.new_page(browser, label='manager')
        q.quick_login(mgr, 'quick_login_manager')
        snap(mgr, '03_home_manager')

        def chat():
            q.nav(mgr, 'Trợ lý')
            new_chat = mgr.get_by_role('button', name='Trò chuyện mới')
            if new_chat.count():
                new_chat.first.click()
                q.idle(mgr)
            for message in ('công thức TS1', 'doanh thu hôm qua và hôm kia', 'dự báo ngày mai bán bao nhiêu ly'):
                q.send_chat(mgr, message, 'report')
            snap(mgr, '04_chat_manager')
        step(chat)

        def ocr():
            q.nav(mgr, 'Chốt ca')
            snap(mgr, '05_ocr_empty')
            photos = [ROOT / 'data/shift_photos' / n for n in
                      ('20261101_ca_sang_chieu.jpg', '20261101_ca_toi_tong_ket.jpg', '20261101_ca_toi_pos_slip.jpg')]
            mgr.locator('.st-key-shift_photo_uploader input[type=file]').first.set_input_files([str(x) for x in photos])
            q.idle(mgr, 2500)
            if mgr.locator('.st-key-ocr_move_day button').count():
                mgr.locator('.st-key-ocr_move_day button').first.click()
                q.idle(mgr, 1500)
            mgr.locator('.st-key-run_shift_ocr button').first.click()
            q.idle(mgr, 1500, limit=240)
            if mgr.locator('.st-key-ocr_move_day button').count():
                mgr.locator('.st-key-ocr_move_day button').first.click()
                q.idle(mgr, 1500)
            snap(mgr, '06_ocr_read')
            if mgr.locator('.st-key-ocr_open_evidence button').count():
                mgr.locator('.st-key-ocr_open_evidence button').first.click()
                q.idle(mgr, 1500)
                snap(mgr, '07_ocr_evidence', full=False)
                mgr.keyboard.press('Escape')
                q.idle(mgr)
        step(ocr)

        def stock():
            q.nav(mgr, 'Doanh thu & Kho')
            tabs = mgr.get_by_role('tab')
            for i in range(tabs.count()):
                tabs.nth(i).click()
                q.idle(mgr, 800)
                snap(mgr, f'08_stock_tab{i}')
        step(stock)

        def forecast():
            q.nav(mgr, 'Dự báo bán hàng')
            mgr.get_by_role('button', name='🚀 Dự báo').first.click()
            q.idle(mgr, 1500)
            snap(mgr, '09_forecast')
        step(forecast)

        def prep():
            q.nav(mgr, 'Nấu topping')
            mgr.get_by_role('button', name='⚡ Tính số mẻ cần nấu').first.click()
            q.idle(mgr, 1500)
            snap(mgr, '10_prep')
        step(prep)

        def po():
            q.nav(mgr, 'Đặt hàng nguyên liệu')
            snap(mgr, '11_po')
        step(po)

        def recipe():
            q.nav(mgr, 'Công thức')
            q.idle(mgr, 2500)
            snap(mgr, '12_recipe')
        step(recipe)

        def employees():
            q.nav(mgr, 'Quản lý nhân viên')
            snap(mgr, '13_employees')
        step(employees)
        mgr.context.close()

        staff = q.new_page(browser, label='staff')
        q.quick_login(staff, 'quick_login_staff')
        snap(staff, '14_home_staff')

        def staff_stock():
            q.nav(staff, 'Phiếu')
            snap(staff, '15_staff_stock_slip')
        step(staff_stock)
        staff.context.close()

        for width, height in ((390, 844),):
            mob = q.new_page(browser, width, height, 'mobile')
            q.quick_login(mob, 'quick_login_manager')
            snap(mob, '16_home_mobile')
            q.nav(mob, 'Chốt ca')
            snap(mob, '17_ocr_mobile')
            q.nav(mob, 'Trợ lý')
            snap(mob, '18_chat_mobile')
            mob.context.close()
        browser.close()
    print('done', len(done), 'shots')


if __name__ == '__main__':
    started = time.time()
    main()
    print(f'{time.time() - started:.0f}s')
