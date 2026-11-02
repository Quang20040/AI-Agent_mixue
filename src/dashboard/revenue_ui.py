"""Revenue views built on src.engine.revenue (approved shift closings + POS item sales, never added together)."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

from src.dashboard.sales_view import business_today
from src.engine.revenue import SHIFTS, daily_revenue, day_revenue

SHIFT_NAMES = {'CA_SANG': 'Ca sáng', 'CA_CHIEU': 'Ca chiều', 'CA_TOI': 'Ca tối'}


def money(value) -> str:
    return f"{float(value or 0):,.0f} đ".replace(',', '.')


def _chart(frame: pd.DataFrame, x: str, y: str, kind: str = 'bar', color: str = '#E60012', height: int = 230) -> None:
    data = pd.DataFrame({x: pd.to_datetime(frame[x]).dt.strftime('%Y-%m-%d'), y: frame[y]})
    st.vega_lite_chart(data, {
        'mark': {'type': kind, 'color': color, 'tooltip': True},
        'encoding': {'x': {'field': x, 'type': 'temporal', 'title': None, 'axis': {'format': '%d/%m'}},
                     'y': {'field': y, 'type': 'quantitative', 'title': None}},
        'height': height,
    }, use_container_width=True)


def _pending_shifts(day: date) -> set[str]:
    """Shifts of this day that staff or a manager sent and that wait for approval."""
    agent = st.session_state.get('operations_agent')
    if agent is None:
        return set()
    try:
        items = agent.list_staff_submissions(st.session_state.get('user_role', ''), st.session_state.get('user_name', ''),
                                             user_id=st.session_state.get('username'))
    except Exception:  # noqa: BLE001 - the revenue view must render even if the queue is unavailable
        return set()
    return {sub.get('shift_code') for sub in items if sub.get('business_date') == day.isoformat()}


def render_day_revenue_viewer() -> None:
    """Home (managers only): one day's recorded revenue, today by default."""
    today = business_today()
    if 'home_rev_day' not in st.session_state:
        st.session_state.home_rev_day = today

    def pick(day):
        st.session_state.home_rev_day = day

    with st.container(border=True, key='home_revenue_card'):
        head, b_today, b_yesterday, picker = st.columns([2.2, 0.8, 0.8, 1.2], vertical_alignment='bottom')
        head.markdown('<div class="px-card-title">📅 Xem doanh thu theo ngày</div>', unsafe_allow_html=True)
        b_today.button('Hôm nay', key='rev_today', use_container_width=True, on_click=pick, args=(today,))
        b_yesterday.button('Hôm qua', key='rev_yesterday', use_container_width=True, on_click=pick,
                           args=(today - timedelta(days=1),))
        day = picker.date_input('Ngày', key='home_rev_day', label_visibility='collapsed', format='DD/MM/YYYY')
        info = day_revenue(day)
        pending = _pending_shifts(day)
        if info['source'] == 'Chưa có dữ liệu':
            st.info(f'Chưa có dữ liệu doanh thu ghi nhận cho ngày {day:%d/%m/%Y}.')
        cards = [
            ('Tổng thực thu', money(info['effective_revenue_vnd']) if info['source'] != 'Chưa có dữ liệu' else 'Chưa phát sinh',
             f"Nguồn: {info['source']}"),
            ('Doanh thu máy POS', money(info['slip_pos_revenue_vnd'] or info['pos_sku_revenue_vnd']),
             f"{info['quantity_sold']:,} ly".replace(',', '.') if info['quantity_sold'] else 'Từ phiếu POS ca tối hoặc file bán hàng'),
            ('Chênh lệch đối soát', money(info['variance_vnd']).replace('-', '−'),
             'Thực thu chốt ca so với POS' if info['variance_vnd'] else '—'),
            ('Tiền mặt / Chuyển khoản / App', f"{money(info['cash_vnd'])}",
             f"CK {money(info['bank_vnd'])} · App {money(info['apps_vnd'])}"),
        ]
        st.markdown('<section class="px-kpis">' + ''.join(
            f'<div class="px-kpi"><small>{escape(a)}</small><b class="px-num">{escape(b)}</b><span>{escape(c)}</span></div>'
            for a, b, c in cards) + '</section>', unsafe_allow_html=True)
        chips = []
        for code in SHIFTS:
            if info['shifts'].get(code):
                state, text = 'ok', 'Đã duyệt'
            elif code in pending:
                state, text = 'warn', 'Đang chờ duyệt'
            else:
                state, text = 'unk', 'Chưa chốt'
            chips.append(f'<span class="px-shift-chip"><b>{SHIFT_NAMES[code]}</b> <span class="vocr-badge vocr-{state}">{text}</span></span>')
        st.markdown('<div class="px-shift-chips">' + ''.join(chips) + '</div>', unsafe_allow_html=True)
        week = daily_revenue(day - timedelta(days=6), day, include_empty=True)
        if week['effective_revenue_vnd'].sum() > 0:
            st.caption('7 ngày tính đến ngày đang xem')
            _chart(week.rename(columns={'business_date': 'Ngày', 'effective_revenue_vnd': 'Thực thu'}), 'Ngày', 'Thực thu', height=180)


