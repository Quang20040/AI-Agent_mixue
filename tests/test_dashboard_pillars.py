"""Dashboard surfaces for the two thesis pillars: OCR page, benchmark panel, chat chips."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.auth import CORE_PAGES, get_allowed_pages, page_group

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


def test_home_pillar_button_opens_ocr_page_and_benchmark_runs():
    app = _login()
    app.button(key='pillar_open_ocr').click().run()
    assert not app.exception
    assert app.session_state['main_navigation'] == '📸 Chốt ca & OCR'
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
    html = ' '.join(m.value for m in app.markdown)
    assert 'vocr-table' in html and '962 + 629' in html and 'Cần kiểm tra' in html
    cash = next(item for item in app.number_input if item.label == 'Tiền mặt thu tại quầy (đ)')
    assert cash.value is None  # uncertain handwritten number is never pre-filled


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


def test_ocr_page_submission_goes_through_interrupt_before_any_write(monkeypatch):
    writes = []
    monkeypatch.setattr('src.dashboard.shift_closing_ui.extract_shift_data_from_image', _scripted_extract(1))
    monkeypatch.setattr('src.engine.shift_service.upsert_shift_report',
                        lambda payload, actor_role=None, actor_username=None: (writes.append(payload) or True, '', payload))
    monkeypatch.setattr('src.engine.shift_service.record_ocr_user_edits',
                        lambda **kwargs: {'corrected_fields': [], 'manual_fields': [], 'field_edits': {},
                                          'review_seconds': kwargs.get('review_seconds')})
    app = _login()
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    next(b for b in app.button if b.label == '📷 Sổ Ca Sáng').click().run()
    app.button(key='run_shift_ocr').click().run()
    values = {'Tiền mặt thu tại quầy (đ)': 653000, 'Chênh lệch tiền mặt dư/thiếu (đ)': 0, 'Chuyển khoản ngân hàng (đ)': 1591000,
              'Tiền cố định két (đ)': 1000000, 'ShopeeFood (đ)': 16000, 'GrabFood (đ)': 30000, 'BeFood (đ)': 0,
              'Khoản chi trong ca (đ)': 0, 'Tổng thu về thực tế (đ)': 2290000}
    for item in app.number_input:
        if item.label in values:
            item.set_value(values[item.label])
    app.checkbox[0].check()
    next(b for b in app.button if b.label.startswith('📨 Gửi phê duyệt')).click().run()
    assert not app.exception
    assert writes == []  # paused at interrupt(): nothing written yet
    assert app.session_state['agent_pending_approval']['plan_type'] == 'SHIFT_OCR_DRAFT'
    app.button(key='approve_agent_page').click().run()
    assert not app.exception
    assert len(writes) == 1
    saved = writes[0]
    assert saved['cash_vnd'] == 653000 and saved['bank_transfer_vnd'] == 1591000
    assert saved['ocr_review']['mode'] == 'ocr_page'
    assert saved.get('image_path')


def test_staff_cannot_submit_from_ocr_page():
    app = _login('quick_login_staff')
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    assert not app.exception
    submit = next(b for b in app.button if b.label.startswith('📨 Gửi phê duyệt'))
    assert submit.disabled


def test_real_photo_benchmark_tab_renders_without_saved_readings():
    app = _login()
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    app.radio(key='ocr_benchmark_dataset').set_value('real').run()
    app.button(key='run_ocr_benchmark').click().run()
    assert not app.exception
    report = app.session_state['ocr_benchmark_report']
    assert report['mode'] == 'real_replay' and len(report['cases']) == 4


def test_home_greeting_and_pillars_show_live_numbers_not_invented_ones():
    app = _login()
    html = ' '.join(m.value for m in app.markdown)
    assert 'px-greet' in html and 'Tuyết Vương' in html
    assert 'mx-hero' not in html  # the old hero is replaced on the home page
    assert 'px-pillar' in html and 'data-count' in html
    state = app.session_state['_home_state']
    assert f"{state['bench_raw']} → {state['bench_verified']}" in html
    assert state['bench_verified'] == 0 and state['bench_raw'] > 0
    assert all(node in html for node in ('guard', 'authorize', 'approval'))


def test_chat_page_has_langgraph_rail_with_rbac_counts():
    for key, admin in (('quick_login_manager', True), ('quick_login_staff', False)):
        app = _login(key)
        app.radio(key='main_navigation').set_value('💬 Tuyết Vương AI').run()
        html = ' '.join(m.value for m in app.markdown)
        assert 'px-chat-head' in html and 'px-rail' in html and 'Luồng LangGraph' in html
        assert ('duyệt được interrupt' in html) is admin
