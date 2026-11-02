"""Real multi-session flow: staff and manager use separate browsers; a reload is a new session.

Only the vision model is scripted; drafts, the LangGraph interrupt and the shift ledger are real.
"""
import json
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest
from test_dashboard_pillars import APP, _scripted_extract

VALUES = {'Chênh lệch tiền mặt dư/thiếu (đ)': 0, 'Khoản chi trong ca (đ)': 0, 'Tổng thu về thực tế (đ)': 2290000}
OCR_PAGE = '📸 Chốt ca & OCR'


def _open(login_key=None, token=None):
    app = AppTest.from_file(str(APP), default_timeout=90)
    if token:
        app.query_params['s'] = token
    app.run()
    if login_key:
        app.button(key=login_key).click().run()
    assert not app.exception, app.exception
    return app


def _token(app):
    value = app.query_params.get('s')
    return value[0] if isinstance(value, list) else value


def _saved(day):
    path = Path(os.environ['SHIFT_DATA_FILE'])
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    return [r for r in data if r.get('business_date') == day]


def test_reload_keeps_the_user_signed_in_and_logout_ends_it():
    app = _open('quick_login_staff')
    token = _token(app)
    assert token
    again = _open(token=token)  # F5
    assert again.session_state['authenticated'] and again.session_state['username'] == app.session_state['username']
    again.button(key='btn_logout').click().run()
    assert any(b.key == 'quick_login_staff' for b in _open(token=token).button)  # login screen again
    assert any(b.key == 'quick_login_staff' for b in _open(token='made-up').button)


def test_staff_to_manager_to_ledger_across_separate_sessions(monkeypatch):
    monkeypatch.setattr('src.dashboard.shift_closing_ui.extract_shift_data_from_image', _scripted_extract(1))
    staff = _open('quick_login_staff')
    staff.radio(key='main_navigation').set_value(OCR_PAGE).run()
    next(b for b in staff.button if b.label == '📷 Sổ Ca Sáng').click().run()
    day = staff.session_state['shift_chosen_date_picker'].isoformat()

    # A reload before reading keeps the day's photos.
    staff = _open(token=_token(staff))
    staff.radio(key='main_navigation').set_value(OCR_PAGE).run()
    assert staff.session_state['ocr_day_images'].get(day), 'photos lost on reload'

    staff.button(key='run_shift_ocr').click().run()
    for item in staff.number_input:
        if item.label in VALUES:
            item.set_value(VALUES[item.label])
    for box in staff.checkbox:
        box.check()
    next(b for b in staff.button if b.label == '📨 Gửi Quản lý duyệt').click().run()
    assert not staff.exception

    manager = _open('quick_login_manager')  # another browser, on the home page
    assert any(b.key == 'open_staff_inbox' for b in manager.button), 'manager is not told a report is waiting'
    manager.button(key='open_staff_inbox').click().run()
    assert manager.session_state['main_navigation'] == OCR_PAGE
    next(b for b in manager.button if (b.key or '').startswith('open_sub_')).click().run()
    pending = manager.session_state['agent_pending_approval']
    assert pending['plan_type'] == 'SHIFT_OCR_DRAFT' and pending['plan']['fields']['report_date'] == day
    before = len(_saved(day))
    manager.button(key='approve_agent_page').click().run()
    assert not manager.exception
    assert len(_saved(day)) == before + 1, 'approved report not written to the ledger'
    assert manager.session_state['shift_chosen_date_picker'].isoformat() == day
    assert not any((b.key or '').startswith('open_sub_') for b in manager.button)

    reloaded = _open(token=_token(manager))  # F5 after approving: still signed in, report still there
    reloaded.radio(key='main_navigation').set_value(OCR_PAGE).run()
    reloaded.session_state['shift_chosen_date_picker']  # noqa: B018 - exists
    assert len(_saved(day)) == before + 1
    assert not any(b.key == 'open_staff_inbox' for b in reloaded.button)
