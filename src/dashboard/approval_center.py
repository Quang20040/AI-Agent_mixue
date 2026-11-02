"""One list of everything waiting for a manager: shift reports, stock slips, prep plans and orders.

Managers tick several items and approve or reject them together, or decide one at a time. Shift reports are
approved through the agent (draft → approval step → write), stock slips through the stock service, plans
through the plan approval tool; nothing is written for a rejected item.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from src.engine.daily_stock_service import approve_stock_request, get_pending_requests, reject_stock_request
from src.engine.plan_service import list_plans, reject_plan

SHIFT_NAMES = {'CA_SANG': 'Ca sáng', 'CA_CHIEU': 'Ca chiều', 'CA_TOI': 'Ca tối'}
KINDS = {'shift': '📸 Chốt ca', 'stock': '📦 Nhập / xuất kho', 'plan': '📋 Kế hoạch & đặt hàng'}


def money(value) -> str:
    return '—' if value is None else f"{float(value):,.0f} đ".replace(',', '.')


def _date(text) -> str:
    text = str(text or '')[:10]
    return f'{text[8:10]}/{text[5:7]}/{text[:4]}' if len(text) == 10 else (text or '—')


def pending_items(agent, user_role: str, user_name: str, user_id: str) -> list[dict]:
    """Everything waiting for this store's manager, newest first within each kind."""
    items = []
    for sub in agent.list_staff_submissions(user_role, user_name, user_id=user_id) if agent else []:
        fields, meta = sub.get('fields') or {}, sub.get('meta') or {}
        warnings = len((sub.get('consistency') or {}).get('discrepancies') or [])
        items.append({
            'kind': 'shift', 'id': sub['draft_id'],
            'title': f"{SHIFT_NAMES.get(sub.get('shift_code'), sub.get('shift_code'))} · {_date(sub.get('business_date'))}",
            'detail': (f"Gửi bởi {meta.get('submitted_by_name') or sub.get('user_id')} · lúc {str(meta.get('submitted_at', ''))[11:16]} · "
                       f"Tiền mặt {money(fields.get('cash_vnd'))} · CK {money(fields.get('bank_transfer_vnd'))} · "
                       f"App {money(sum(fields.get(k) or 0 for k in ('shopee_food_vnd', 'grab_food_vnd', 'be_food_vnd')))} · "
                       f"<b>Tổng thực thu {money(fields.get('total_collected_vnd'))}</b>"
                       + (f" · ⚠️ {warnings} cảnh báo lệch" if warnings else '')),
        })
    for req in get_pending_requests():
        items.append({
            'kind': 'stock', 'id': str(req['id']),
            'title': f"{req['type_vi']} · {escape(str(req['ingredient_name']))}",
            'detail': (f"Số lượng {req['quantity']:g} · ngày {_date(req['business_date'])} · đề xuất bởi {escape(str(req['recorded_by']))}"
                       + (f" · {escape(str(req['notes']))}" if req.get('notes') and req['notes'] != '—' else '')),
        })
    from src.dashboard.sales_view import business_today
    today = business_today().isoformat()
    for plan in list_plans():
        # A plan for a day that has passed can no longer be carried out; it is history, not work.
        if plan.get('status') != 'PENDING_APPROVAL' or str(plan.get('target_date', ''))[:10] < today:
            continue
        kind_label = 'Đơn đặt hàng nguyên liệu' if plan.get('plan_type') == 'REPLENISHMENT_PO' else 'Kế hoạch nấu topping'
        items.append({
            'kind': 'plan', 'id': plan['plan_id'],
            'title': f"{kind_label} · {_date(plan.get('target_date'))}",
            'detail': f"Mã {plan['plan_id']} · tạo lúc {str(plan.get('created_at', ''))[:16].replace('T', ' ')}",
        })
    return items


def _decide(agent, items, approve: bool, user_role, user_name, user_id) -> list[str]:
    messages = []
    shift_ids = [item['id'] for item in items if item['kind'] == 'shift']
    if shift_ids:
        for result in agent.decide_submissions(shift_ids, approve, user_role, user_name, user_id=user_id,
                                               reason='' if approve else 'Quản lý từ chối'):
            messages.append(('✅ ' if result['ok'] else '⚠️ ') + result['text'])
    for item in items:
        if item['kind'] == 'stock':
            ok, msg = (approve_stock_request(int(item['id']), admin_username=user_id) if approve
                       else reject_stock_request(int(item['id']), admin_username=user_id, reason='Quản lý từ chối'))
            messages.append(('✅ ' if ok else '⚠️ ') + msg)
        elif item['kind'] == 'plan':
            if approve:
                res = agent.tool_approve_plan(item['id'], user_role=user_role, user_name=user_name)
                ok, msg = bool(res.get('is_approved')), res.get('message', '')
            else:
                ok, msg = reject_plan(item['id'], user_id, 'Quản lý từ chối')
            messages.append(('✅ ' if ok else '⚠️ ') + msg)
    return messages


