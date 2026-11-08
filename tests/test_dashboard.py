"""Kiểm thử tự động luồng Xác thực đăng nhập & Phân quyền RBAC trên Dashboard."""
from pathlib import Path

from streamlit.testing.v1 import AppTest
from src.dashboard.brand_ui import nav_label
from src.auth import normalize_role

APP = Path(__file__).resolve().parents[1] / 'src' / 'dashboard' / 'app.py'


def test_shift_ocr_does_not_fill_sample_amounts_when_api_disabled():
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.button(key='quick_login_manager').click().run()
    app.radio(key='main_navigation').set_value('📸 Chốt ca & OCR').run()
    next(button for button in app.button if button.label == '📷 Sổ Ca Chiều').click().run()
    assert app.session_state['shift_ocr_selection'][0] == 'CA_CHIEU'
    app.button(key='run_shift_ocr').click().run()
    assert not app.exception
    assert app.session_state['extracted_cache']['status'] in {'OCR_DISABLED', 'EXTERNAL_TRANSFER_DISABLED'}
    assert 'cash_vnd' not in app.session_state['extracted_cache']
    cash_input = next(item for item in app.number_input if item.label == 'Tiền mặt thu tại quầy (đ)')
    assert cash_input.value is None


def test_unauthenticated_login_screen():
    """Kiểm tra màn hình đăng nhập hiển thị khi chưa xác thực."""
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    assert not app.exception
    assert not app.session_state.get('authenticated', False)
    # Phải có ô nhập tài khoản, mật khẩu và nút đăng nhập
    assert 'login_username' in [t.key for t in app.text_input]
    assert 'login_password' in [t.key for t in app.text_input]
    assert any('quick_login_' in b.key for b in app.button)


def test_dashboard_admin_full_access():
    """Kiểm tra tài khoản Quản lý / Chủ quán (Admin) có toàn quyền truy cập 7 tabs."""
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.button(key='quick_login_manager').click().run()
    assert not app.exception
    assert app.session_state.get('authenticated') is True
    assert app.session_state.get('user_role') == 'ADMIN'

    # Admin thấy 2 trụ cột (AI Agent, Chốt ca & OCR) ngay sau Trang chủ, rồi tới công cụ phụ trợ và quản trị
    expected_tabs = ['Trang chủ', '💬 Tuyết Vương AI', '📸 Chốt ca & OCR', 'Báo cáo & kho', 'Dự báo', 'Sơ chế', 'Nhập hàng', 'Tem & công thức', '📅 Lịch làm', '👥 Quản lý nhân viên', '🛠️ Kỹ thuật AI']
    assert app.radio(key='main_navigation').options == [nav_label(page) for page in expected_tabs]

    # Kiểm tra tra cứu món và gửi công thức sang chat
    app.text_input(key='menu_search').set_value('tra sua tran chau').run()
    assert not app.exception
    assert any('Trà sữa trân châu' in m.value for m in app.markdown)
    app.button(key='menu_TS1').click().run()
    history = app.session_state['chat_history_vi']
    assert history[-2]['content'] == 'Công thức TS1'
    assert 'TS1' in history[-1]['content']
    assert history[-1]['evidence']

    # Kiểm tra duyệt các tab quản trị
    for page in ['📸 Chốt ca & OCR', 'Báo cáo & kho', 'Dự báo', 'Sơ chế', 'Nhập hàng', 'Tem & công thức', '👥 Quản lý nhân viên']:
        app.radio(key='main_navigation').set_value(page).run()
        assert not app.exception, page
        assert not app.chat_input  # the full chat lives only on the assistant page
        assert any(t.key == 'mascot_q' for t in app.text_input)  # small Tuyết Vương corner button instead

    # Kiểm tra xóa lịch sử chat (trang Trợ lý Tuyết Vương)
    app.radio(key='main_navigation').set_value('💬 Tuyết Vương AI').run()
    assert app.chat_input
    app.button(key='clear_chat').click().run()
    assert len(app.session_state['chat_history_vi']) == 1


