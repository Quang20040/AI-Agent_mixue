"""Approval queue (several shifts + stock slips, batch approve), revenue from approved shifts, role greetings,
monthly stock file without sample data."""
import json
import os
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest
from test_dashboard_pillars import APP, _scripted_extract

from src.engine.daily_stock_service import create_stock_request, get_pending_requests

OCR_PAGE = '📸 Chốt ca & OCR'
SEND = '📨 Gửi yêu cầu Quản lý duyệt'
VALUES = {'Chênh lệch tiền mặt dư/thiếu (đ)': 0, 'Khoản chi trong ca (đ)': 0, 'Tổng thu về thực tế (đ)': 2290000}


def _open(login_key):
    app = AppTest.from_file(str(APP), default_timeout=90).run()
    app.button(key=login_key).click().run()
    assert not app.exception
    return app


def _send(app):
    for item in app.number_input:
        if item.label in VALUES:
            item.set_value(VALUES[item.label])
    for box in app.checkbox:
        if not (box.key or '').startswith('apv_'):
            box.check()
    next(b for b in app.button if b.label == SEND).click().run()
    assert not app.exception


def _saved(day):
    path = Path(os.environ['SHIFT_DATA_FILE'])
    return [r for r in json.loads(path.read_text(encoding='utf-8')) if r.get('business_date') == day]


def test_two_shifts_and_a_stock_slip_wait_together_and_are_approved_in_one_click(monkeypatch):
    monkeypatch.setattr('src.dashboard.shift_closing_ui.extract_shift_data_from_image', _scripted_extract(1))
    staff = _open('quick_login_staff')
    staff.radio(key='main_navigation').set_value(OCR_PAGE).run()
    next(b for b in staff.button if b.label == '📷 Sổ Ca Sáng').click().run()
    day = staff.session_state['shift_chosen_date_picker'].isoformat()
    staff.button(key='run_shift_ocr').click().run()
    _send(staff)
    # Without waiting for the morning to be approved, send the afternoon too.
    staff.session_state['shift_ocr_selection'] = ('CA_CHIEU', 'Ca chiều')
    staff.run()
    staff.button(key='run_shift_ocr').click().run()
    _send(staff)
    slip = create_stock_request(business_date=date.fromisoformat(day), ingredient_id='1', movement_type='OUT', quantity=1,
                                recorded_by='nhanvien', user_role='STAFF_OFFICIAL', notes='queue test')
    assert slip['status'] == 'SUCCESS'

    manager = _open('quick_login_manager')
    rows = [b.key for b in manager.button if (b.key or '').startswith('apv_y_home_')]
    shift_rows = [k for k in rows if '_shift_' in k]
    assert len(shift_rows) == 2 and any('_stock_' in k for k in rows), rows
    assert 'yêu cầu đang chờ bạn phê duyệt' in ' '.join(m.value for m in manager.markdown)
    before = {r['shift_code']: r.get('updated_at') for r in _saved(day)}
    pending_stock = len(get_pending_requests())
    manager.button(key='apv_all_home').click().run()
    batch = manager.button(key='apv_ok_home')
    assert not batch.disabled and f'({len(rows)})' in batch.label
    batch.click().run()
    assert not manager.exception
    after = {r['shift_code']: r.get('updated_at') for r in _saved(day)}
    assert all(after.get(code) and after[code] != before.get(code) for code in ('CA_SANG', 'CA_CHIEU'))  # both written
    assert len(get_pending_requests()) == pending_stock - 1  # the slip is approved
    assert not any((b.key or '').startswith('apv_y_home_') for b in manager.button)

    # Revenue: the two approved shifts show up at once on the home day view.
    from src.engine.revenue import day_revenue
    info = day_revenue(date.fromisoformat(day))
    assert info['shift_count'] >= 2 and info['effective_revenue_vnd'] == sum(
        r['total_collected_vnd'] for r in _saved(day))
    assert info['source'].startswith(('Chốt ca', 'Đã đối soát'))


def test_resending_the_same_shift_replaces_the_waiting_report_only(monkeypatch):
    monkeypatch.setattr('src.dashboard.shift_closing_ui.extract_shift_data_from_image', _scripted_extract(1))
    staff = _open('quick_login_staff')
    staff.radio(key='main_navigation').set_value(OCR_PAGE).run()
    next(b for b in staff.button if b.label == '📷 Sổ Ca Sáng').click().run()
    staff.button(key='run_shift_ocr').click().run()
    _send(staff)
    _send(staff)
    assert any('đã được thay bằng bản mới' in i.value for i in [*staff.info, *staff.success])
    mine = staff.session_state['operations_agent'].list_my_submissions('STAFF_OFFICIAL', 'x', user_id=staff.session_state['username'])
    statuses = [m['status'] for m in mine[:2]]
    assert statuses == ['SUBMITTED', 'SUPERSEDED']