def render_revenue_report() -> None:
    """'Thống kê doanh thu' tab: a date range (this month by default) from approved shifts and POS sales."""
    today = business_today()
    first = today.replace(day=1)
    last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    picked = st.date_input('Khoảng ngày', value=(first, min(last, today)), key='rev_range', format='DD/MM/YYYY')
    start, end = (picked if isinstance(picked, (list, tuple)) and len(picked) == 2 else (first, today))
    frame = daily_revenue(start, end)
    if frame.empty or frame['effective_revenue_vnd'].sum() == 0:
        st.info('Chưa có dữ liệu doanh thu thực tế trong khoảng thời gian đã chọn.')
        return
    total = frame['effective_revenue_vnd'].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Tổng thực thu', money(total))
    c2.metric('Số ngày có số liệu', f'{len(frame)} ngày')
    c3.metric('Bình quân mỗi ngày', money(total / len(frame)))
    c4.metric('Ngày có chốt ca', f"{int((frame['shift_count'] > 0).sum())} ngày")
    _chart(frame.rename(columns={'business_date': 'Ngày', 'effective_revenue_vnd': 'Thực thu'}), 'Ngày', 'Thực thu', height=260)
    table = pd.DataFrame({
        'Ngày': pd.to_datetime(frame['business_date']).dt.strftime('%d/%m/%Y'),
        'Thực thu chốt ca': frame['shift_collected_vnd'].map(lambda v: money(v) if v else '—'),
        'Tiền mặt': frame['cash_vnd'].map(lambda v: money(v) if v else '—'),
        'Chuyển khoản': frame['bank_vnd'].map(lambda v: money(v) if v else '—'),
        'App giao hàng': frame['apps_vnd'].map(lambda v: money(v) if v else '—'),
        'Doanh thu POS': frame.apply(lambda r: money(r['slip_pos_revenue_vnd'] or r['pos_sku_revenue_vnd'])
                                     if (r['slip_pos_revenue_vnd'] or r['pos_sku_revenue_vnd']) else '—', axis=1),
        'Số ly': frame['quantity_sold'].map(lambda v: f'{v:,}'.replace(',', '.') if v else '—'),
        'Chênh lệch': frame['variance_vnd'].map(lambda v: money(v).replace('-', '−') if v else '—'),
        'Ghi nhận theo': frame['source'],
        'Doanh thu ghi nhận': frame['effective_revenue_vnd'].map(money),
    }).iloc[::-1]
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.caption('Không cộng trùng: ngày có chốt ca đã duyệt ghi nhận theo số tiền bàn giao; ngày chỉ có file bán hàng '
               'ghi nhận theo máy POS. Cột Chênh lệch là thực thu chốt ca trừ doanh thu POS.')