def render_approval_center(agent, user_role: str, user_name: str, *, kinds=('shift', 'stock', 'plan'), key: str = 'home') -> None:
    """Queue with filters, one checkbox per item, per-item buttons and batch approve/reject."""
    user_id = st.session_state.get('username', user_name)
    items = [item for item in pending_items(agent, user_role, user_name, user_id) if item['kind'] in kinds]
    with st.container(border=True, key=f'approval_center_{key}'):
        st.markdown(f'<div class="px-card-title">🗂️ Hàng đợi chờ phê duyệt · {len(items)}</div>', unsafe_allow_html=True)
        if notes := st.session_state.pop(f'approval_results_{key}', None):
            for note in notes:
                (st.success if note.startswith('✅') else st.warning)(note)
        if not items:
            st.caption('Hiện chưa có yêu cầu nào chờ phê duyệt.')
            return
        counts = {kind: sum(1 for item in items if item['kind'] == kind) for kind in kinds}
        options = ['all', *[kind for kind in kinds if counts[kind]]]
        labels = {'all': f'Tất cả ({len(items)})', **{kind: f'{KINDS[kind]} ({counts[kind]})' for kind in kinds}}
        chosen = 'all'
        if len(options) > 2:
            chosen = st.segmented_control('Lọc', options, format_func=labels.get, default='all',
                                          key=f'approval_filter_{key}', label_visibility='collapsed') or 'all'
        shown = [item for item in items if chosen == 'all' or item['kind'] == chosen]

        def box_key(item):
            return f"apv_{key}_{item['kind']}_{item['id']}"

        def select_all(value: bool):
            for item in shown:
                st.session_state[box_key(item)] = value

        def run(selected, approve):
            st.session_state[f'approval_results_{key}'] = _decide(agent, selected, approve, user_role, user_name, user_id)
            for item in selected:
                st.session_state.pop(box_key(item), None)

        selected = [item for item in shown if st.session_state.get(box_key(item))]
        bar = st.columns([1.1, 1.6, 1.6], gap='small')
        all_on = shown and len(selected) == len(shown)
        bar[0].button('☐ Bỏ chọn' if all_on else '☑️ Chọn tất cả', key=f'apv_all_{key}', use_container_width=True,
                      on_click=select_all, args=(not all_on,))
        bar[1].button(f'✅ Duyệt các khoản đã chọn ({len(selected)})', key=f'apv_ok_{key}', type='primary',
                      use_container_width=True, disabled=not selected, on_click=run, args=(selected, True))
        bar[2].button(f'❌ Từ chối các khoản đã chọn ({len(selected)})', key=f'apv_no_{key}',
                      use_container_width=True, disabled=not selected, on_click=run, args=(selected, False))
        limit_key = f'apv_show_all_{key}'
        visible = shown if st.session_state.get(limit_key) or len(shown) <= 10 else shown[:10]
        for item in visible:
            with st.container(border=True, key=f"apv_row_{key}_{item['kind']}_{item['id']}"):
                tick, body, yes, no = st.columns([0.35, 5, 1, 1], vertical_alignment='center')
                tick.checkbox('Chọn', key=box_key(item), label_visibility='collapsed')
                body.markdown(f"<small>{KINDS[item['kind']]}</small><br><b>{item['title']}</b><br>"
                              f"<small>{item['detail']}</small>", unsafe_allow_html=True)
                yes.button('✅ Duyệt', key=f"apv_y_{key}_{item['kind']}_{item['id']}", use_container_width=True,
                           on_click=run, args=([item], True))
                no.button('❌ Từ chối', key=f"apv_n_{key}_{item['kind']}_{item['id']}", use_container_width=True,
                          on_click=run, args=([item], False))
        if len(visible) < len(shown):
            st.button(f'Xem thêm {len(shown) - len(visible)} khoản', key=f'apv_more_{key}',
                      on_click=lambda: st.session_state.update({limit_key: True}))


def render_my_submissions(agent, user_role: str, user_name: str) -> None:
    """Staff: the reports I sent and their status."""
    user_id = st.session_state.get('username', user_name)
    subs = agent.list_my_submissions(user_role, user_name, user_id=user_id) if agent else []
    with st.container(border=True, key='my_submissions'):
        st.markdown('<div class="px-card-title">📨 Báo cáo chốt ca bạn đã gửi</div>', unsafe_allow_html=True)
        if not subs:
            st.caption('Bạn chưa gửi báo cáo chốt ca nào.')
            return
        status = {'SUBMITTED': ('⏳ Chờ duyệt', 'warn'), 'APPROVED': ('✅ Đã duyệt', 'ok'), 'FORWARDED': ('⏳ Quản lý đang duyệt', 'warn'),
                  'REJECTED': ('❌ Từ chối', 'bad'), 'SUPERSEDED': ('↺ Đã thay bằng bản mới', 'unk')}
        rows = []
        for sub in subs:
            text, tone = status.get(sub.get('status'), (sub.get('status'), 'unk'))
            total = (sub.get('fields') or {}).get('total_collected_vnd')
            rows.append(f"<li><b>{SHIFT_NAMES.get(sub.get('shift_code'), sub.get('shift_code'))} · {_date(sub.get('business_date'))}</b> · "
                        f"{money(total)} <span class='vocr-badge vocr-{tone}'>{text}</span></li>")
        st.markdown('<ul class="px-sub-list">' + ''.join(rows) + '</ul>', unsafe_allow_html=True)