def test_rejected_report_writes_nothing_and_staff_sees_it(monkeypatch):
    monkeypatch.setattr('src.dashboard.shift_closing_ui.extract_shift_data_from_image', _scripted_extract(1))
    staff = _open('quick_login_staff')
    staff.radio(key='main_navigation').set_value(OCR_PAGE).run()
    next(b for b in staff.button if b.label == '📷 Sổ Ca Tối') .click().run()
    day = staff.session_state['shift_chosen_date_picker'].isoformat()
    staff.button(key='run_shift_ocr').click().run()
    _send(staff)
    before = len(_saved(day))
    manager = _open('quick_login_manager')
    next(b for b in manager.button if (b.key or '').startswith('apv_n_home_shift_')).click().run()
    assert len(_saved(day)) == before
    staff.radio(key='main_navigation').set_value('Trang chủ').run()
    staff.radio(key='main_navigation').set_value(OCR_PAGE).run()
    assert any('Từ chối' in m.value for m in staff.markdown)


def test_greetings_follow_the_role():
    from src.dashboard.brand_ui import greeting_for
    state = {'staff_waiting': 0, 'stock_waiting': 0, 'plans_waiting': 0, 'pending_approval': None, 'my_pending': 0}
    _, admin_none, _, _ = greeting_for('ADMIN', 'buổi sáng', 'Quang', state)
    assert admin_none == 'Chào buổi sáng, Quang! Hiện chưa có yêu cầu nào chờ phê duyệt.'
    _, admin_some, _, _ = greeting_for('ADMIN', 'buổi sáng', 'Quang', {**state, 'staff_waiting': 2, 'stock_waiting': 1})
    assert admin_some == 'Chào buổi sáng, Quang! Hiện có 3 yêu cầu đang chờ bạn phê duyệt.'
    _, staff, sub, _ = greeting_for('STAFF_OFFICIAL', 'buổi tối', 'Thảo', {**state, 'my_pending': 2})
    assert staff == 'Chào buổi tối, Thảo! Chúc bạn một ca làm việc hiệu quả tại quầy Mixue.'
    assert sub == 'Bạn có 2 phiếu đề xuất đang chờ Quản lý xác nhận.'
    _, probation, sub, _ = greeting_for('STAFF_PROBATION', 'buổi trưa', 'An', state, can_ocr=False)
    assert probation == 'Chào buổi trưa, An! Sẵn sàng tra cứu công thức pha chế & quy chuẩn SOP quầy bar.'
    for role in ('STAFF_OFFICIAL', 'STAFF_PROBATION'):
        text = ' '.join(greeting_for(role, 'x', 'y', state)[1:])
        assert 'phê duyệt' not in text.replace('Quản lý xác nhận', '') and 'Mọi phê duyệt đã xong' not in text
    staff_html = ' '.join(m.value for m in _open('quick_login_staff').markdown)
    assert 'Chúc bạn một ca làm việc hiệu quả' in staff_html and 'Xem doanh thu theo ngày' not in staff_html


def test_stock_file_follows_the_real_month_and_says_when_empty():
    from src.engine.daily_stock_service import get_stock_matrix_df
    from src.engine.stock_matrix import current_period, opening_label
    year, month = current_period()
    frame = get_stock_matrix_df()
    assert opening_label(year, month) in frame.columns
    import calendar
    days = calendar.monthrange(year, month)[1]
    assert sum(1 for c in frame.columns if str(c).startswith('Nhập ')) == days
    feb = get_stock_matrix_df(2027, 2)
    assert 'Tồn cuối T1/2027' in feb.columns and not any(c.startswith('Nhập 29/') for c in feb.columns)
    app = _open('quick_login_manager')
    app.radio(key='main_navigation').set_value('Báo cáo & kho').run()
    app.date_input(key='stock_period').set_value(date(2030, 1, 1)).run()
    assert not app.exception
    assert any('Kỳ Tháng 01/2030 hiện chưa có giao dịch thực tế phát sinh' in i.value for i in app.info)
    assert any('31 ngày' in s.value for s in app.subheader)


def test_clean_script_keeps_master_data(tmp_path):
    import shutil
    import subprocess
    import sys
    db = tmp_path / 'b.db'
    shutil.copy2(Path(os.environ['DATABASE_URL'].removeprefix('sqlite:///')), db)
    shift = tmp_path / 's.json'
    shift.write_text('[{"business_date": "2026-10-14"}]', encoding='utf-8')
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'scripts' / 'clean_demo_transactions.py'), '--apply',
                    '--db', f'sqlite:///{db}', '--shift-file', str(shift)], check=True, capture_output=True)
    import sqlite3
    con = sqlite3.connect(db)
    assert con.execute('SELECT COUNT(*) FROM sales_daily').fetchone()[0] == 0
    assert con.execute('SELECT COUNT(*) FROM daily_stock_movements').fetchone()[0] == 0
    assert con.execute('SELECT COUNT(*) FROM menu_items').fetchone()[0] == 39
    assert con.execute('SELECT COUNT(*) FROM users').fetchone()[0] >= 4
    assert json.loads(shift.read_text(encoding='utf-8')) == []
