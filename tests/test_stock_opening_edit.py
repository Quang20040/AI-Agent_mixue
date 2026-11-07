"""Correcting last month's closing stock from this month's sheet (and the other way round)."""
from src.engine.daily_stock_service import get_stock_matrix_df, update_stock_cell_manually


def _row(year, month, ing='2'):
    frame = get_stock_matrix_df(year, month)
    return frame[frame['Mã NL'] == ing].iloc[0]


def test_editing_the_opening_column_fixes_last_months_closing():
    ok, msg = update_stock_cell_manually('2', 'Tồn cuối T10/2026', 9, 'chucuahang', year=2026, month=11)
    assert ok, msg
    nov, oct_ = _row(2026, 11), _row(2026, 10)
    assert nov['Tồn cuối T10/2026'] == 9
    assert nov['Tồn sổ sách'] == 9 + nov['Tổng nhập'] - nov['Tổng xuất']   # whole month recomputed from 9
    assert oct_['Tồn thực tế'] == 9 and oct_['Ngày kiểm kê'] == '2026-10-31'   # shows on October's sheet as the month-end count
    ok, _ = update_stock_cell_manually('2', 'Tồn cuối T10/2026', '', 'chucuahang', year=2026, month=11)   # undo
    assert ok and _row(2026, 10)['Tồn thực tế'] == '—'


def test_month_end_count_in_october_becomes_novembers_opening():
    ok, msg = update_stock_cell_manually('3', 'Tồn thực tế', 4, 'chucuahang', year=2026, month=10)
    assert ok, msg
    assert _row(2026, 11, '3')['Tồn cuối T10/2026'] == 4


def test_staff_cannot_change_the_opening_balance():
    ok, _ = update_stock_cell_manually('2', 'Tồn cuối T10/2026', 1, 'nhanvien', year=2026, month=11)
    assert not ok


def test_stock_page_offers_the_opening_column_for_editing():
    from test_e2e_staff_manager import _open
    app = _open('quick_login_owner')
    app.radio(key='main_navigation').set_value('Báo cáo & kho').run()
    app.session_state['stock_admin_tabs'] = app.tabs[1].label if len(app.tabs) > 1 else None
    app.run()
    assert not app.exception, app.exception
    assert any('sửa được nếu tồn cuối tháng trước bị nhầm' in i.value for i in app.info)
