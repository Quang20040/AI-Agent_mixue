"""Dashboard surfaces for the two thesis pillars: OCR page, benchmark panel, chat chips."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.auth import CORE_PAGES, get_allowed_pages, page_group
from src.engine.vision_ocr import extract_image

APP = Path(__file__).resolve().parents[1] / 'src' / 'dashboard' / 'app.py'


def _login(key='quick_login_manager'):
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.button(key=key).click().run()
    assert not app.exception
    return app


def test_pillars_come_right_after_home_for_every_role():
    for role in ('MANAGER', 'STAFF_OFFICIAL'):
        pages = get_allowed_pages(role)
        assert tuple(pages[1:3]) == CORE_PAGES
        assert [page_group(p) for p in pages[3:]] and all(page_group(p) in {'support', 'admin'} for p in pages[3:])
    assert get_allowed_pages('STAFF_PROBATION')[1] == '💬 Tuyết Vương AI'


def test_ocr_page_benchmark_runs():
    app = _login()
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    app.button(key='run_ocr_benchmark').click().run()
    assert not app.exception
    report = app.session_state['ocr_benchmark_report']
    assert report['mode'] == 'scripted'
    assert report['verified_summary']['errors_reaching_form'] == 0
    assert report['raw_summary']['errors_reaching_form'] > 0


def test_chat_action_chip_reaches_governance_tool():
    app = _login()
    app.radio(key='main_navigation').set_value('💬 Tuyết Vương AI').run()
    for key in ('chip_ocr_read', 'chip_ocr_update', 'chip_ocr_approve', 'chip_sticker_sop', 'chip_governance'):
        assert any(b.key == key for b in app.button), key
    app.button(key='chip_governance').click().run()
    assert not app.exception
    assert 'Quyền hạn' in app.session_state['chat_history_vi'][-1]['content']


def test_probation_staff_gets_agent_but_not_ocr_page():
    from src.auth import OCR_PAGE, can_access_page
    pages = get_allowed_pages('STAFF_PROBATION')
    assert OCR_PAGE not in pages and not can_access_page('STAFF_PROBATION', OCR_PAGE)
    assert can_access_page('STAFF_OFFICIAL', OCR_PAGE) and can_access_page('MANAGER', OCR_PAGE)


def _scripted_extract(case_index):
    from src.engine.ocr_evaluation import _ScriptedReader, benchmark_cases, make_synthetic_test_images
    from src.engine.vision_ocr import extract_image
    case = benchmark_cases()[case_index]
    image = make_synthetic_test_images()[case['image_key']]

    def fake(*args, shift_hint=None, target_date=None, **kwargs):
        return extract_image(image_bytes=image, model=_ScriptedReader(case['reading']),
                             shift_hint=shift_hint or case['shift_hint'], target_date=target_date)
    return fake


def test_ocr_page_renders_verifiable_table_after_a_read(monkeypatch):
    monkeypatch.setattr('src.dashboard.shift_closing_ui.extract_shift_data_from_image', _scripted_extract(1))
    app = _login()
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    next(b for b in app.button if b.label == '📷 Sổ Ca Sáng').click().run()
    app.button(key='run_shift_ocr').click().run()
    assert not app.exception
    page = ' '.join(m.value for m in app.markdown)
    assert 'px-read-summary' in page and 'ô vàng cần kiểm tra' in page
    assert '<table class="vocr-table vocr-evidence"' not in page  # the evidence lives in a popup
    app.button(key='ocr_open_evidence').click().run()
    html = ' '.join(m.value for m in app.markdown)
    assert 'vocr-table' in html and '962 + 629' in html and 'Cần kiểm tra' in html
    cash = next(item for item in app.number_input if item.label == 'Tiền mặt thu tại quầy (đ)')
    # Uncertain handwritten shorthand is pre-filled as a highlighted suggestion (653 -> 653.000 đ),
    # never as a verified reading: the evidence table still marks it 'Cần kiểm tra'.
    assert cash.value == 653000 and cash.key.startswith('ocr_sugg_cash_vnd')
    bank = next(item for item in app.number_input if item.label == 'Chuyển khoản ngân hàng (đ)')
    assert bank.value == 1591000 and bank.key.startswith('ocr_sugg_')
    assert app.session_state['extracted_cache']['cash_vnd'] is None  # verified value stays empty


def test_chat_draft_and_interrupt_cards_render(monkeypatch):
    monkeypatch.setattr('src.engine.shift_service.extract_shift_image_with_ai', _scripted_extract(1))
    monkeypatch.setattr('src.engine.shift_service.upsert_shift_report',
                        lambda payload, actor_role=None, actor_username=None: (True, '', payload))
    monkeypatch.setattr('src.engine.shift_service.record_ocr_user_edits',
                        lambda **kwargs: {'corrected_fields': [], 'manual_fields': [], 'field_edits': {}})
    app = _login()
    app.radio(key='main_navigation').set_value('💬 Tuyết Vương AI').run()
    sample = next(b for b in app.button if b.key and b.key.startswith('ocr_sample_20261014_ca_sang'))
    sample.click().run()
    assert not app.exception
    assert 'DRAFT_OCR_' in app.session_state['chat_history_vi'][-1]['content']
    assert any(b.key and b.key.startswith('confirm_ocr_DRAFT_OCR_') for b in app.button)

    app.chat_input(key='operations_chat').set_value(
        'Sửa tiền mặt thành 653000, chuyển khoản 1591000, shopee 16000, grab 30000, be food 0, '
        'lệch tiền mặt 0, giữ két 1000000, khoản chi 0, tổng thực thu 2290000, ca sáng ngày 14/10/2026').run()
    app.button(key='chip_ocr_approve').click().run()
    assert not app.exception
    assert app.session_state['agent_pending_approval']['plan_type'] == 'SHIFT_OCR_DRAFT'
    assert any('interrupt()' in m.value for m in app.markdown)
    app.button(key='approve_agent').click().run()
    assert not app.exception
    assert 'ĐÃ XÁC NHẬN' in app.session_state['chat_history_vi'][-1]['content']
    assert not app.session_state['agent_pending_approval']


def _fill_and_send(app, values, label='📨 Gửi yêu cầu Quản lý duyệt'):
    for item in app.number_input:
        if item.label in values:
            item.set_value(values[item.label])
    for box in app.checkbox:
        if not (box.key or '').startswith('apv_'):
            box.check()
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception


def _ledger_mocks(monkeypatch, writes):
    monkeypatch.setattr('src.engine.shift_service.upsert_shift_report',
                        lambda payload, actor_role=None, actor_username=None: (writes.append(payload) or True, '', payload))
    monkeypatch.setattr('src.engine.shift_service.record_ocr_user_edits',
                        lambda **kwargs: {'corrected_fields': [], 'manual_fields': [], 'field_edits': {},
                                          'review_seconds': kwargs.get('review_seconds')})


FULL_VALUES = {'Tiền mặt thu tại quầy (đ)': 653000, 'Chênh lệch tiền mặt dư/thiếu (đ)': 0, 'Chuyển khoản ngân hàng (đ)': 1591000,
               'Tiền cố định két (đ)': 1000000, 'ShopeeFood (đ)': 16000, 'GrabFood (đ)': 30000, 'BeFood (đ)': 0,
               'Khoản chi trong ca (đ)': 0, 'Tổng thu về thực tế (đ)': 2290000}


def test_manager_submission_waits_in_queue_and_is_written_only_on_approval(monkeypatch):
    writes = []
    monkeypatch.setattr('src.dashboard.shift_closing_ui.extract_shift_data_from_image', _scripted_extract(1))
    _ledger_mocks(monkeypatch, writes)
    app = _login()
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    next(b for b in app.button if b.label == '📷 Sổ Ca Sáng').click().run()
    app.button(key='run_shift_ocr').click().run()
    _fill_and_send(app, FULL_VALUES)
    assert writes == []  # queued: nothing written yet
    assert not app.session_state['agent_pending_approval']
    approve = next(b for b in app.button if (b.key or '').startswith('apv_y_ocr_shift_'))
    approve.click().run()
    assert not app.exception and len(writes) == 1
    saved = writes[0]
    assert saved['cash_vnd'] == 653000 and saved['bank_transfer_vnd'] == 1591000
    assert saved['ocr_review']['mode'] == 'ocr_page'
    assert saved.get('image_path')
    assert not any((b.key or '').startswith('apv_y_ocr_shift_') for b in app.button)


def test_staff_checks_prefilled_form_and_manager_approves_it(monkeypatch):
    writes = []
    monkeypatch.setattr('src.dashboard.shift_closing_ui.extract_shift_data_from_image', _scripted_extract(1))
    _ledger_mocks(monkeypatch, writes)
    app = _login('quick_login_staff')
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    next(b for b in app.button if b.label == '📷 Sổ Ca Sáng').click().run()
    app.button(key='run_shift_ocr').click().run()
    submit = next(b for b in app.button if b.label == '📨 Gửi yêu cầu Quản lý duyệt')
    assert not submit.disabled
    # Without ticking the yellow-field check the form refuses to send.
    app.checkbox[0].check()
    submit.click().run()
    assert any('ô tô vàng' in e.value for e in app.error)
    _fill_and_send(app, {'Chênh lệch tiền mặt dư/thiếu (đ)': 0, 'Khoản chi trong ca (đ)': 0, 'Tổng thu về thực tế (đ)': 2290000})
    assert writes == []
    assert any('danh sách chờ duyệt' in str(m.value) for m in [*app.info, *app.success, *app.markdown])
    assert any('Chờ duyệt' in m.value for m in app.markdown)  # the staff member sees the status

    app.button(key='btn_logout').click().run()
    app.button(key='quick_login_manager').click().run()
    assert any((b.key or '').startswith('apv_y_home_shift_') for b in app.button)  # waiting on the home page
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    next(b for b in app.button if (b.key or '').startswith('apv_y_ocr_shift_')).click().run()
    assert not app.exception and len(writes) == 1
    saved = writes[0]
    assert saved['cash_vnd'] == 653000 and saved['bank_transfer_vnd'] == 1591000 and saved['total_collected_vnd'] == 2290000
    assert 'gửi' in saved.get('notes', '')


def test_real_photo_benchmark_tab_renders_without_saved_readings():
    app = _login()
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    app.radio(key='ocr_benchmark_dataset').set_value('real').run()
    app.button(key='run_ocr_benchmark').click().run()
    assert not app.exception
    report = app.session_state['ocr_benchmark_report']
    assert report['mode'] == 'real_replay' and len(report['cases']) == 4


def test_home_greeting_by_role_and_no_thesis_blocks():
    expected = {'quick_login_manager': 'chờ phê duyệt', 'quick_login_staff': 'ca làm việc hiệu quả tại quầy Mixue'}
    for key, phrase in expected.items():
        app = _login(key)
        html = ' '.join(m.value for m in app.markdown)
        assert 'px-greet' in html and phrase in html
        assert 'Mọi phê duyệt đã xong' not in html
        assert 'px-pillar' not in html and 'TRỤ CỘT' not in html.upper()
    staff_html = ' '.join(m.value for m in _login('quick_login_staff').markdown)
    assert 'home_revenue_card' not in staff_html and 'Xem doanh thu theo ngày' not in staff_html


def test_chat_page_has_langgraph_rail_with_rbac_counts():
    for key, admin in (('quick_login_manager', True), ('quick_login_staff', False)):
        app = _login(key)
        app.radio(key='main_navigation').set_value('💬 Tuyết Vương AI').run()
        html = ' '.join(m.value for m in app.markdown)
        assert 'px-chat-head' in html and 'px-rail' in html and 'Luồng LangGraph' in html
        assert ('duyệt được interrupt' in html) is admin
        assert 'Quyền hạn (máy chủ xác thực)' in html


def test_day_photos_are_read_once_and_each_shift_fills_its_own_numbers(monkeypatch):
    """Load the whole day's photos, read once, then switch shifts: each shows its own numbers and photos."""
    from test_day_sheet import DayReader
    reader = DayReader()

    def fake(*args, shift_hint=None, target_date=None, image_path=None, image_paths=None, **kwargs):
        return extract_image(image_path=image_path, image_paths=image_paths, model=reader,
                             shift_hint=shift_hint, target_date=target_date)
    monkeypatch.setattr('src.dashboard.shift_closing_ui.extract_shift_data_from_image', fake)
    app = _login()
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    app.button(key='ocr_sample_all').click().run()
    app.button(key='run_shift_ocr').click().run()
    assert not app.exception
    calls_after_read = reader.calls
    assert calls_after_read == 3  # one call per photo, covering all shifts

    def number(label):
        return next(item for item in app.number_input if item.label == label).value

    assert number('Tiền mặt thu tại quầy (đ)') == 653000
    html = ' '.join(m.value for m in app.markdown)
    assert 'có trong ảnh đã đọc' in html  # opened on today: the photos' shifts are read, nothing closed yet
    # The sample photos say 14/10: the page flags it and offers to close that day instead.
    assert any('Ảnh ghi ngày **14/10/2026**' in e.value for e in app.error)
    app.button(key='ocr_move_day').click().run()
    assert not app.exception
    assert app.session_state['shift_chosen_date_picker'].isoformat() == '2026-10-14'
    html = ' '.join(m.value for m in app.markdown)
    assert 'đã duyệt, đã ghi sổ' in html and 'Gửi lại sẽ tạo bản cập nhật' in ' '.join(i.value for i in app.info)
    assert number('Tiền mặt thu tại quầy (đ)') == 653000
    # Switch to the afternoon: numbers change, nothing is sent to the model again.
    app.session_state['shift_ocr_selection'] = ('CA_CHIEU', 'Ca chiều')
    app.run()
    assert not app.exception
    assert number('Tiền mặt thu tại quầy (đ)') == 2014000
    assert number('Chênh lệch tiền mặt dư/thiếu (đ)') == 20000
    assert number('Chuyển khoản ngân hàng (đ)') == 3861000
    # Photos without the afternoon are marked, not mixed in.
    app.session_state['shift_ocr_selection'] = ('CA_TOI', 'Ca tối')
    app.run()
    assert number('Khoản chi trong ca (đ)') == 56000
    assert number('Tổng doanh thu POS (đ, nếu có)') == 10119000
    assert number('Tổng thu về thực tế (đ)') == 9877000