def test_dashboard_staff_restricted_access():
    """Kiểm tra tài khoản Nhân viên chính thức truy cập Sổ kho, Menu/Công thức/Tem và Tuyết Vương AI."""
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.button(key='quick_login_staff').click().run()
    assert not app.exception
    assert app.session_state.get('authenticated') is True
    assert normalize_role(app.session_state.get('user_role')) == 'STAFF_OFFICIAL'

    # Nhân viên chính thức: Trang chủ, 2 trụ cột (AI Agent, Chốt ca & OCR), Báo cáo & kho, Tem & công thức
    allowed_staff_tabs = ['Trang chủ', '💬 Tuyết Vương AI', '📸 Chốt ca & OCR', 'Báo cáo & kho', 'Tem & công thức', '📅 Lịch làm']
    # Staff only file stock slips there, so their menu names the page by that (not "Doanh thu & Kho hàng").
    staff_labels = [('Phiếu xin nhập / xuất kho' if page == 'Báo cáo & kho' else nav_label(page)) for page in allowed_staff_tabs]
    assert app.radio(key='main_navigation').options == staff_labels
    assert len(app.radio(key='mobile_navigation').options) == len(allowed_staff_tabs)
    assert not any('mx-revenue-total' in m.value for m in app.markdown)
    assert not any('mx-approvals' in m.value for m in app.markdown)

    # Các tab quản trị nâng cao phải bị ẩn hoàn toàn
    for restricted in ['Dự báo', 'Sơ chế', 'Nhập hàng', '👥 Quản lý nhân viên']:
        assert nav_label(restricted) not in app.radio(key='main_navigation').options

    # Nhân viên vẫn được xem thực đơn và công thức món
    app.button(key='menu_TS1').click().run()
    history = app.session_state['chat_history_vi']
    assert history[-2]['content'] == 'Công thức TS1'
    assert 'TS1' in history[-1]['content']

    # Kiểm tra tab Tem & công thức
    app.radio(key='main_navigation').set_value('Tem & công thức').run()
    assert not app.exception
    assert len(app.text_input) > 0


def test_dashboard_logout_flow():
    """Kiểm tra chức năng Đăng xuất trả người dùng về màn hình đăng nhập."""
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.button(key='quick_login_owner').click().run()
    assert app.session_state.get('authenticated') is True

    # Bấm đăng xuất
    app.button(key='btn_logout').click().run()
    assert not app.exception
    assert not app.session_state.get('authenticated', False)
    assert 'login_username' in [t.key for t in app.text_input]


def test_mobile_navigation_syncs_with_sidebar():
    """Both controls must open the same authorized page after each rerun."""
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.button(key='quick_login_manager').click().run()
    app.radio(key='mobile_navigation').set_value('Tem & công thức').run()
    assert not app.exception
    assert app.session_state['main_navigation'] == 'Tem & công thức'
    assert app.radio(key='main_navigation').value == 'Tem & công thức'
    app.radio(key='main_navigation').set_value('Trang chủ').run()
    assert not app.exception
    assert app.radio(key='mobile_navigation').value == 'Trang chủ'


def test_forecast_context_and_estimated_batch_controls(monkeypatch):
    from datetime import date

    saved = []
    monkeypatch.setattr('src.agent.mixue_agent.save_plan', lambda plan: saved.append(plan))
    app = AppTest.from_file(str(APP), default_timeout=90).run()
    app.button(key='quick_login_manager').click().run()
    app.radio(key='main_navigation').set_value('Dự báo').run()
    app.date_input(key='fc_date_picker_vi').set_value(date(2026, 10, 16)).run()
    app.button(key='run_fc_btn_vi').click().run()
    assert not app.exception
    result = app.session_state['latest_forecast_vi']
    assert result.attrs['forecast_context']['status'] == 'DISABLED'
    assert len(result) == 39
    app.radio(key='main_navigation').set_value('Sơ chế').run()
    app.date_input(key='prep_date_in_vi').set_value(date(2026, 10, 16)).run()
    app.button(key='calc_prep_btn_vi').click().run()
    assert not app.exception
    plan = app.session_state['prep_plan_vi']
    pearl = next(line for line in plan['recommendations'] if line['ingredient_id'] == 'TP02')
    assert pearl['unit'] == 'g' and 'Trân châu' in pearl['ingredient_name']
    assert pearl['batch_yield_is_estimate']
    assert pearl['initial_prep_qty'] <= pearl['recommended_prep_qty']
    assert saved[-1]['forecast_context']['status'] == 'DISABLED'
    app.number_input(key='pearl_yield_estimate').set_value(2500).run()
    app.button(key='calc_prep_btn_vi').click().run()
    assert not app.exception
    recalculated = next(line for line in app.session_state['prep_plan_vi']['recommendations'] if line['ingredient_id'] == 'TP02')
    assert recalculated['batch_size'] == 2500
    assert recalculated['batch_yield_is_estimate']
