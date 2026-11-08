"""Agent tools for the weekly work schedule (see src/engine/staff_schedule.py).

Who may do what is decided from the authenticated actor, never from the chat text: staff can only report
their own busy days and read the published schedule; the manager sets main shifts, records busy days for
anyone, and has the AI draft a week — which still waits for approval before staff see it.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from src.auth import is_admin_role
from src.engine import staff_schedule as ss

SHIFT_FROM_VI = {'sáng': 'CA_SANG', 'chiều': 'CA_CHIEU', 'tối': 'CA_TOI'}


def _actor(service):
    actor = getattr(service, '_current_actor', None)
    if actor is None:
        raise PermissionError('Không xác định được người dùng.')
    return actor


def _today():
    from src.engine.stock_matrix import today_vn
    return today_vn()


def _grid_text(schedule) -> str:
    names = {e['username']: e['full_name'].split()[-1] for e in ss.employees()}
    lines = ['| Ngày | Sáng | Chiều | Tối |', '|---|---|---|---|']
    for d in ss.week_days(date.fromisoformat(schedule['week_start'])):
        slots = schedule['assignments'].get(d.isoformat(), {})
        cells = [', '.join(names.get(u, u) for u in slots.get(s, [])) or '—' for s in ss.SHIFTS]
        lines.append(f"| {ss.day_label(d)} | " + ' | '.join(cells) + ' |')
    return '\n'.join(lines)


def set_main_shift(service, employee: str, main_shift: str | None = None) -> dict[str, Any]:
    actor = _actor(service)
    if not is_admin_role(actor.role):
        return {'status': 'UNAUTHORIZED', 'message': 'Chỉ Quản lý / Chủ quán đặt ca chính cho nhân viên.'}
    try:
        person = ss.find_employee(employee)
    except ValueError as exc:
        return {'status': 'NOT_FOUND', 'message': str(exc)}
    ss.set_main_shift(person['username'], SHIFT_FROM_VI.get(main_shift), actor.name)
    return {'status': 'SUCCESS', 'employee': person['full_name'], 'main_shift': main_shift or 'không có',
            'message': f"Đã đặt ca chính của {person['full_name']}: {main_shift or 'không có'}.",
            'source_refs': ['table:staff_shift_preferences']}


def report_busy(service, start_date: date, end_date: date | None = None, shift: str | None = None,
                employee: str | None = None, reason: str = '') -> dict[str, Any]:
    actor = _actor(service)
    if employee and not is_admin_role(actor.role):
        try:
            if ss.find_employee(employee)['username'] != actor.user_id:
                return {'status': 'UNAUTHORIZED', 'message': 'Bạn chỉ báo bận được cho chính mình; nhờ Quản lý ghi cho người khác.'}
        except ValueError:
            return {'status': 'UNAUTHORIZED', 'message': 'Bạn chỉ báo bận được cho chính mình.'}
    try:
        person = ss.find_employee(employee) if employee else next(e for e in ss.employees() if e['username'] == actor.user_id)
    except StopIteration:
        return {'status': 'NOT_FOUND', 'message': 'Tài khoản của bạn không nằm trong danh sách được xếp lịch. Nói rõ tên nhân viên.'}
    except ValueError as exc:
        return {'status': 'NOT_FOUND', 'message': str(exc)}
    if start_date < _today():
        return {'status': 'INVALID', 'message': 'Ngày bận đã qua.'}
    days = [start_date + timedelta(days=i) for i in range(((end_date or start_date) - start_date).days + 1)]
    added = ss.add_busy(person['username'], days, SHIFT_FROM_VI.get(shift), reason, actor.name)
    when = f'{days[0]:%d/%m}' + (f' – {days[-1]:%d/%m}' if len(days) > 1 else '')
    return {'status': 'SUCCESS', 'employee': person['full_name'], 'days': [d.isoformat() for d in days],
            'shift': shift or 'cả ngày', 'added': added,
            'message': f"Đã ghi {person['full_name']} bận {('ca ' + shift) if shift else 'cả ngày'} {when}. "
                       'AI sẽ không xếp vào ca này; nếu lịch tuần đó đã công bố, Quản lý cần xếp lại.',
            'source_refs': ['table:staff_unavailability']}


def create_schedule(service, week_of: date | None = None, needs: list | None = None) -> dict[str, Any]:
    actor = _actor(service)
    if not is_admin_role(actor.role):
        return {'status': 'UNAUTHORIZED', 'message': 'Chỉ Quản lý / Chủ quán xếp lịch làm.'}
    start = ss.week_start(week_of or (_today() + timedelta(days=7)))
    if start + timedelta(days=6) < _today():
        return {'status': 'INVALID', 'message': 'Tuần này đã qua.'}
    table = ss.default_needs(start)
    for n in needs or []:
        n = n if isinstance(n, dict) else n.model_dump()
        day = n['day'] if isinstance(n['day'], date) else date.fromisoformat(str(n['day']))
        if ss.week_start(day) == start:
            table[day.isoformat()][SHIFT_FROM_VI[n['shift']]] = int(n['people'])
    if not ss.employees():
        return {'status': 'NO_DATA', 'message': 'Chưa có nhân viên chính thức / thử việc nào để xếp lịch.'}
    plan = ss.create_draft(start, table, by=actor.name)
    check = plan['verification']
    return {'status': 'PENDING_APPROVAL', 'plan_id': plan['plan_id'], 'week': f"{start:%d/%m} – {start + timedelta(days=6):%d/%m/%Y}",
            'schedule_table': _grid_text(plan['schedule']), 'warnings': check['warnings'],
            'shifts_per_person': check['shifts_per_person'],
            'message': (f"Đã xếp nháp lịch tuần {start:%d/%m}. Nhân viên CHƯA thấy lịch: Quản lý xem/sửa ở trang 📅 Lịch làm "
                        f"rồi bấm Duyệt & gửi (hoặc nói 'duyệt {plan['plan_id']}')."),
            'source_refs': ['table:users', 'table:staff_shift_preferences', 'table:staff_unavailability', f"plan:{plan['plan_id']}"]}


def view_schedule(service, week_of: date | None = None) -> dict[str, Any]:
    actor = _actor(service)
    start = ss.week_start(week_of or _today())
    out: dict[str, Any] = {'status': 'SUCCESS', 'week': f"{start:%d/%m} – {start + timedelta(days=6):%d/%m/%Y}",
                           'source_refs': ['table:operation_plans']}
    c = ss.cycle()
    out['busy_round'] = {'week': f"{c['target_week']:%d/%m}", 'deadline': f"{c['deadline']:%H:%M %d/%m}",
                         'open': c['open'], 'auto_schedule_after_deadline': True}
    if not is_admin_role(actor.role):
        out['reminders'] = [r['text'] for r in ss.reminders(actor.user_id)]
    else:
        rows = ss.responses(c['target_week'])
        out['busy_round']['answered'] = f"{sum(1 for r in rows if r['response'])}/{len(rows)}"
        out['busy_round']['not_answered'] = [r['full_name'] for r in rows if not r['response']]
    plan = ss.published(start)
    if plan:
        out['published_table'] = _grid_text(plan['schedule'])
        out['approved_by'] = plan.get('approved_by')
        mine = [d for d in ss.my_shifts(actor.user_id, start) if d['shifts']]
        if mine or not is_admin_role(actor.role):
            out['my_shifts'] = [f"{d['label']}: " + ' + '.join(ss.SHIFT_VI[s] for s in d['shifts']) for d in mine] or ['Không có ca nào.']
    else:
        out['published_table'] = None
        out['message'] = 'Tuần này chưa có lịch được duyệt.'
    if is_admin_role(actor.role):
        draft = ss.pending(start)
        if draft:
            out['draft'] = {'plan_id': draft['plan_id'], 'table': _grid_text(draft['schedule']),
                            'warnings': draft['verification']['warnings']}
        out['main_shifts'] = {e['full_name']: ss.SHIFT_VI.get(e['main_shift'], '—') for e in ss.employees()}
        out['busy'] = [f"{b['full_name']}: {b['date']:%d/%m} " + (ss.SHIFT_VI[b['shift']].lower() if b['shift'] else 'cả ngày')
                       + (f" ({b['reason']})" if b['reason'] else '') for b in ss.busy_list(start, start + timedelta(days=6))]
    elif not plan:
        out['status'] = 'NO_DATA'
    return out


def confirm_free(service) -> dict[str, Any]:
    """The signed-in staff member says they have no busy days next week."""
    actor = _actor(service)
    c = ss.cycle()
    if not any(e['username'] == actor.user_id for e in ss.employees()):
        return {'status': 'NOT_FOUND', 'message': 'Tài khoản của bạn không nằm trong danh sách được xếp lịch.'}
    ss.confirm_no_busy(actor.user_id, c['target_week'])
    return {'status': 'SUCCESS', 'week': f"{c['target_week']:%d/%m}",
            'message': f"Đã ghi nhận bạn rảnh tuần {c['target_week']:%d/%m} (những ngày bận đã báo vẫn giữ).",
            'source_refs': ['table:schedule_responses']}
