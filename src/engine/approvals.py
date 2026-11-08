"""Everything waiting for a manager — shift reports, stock slips, prep plans and purchase orders — and the
approve/reject action. Shared by the Streamlit approval center and the REST API (no UI code here).

Shift reports are approved through the agent (draft → approval step → write), stock slips through the stock
service, plans through the plan approval tool; nothing is written for a rejected item.
"""
from __future__ import annotations

from html import escape

from src.engine.daily_stock_service import approve_stock_request, get_pending_requests, reject_stock_request
from src.engine.plan_service import list_plans, reject_plan


SHIFT_NAMES = {'CA_SANG': 'Ca sáng', 'CA_CHIEU': 'Ca chiều', 'CA_TOI': 'Ca tối'}


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
    from src.engine.stock_matrix import today_vn
    today = today_vn().isoformat()
    for plan in list_plans():
        # A plan for a day that has passed can no longer be carried out; it is history, not work.
        # Topping prep plans are advice for the bar, never waiting on a manager (older ones were saved as pending).
        if (plan.get('status') != 'PENDING_APPROVAL' or plan.get('plan_type') == 'TOPPING_PREPARATION'
                or str(plan.get('target_date', ''))[:10] < today):
            continue
        if plan.get('plan_type') == 'STAFF_SCHEDULE':
            week = plan['schedule']
            check = plan.get('verification') or {}
            items.append({
                'kind': 'plan', 'id': plan['plan_id'],
                'title': f"📅 Lịch làm tuần {_date(week['week_start'])[:5]} – {_date(week['week_end'])}",
                'detail': (f"Mã {plan['plan_id']} · AI xếp, chờ duyệt để gửi cho nhân viên"
                           + (f" · ⚠️ {len(check.get('warnings', []))} lưu ý" if check.get('warnings') else '')),
            })
            continue
        kind_label = 'Đơn đặt hàng nguyên liệu' if plan.get('plan_type') == 'REPLENISHMENT_PO' else 'Kế hoạch'
        items.append({
            'kind': 'plan', 'id': plan['plan_id'],
            'title': f"{kind_label} · {_date(plan.get('target_date'))}",
            'detail': f"Mã {plan['plan_id']} · tạo lúc {str(plan.get('created_at', ''))[:16].replace('T', ' ')}",
        })
    return items


def decide(agent, items, approve: bool, user_role, user_name, user_id) -> list[str]:
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
