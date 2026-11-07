"""Purchase order life cycle after the AI drafts it.

    AI draft (PENDING_APPROVAL) ──manager edits quantities──► same draft, lines marked as edited
          │ manager / owner approves (tool_approve_plan)
          ▼
    APPROVED — waiting for goods; expected on approval day + lead time
          │ "Đã nhận hàng": actual cartons per line (may differ from ordered)
          ▼
    RECEIVED — one stock-in slip per line written to the stock ledger (approved at once for a manager/owner,
               waiting for a manager if a staff member records the delivery)

Quantities are whole cartons/packs (Mixue ships whole cartons); the ledger counts the same units.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

from src.auth import is_admin_role
from src.engine.plan_service import get_plan, save_plan

MAX_PACKS = 999


def _clean_packs(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError('Số thùng phải là số.')
    if not math.isfinite(number) or number < 0 or number > MAX_PACKS or number != int(number):
        raise ValueError(f'Số thùng phải là số nguyên từ 0 đến {MAX_PACKS}.')
    return int(number)


def _set_packs(line: dict, packs: int) -> None:
    line['packs_to_order'] = packs
    line['recommended_order_qty'] = packs * float(line.get('pack_size') or 1)
    line['display_order'] = f"{packs} {line.get('carton_unit') or 'thùng'}"


def expected_arrival(plan: dict) -> date | None:
    if not plan.get('approved_at'):
        return None
    approved = datetime.fromisoformat(str(plan['approved_at'])).date()
    return approved + timedelta(days=int(plan.get('lead_time_days') or 2))


def update_quantities(plan_id: str, packs_by_ingredient: dict[str, Any], user_name: str, user_role: str) -> tuple[bool, str]:
    """Manager/owner changes how many cartons to order before approving. AI numbers are kept for the record."""
    if not is_admin_role(user_role):
        return False, 'Chỉ Quản lý / Chủ quán được sửa số lượng đơn đặt hàng.'
    plan = get_plan(plan_id)
    if not plan or plan.get('plan_type') != 'REPLENISHMENT_PO':
        return False, 'Không tìm thấy đơn đặt hàng.'
    if plan.get('status') != 'PENDING_APPROVAL':
        return False, 'Đơn đã duyệt hoặc đã đóng; không sửa số lượng được nữa.'
    try:
        wanted = {str(k): _clean_packs(v) for k, v in packs_by_ingredient.items()}
    except ValueError as exc:
        return False, str(exc)
    changed = []
    for line in plan['lines']:
        ing = str(line['ingredient_id'])
        if ing not in wanted or wanted[ing] == int(line.get('packs_to_order') or 0):
            continue
        line.setdefault('ai_packs', int(line.get('packs_to_order') or 0))
        _set_packs(line, wanted[ing])
        line['edited'] = line['packs_to_order'] != line['ai_packs']
        changed.append(f"{line['ingredient_name']}: {line['ai_packs']} → {line['packs_to_order']} {line.get('carton_unit', 'thùng')}")
    if not changed:
        return True, 'Không có thay đổi.'
    if not any(int(line.get('packs_to_order') or 0) > 0 for line in plan['lines']):
        return False, 'Đơn phải có ít nhất một mặt hàng.'
    plan.setdefault('edits', []).append({'by': f'{user_name} ({user_role})', 'at': datetime.now().isoformat(timespec='seconds'),
                                         'changes': changed})
    save_plan(plan)
    return True, 'Đã lưu: ' + '; '.join(changed)


def receive(plan_id: str, received_by_ingredient: dict[str, Any], received_on: date, username: str,
            user_role: str, note: str = '') -> tuple[bool, str, list[dict]]:
    """Goods arrived: write one stock-in slip per line with the cartons actually received."""
    from src.engine.daily_stock_service import create_stock_request
    plan = get_plan(plan_id)
    if not plan or plan.get('plan_type') != 'REPLENISHMENT_PO':
        return False, 'Không tìm thấy đơn đặt hàng.', []
    if plan.get('status') == 'RECEIVED':
        return False, f"Đơn này đã nhận hàng lúc {plan.get('received_at', '')[:16].replace('T', ' ')}.", []
    if plan.get('status') != 'APPROVED':
        return False, 'Chỉ nhận hàng cho đơn đã được Quản lý duyệt.', []
    if received_on > date.today() + timedelta(days=1):
        return False, 'Ngày nhận hàng không được ở tương lai.', []
    try:
        received = {str(k): _clean_packs(v) for k, v in received_by_ingredient.items()}
    except ValueError as exc:
        return False, str(exc), []
    lines = [line for line in plan['lines'] if received.get(str(line['ingredient_id']), 0) > 0]
    if not lines:
        return False, 'Chưa có mặt hàng nào được nhận (số thùng đều bằng 0).', []
    slips = []
    for line in lines:
        qty = received[str(line['ingredient_id'])]
        result = create_stock_request(
            business_date=received_on, ingredient_id=str(line['ingredient_id']), movement_type='IN', quantity=float(qty),
            recorded_by=username, user_role=user_role,
            notes=f"Nhận hàng đơn {plan_id} (đặt {int(line.get('packs_to_order') or 0)}, nhận {qty} {line.get('carton_unit', 'thùng')})"
                  + (f' · {note}' if note else ''))
        if result.get('status') not in {'SUCCESS'}:
            return False, f"{line['ingredient_name']}: {result.get('message', 'không ghi được phiếu kho')}", slips
        slips.append({'ingredient_id': str(line['ingredient_id']), 'ingredient_name': line['ingredient_name'],
                      'ordered': int(line.get('packs_to_order') or 0), 'received': qty,
                      'request_id': result.get('request_id'), 'approved': bool(result.get('is_approved'))})
    plan.update(status='RECEIVED', received_at=datetime.now().isoformat(timespec='seconds'), received_on=received_on.isoformat(),
                received_by=f'{username} ({user_role})', received_lines=slips, receive_note=note)
    save_plan(plan)
    short = [s for s in slips if s['received'] < s['ordered']]
    waiting = not is_admin_role(user_role)
    message = (f"Đã nhận {len(slips)} mặt hàng của đơn {plan_id}. "
               + ('Phiếu nhập kho đang chờ Quản lý duyệt.' if waiting else 'Đã cộng vào sổ kho.')
               + (f" Thiếu so với đơn: {', '.join(s['ingredient_name'] for s in short)}." if short else ''))
    return True, message, slips
