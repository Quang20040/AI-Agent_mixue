# -*- coding: utf-8 -*-
"""Kiểm thử tự động luồng Xác thực đăng nhập & Phân quyền RBAC trên Dashboard."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / 'src' / 'dashboard' / 'app.py'


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

    # Admin phải thấy đủ 8 tab nghiệp vụ (kèm tab Quản lý nhân viên mới)
    expected_tabs = ['Trang chủ', 'Báo cáo & kho', 'Dự báo', 'Sơ chế', 'Nhập hàng', 'Tem & công thức', '👥 Quản lý nhân viên', '💬 Tuyết Vương AI']
    assert app.radio(key='main_navigation').options == expected_tabs

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
    for page in ['Báo cáo & kho', 'Dự báo', 'Sơ chế', 'Nhập hàng', 'Tem & công thức', '👥 Quản lý nhân viên']:
        app.radio(key='main_navigation').set_value(page).run()
        assert not app.exception, page
        assert app.chat_input

    # Kiểm tra xóa lịch sử chat
    app.button(key='clear_chat').click().run()
    assert len(app.session_state['chat_history_vi']) == 1


def test_dashboard_staff_restricted_access():
    """Kiểm tra tài khoản Nhân viên chính thức truy cập Sổ kho, Menu/Công thức/Tem và Tuyết Vương AI."""
    app = AppTest.from_file(str(APP), default_timeout=45).run()
    app.button(key='quick_login_staff').click().run()
    assert not app.exception
    assert app.session_state.get('authenticated') is True
    assert app.session_state.get('user_role') == 'STAFF'

    # Nhân viên chính thức có 4 tab: Trang chủ, Báo cáo & kho (Sổ kho hàng ngày), Tem & công thức, 💬 Tuyết Vương AI
    allowed_staff_tabs = ['Trang chủ', 'Báo cáo & kho', 'Tem & công thức', '💬 Tuyết Vương AI']
    assert app.radio(key='main_navigation').options == allowed_staff_tabs

    # Các tab quản trị nâng cao phải bị ẩn hoàn toàn
    for restricted in ['Dự báo', 'Sơ chế', 'Nhập hàng', '👥 Quản lý nhân viên']:
        assert restricted not in app.radio(key='main_navigation').options

    # Nhân viên vẫn được xem thực đơn và công thức món
    app.button(key='menu_TS1').click().run()
    history = app.session_state['chat_history_vi']
    assert history[-2]['content'] == 'Công thức TS1'
    assert 'TS1' in history[-1]['content']

    # Kiểm tra tab Tem & công thức
    app.radio(key='main_navigation').set_value('Tem & công thức').run()
    assert not app.exception
    assert len(app.text_input) > 0 or app.chat_input


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
