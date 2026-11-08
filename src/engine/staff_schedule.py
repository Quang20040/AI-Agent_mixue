"""Weekly work schedule: the manager sets each person's main shift and the shifts they are busy, the AI fills
the week, the manager checks/edits and approves, then every staff member sees it.

Rules (hard — a schedule that breaks one cannot be approved):
  * nobody is put on a shift they said they are busy for (or a day they are busy all day);
  * at most 2 shifts a day per person, and two shifts must be next to each other (sáng+chiều or chiều+tối);
  * only active official and probation staff are scheduled (managers and the owner are not).
Preferences (soft): main shift first, spread shifts evenly over the week, at least one official staff member
on every shift when possible. Ties are broken at random (seeded), so "Xếp lại" gives a different fair week.
Needs per shift default to sáng 1 · chiều 2 · tối 2 and can be changed day by day.
"""
from __future__ import annotations

import random
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from src.database import Base, SessionLocal, engine
from src.models import ScheduleResponse, StaffShiftPreference, StaffUnavailability, User

Base.metadata.create_all(bind=engine)

SHIFTS = ('CA_SANG', 'CA_CHIEU', 'CA_TOI')
SHIFT_VI = {'CA_SANG': 'Sáng', 'CA_CHIEU': 'Chiều', 'CA_TOI': 'Tối'}
DEFAULT_NEED = {'CA_SANG': 1, 'CA_CHIEU': 2, 'CA_TOI': 2}
ADJACENT = {frozenset(('CA_SANG', 'CA_CHIEU')), frozenset(('CA_CHIEU', 'CA_TOI'))}
WEEKDAY_VI = ('T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN')
PLAN_TYPE = 'STAFF_SCHEDULE'
# Cell values in the per-person grid (what the manager picks when editing).
CELL_OPTIONS = {'—': (), 'Sáng': ('CA_SANG',), 'Chiều': ('CA_CHIEU',), 'Tối': ('CA_TOI',),
                'Sáng + Chiều': ('CA_SANG', 'CA_CHIEU'), 'Chiều + Tối': ('CA_CHIEU', 'CA_TOI')}
STAFF_ROLES = {'STAFF_OFFICIAL', 'STAFF', 'STAFF_PROBATION', 'PROBATION', 'TRAINEE'}


def week_start(day: date | None = None) -> date:
    day = day or date.today()
    return day - timedelta(days=day.weekday())


def week_days(start: date) -> list[date]:
    return [start + timedelta(days=i) for i in range(7)]


def day_label(d: date) -> str:
    return f'{WEEKDAY_VI[d.weekday()]} {d:%d/%m}'


def parse_shift(text: str | None) -> str | None:
    """'ca sáng' / 'sang' / 'CA_SANG' / 'morning' → CA_SANG. None/'' → None (= whole day / no main shift)."""
    if not text:
        return None
    import unicodedata
    t = unicodedata.normalize('NFD', str(text)).encode('ascii', 'ignore').decode().lower().replace('_', ' ')
    for code, words in (('CA_SANG', ('sang', 'morning')), ('CA_CHIEU', ('chieu', 'afternoon')), ('CA_TOI', ('toi', 'evening', 'night'))):
        if any(w in t.split() for w in words) or t.strip() == code.lower().replace('_', ' '):
            return code
    raise ValueError(f"Không hiểu ca '{text}'. Dùng: sáng, chiều hoặc tối.")


# --- people, main shifts, busy days ---------------------------------------------------------------------------

def employees() -> list[dict[str, Any]]:
    """Active staff that can be scheduled: official first, then probation."""
    with SessionLocal() as db:
        rows = db.query(User).filter(User.is_active.is_(True)).all()
        prefs = {p.username: p.main_shift for p in db.query(StaffShiftPreference).all()}
    out = []
    for u in rows:
        role = (u.role or '').upper()
        if role not in STAFF_ROLES:
            continue
        official = role in {'STAFF_OFFICIAL', 'STAFF'}
        out.append({'username': u.username, 'full_name': u.full_name, 'official': official,
                    'role_vi': 'Chính thức' if official else 'Thử việc', 'main_shift': prefs.get(u.username)})
    return sorted(out, key=lambda e: (not e['official'], e['full_name']))


def find_employee(name: str) -> dict[str, Any]:
    """Match a username or (part of) a full name, accents optional. Raises if none or ambiguous."""
    import unicodedata

    def norm(s):
        return unicodedata.normalize('NFD', str(s or '')).encode('ascii', 'ignore').decode().lower().replace('đ', 'd').strip()
    q = norm(name).lstrip('@')
    people = employees()
    exact = [e for e in people if q in {norm(e['username']), norm(e['full_name'])}]
    if len(exact) == 1:
        return exact[0]
    partial = [e for e in people if q and (q in norm(e['full_name']) or q == norm(e['full_name']).split()[-1])]
    if len(partial) == 1:
        return partial[0]
    if not partial:
        raise ValueError(f"Không tìm thấy nhân viên '{name}'. Nhân viên: " + ', '.join(e['full_name'] for e in people))
    raise ValueError(f"'{name}' trùng nhiều người: " + ', '.join(e['full_name'] for e in partial) + '. Nói rõ họ tên.')


def set_main_shift(username: str, shift: str | None, by: str = '') -> None:
    with SessionLocal() as db:
        row = db.get(StaffShiftPreference, username) or StaffShiftPreference(username=username)
        row.main_shift, row.updated_by = shift, by
        db.merge(row)
        db.commit()


def add_busy(username: str, days: list[date], shift: str | None = None, reason: str = '', by: str = '') -> int:
    with SessionLocal() as db:
        existing = {(r.work_date, r.shift_code) for r in db.query(StaffUnavailability).filter(
            StaffUnavailability.username == username, StaffUnavailability.work_date.in_(days))}
        added = 0
        for d in days:
            if (d, shift) in existing or (d, None) in existing:
                continue
            db.add(StaffUnavailability(username=username, work_date=d, shift_code=shift, reason=(reason or '')[:200], created_by=by))
            added += 1
        db.commit()
    for week in {week_start(d) for d in days}:
        _respond(username, week, 'BUSY_REPORTED')
    return added


def remove_busy(busy_id: int) -> bool:
    with SessionLocal() as db:
        row = db.get(StaffUnavailability, busy_id)
        if row is None:
            return False
        db.delete(row)
        db.commit()
    return True


def busy_list(start: date, end: date) -> list[dict[str, Any]]:
    names = {e['username']: e['full_name'] for e in employees()}
    with SessionLocal() as db:
        rows = db.query(StaffUnavailability).filter(StaffUnavailability.work_date >= start,
                                                    StaffUnavailability.work_date <= end).order_by(StaffUnavailability.work_date).all()
        return [{'id': r.id, 'username': r.username, 'full_name': names.get(r.username, r.username), 'date': r.work_date,
                 'shift': r.shift_code, 'reason': r.reason or ''} for r in rows]


# --- the schedule -------------------------------------------------------------------------------------------

def default_needs(start: date) -> dict[str, dict[str, int]]:
    return {d.isoformat(): dict(DEFAULT_NEED) for d in week_days(start)}


def _busy_map(start):
    out = defaultdict(set)
    for b in busy_list(start, start + timedelta(days=6)):
        out[(b['username'], b['date'].isoformat())].add(b['shift'])   # None = all day
    return out


def _is_busy(busy, user, day, shift):
    s = busy.get((user, day), set())
    return None in s or shift in s


def generate(start: date, needs: dict[str, dict[str, int]] | None = None, seed: int | None = None) -> dict[str, Any]:
    """Fill the week. Returns {'assignments': {day: {shift: [username]}}, 'needs', 'seed', ...}."""
    start = week_start(start)
    needs = needs or default_needs(start)
    seed = random.randrange(1, 10**6) if seed is None else seed
    rng = random.Random(seed)
    people = employees()
    info = {e['username']: e for e in people}
    busy = _busy_map(start)
    count = Counter()
    assignments = {}
    for d in week_days(start):
        day = d.isoformat()
        today = defaultdict(list)                           # user -> shifts already today
        slots = {s: [] for s in SHIFTS}
        need = {s: int(needs.get(day, DEFAULT_NEED).get(s, 0)) for s in SHIFTS}
        for rnd in range(max(need.values(), default=0)):
            order = [s for s in SHIFTS if need[s] > rnd]
            rng.shuffle(order)
            for shift in order:
                has_official = any(info[u]['official'] for u in slots[shift])
                best, best_score = None, None
                for e in people:
                    u = e['username']
                    if u in slots[shift] or _is_busy(busy, u, day, shift):
                        continue
                    mine = today[u]
                    if len(mine) >= 2 or (mine and frozenset((mine[0], shift)) not in ADJACENT):
                        continue
                    score = rng.random() * 0.8 - 1.0 * count[u]
                    score += 3.0 if e['main_shift'] == shift else (-0.5 if e['main_shift'] else 0.0)
                    score -= 2.5 if mine else 0.0                  # a second shift only when needed
                    if not has_official:
                        score += 2.0 if e['official'] else -2.0     # someone experienced on every shift
                    if best_score is None or score > best_score:
                        best, best_score = u, score
                if best:
                    slots[shift].append(best)
                    today[best].append(shift)
                    count[best] += 1
        assignments[day] = slots
    return {'week_start': start.isoformat(), 'week_end': (start + timedelta(days=6)).isoformat(),
            'needs': needs, 'assignments': assignments, 'seed': seed}


def check(schedule: dict[str, Any]) -> dict[str, Any]:
    """Hard violations (block approval) and warnings (shown to the manager)."""
    start = date.fromisoformat(schedule['week_start'])
    info = {e['username']: e for e in employees()}
    busy = _busy_map(start)
    violations, warnings = [], []
    for day, slots in schedule['assignments'].items():
        label = day_label(date.fromisoformat(day))
        per_user = defaultdict(list)
        for shift in SHIFTS:
            people = slots.get(shift, [])
            for u in people:
                per_user[u].append(shift)
                if u not in info:
                    violations.append(f'{label} · {SHIFT_VI[shift]}: “{u}” không còn là nhân viên được xếp lịch.')
                elif _is_busy(busy, u, day, shift):
                    violations.append(f"{label} · {SHIFT_VI[shift]}: {info[u]['full_name']} đã báo bận.")
            need = int(schedule['needs'].get(day, DEFAULT_NEED).get(shift, 0))
            if len(people) < need:
                warnings.append(f'{label} · ca {SHIFT_VI[shift].lower()}: thiếu {need - len(people)} người (cần {need}).')
            elif people and not any(info.get(u, {}).get('official') for u in people):
                warnings.append(f'{label} · ca {SHIFT_VI[shift].lower()}: chỉ có nhân viên thử việc.')
        for u, shifts in per_user.items():
            name = info.get(u, {}).get('full_name', u)
            if len(shifts) > 2:
                violations.append(f'{label}: {name} bị xếp {len(shifts)} ca (tối đa 2).')
            elif len(shifts) == 2 and frozenset(shifts) not in ADJACENT:
                violations.append(f'{label}: {name} làm 2 ca không liền nhau (sáng + tối).')
    totals = Counter(u for slots in schedule['assignments'].values() for people in slots.values() for u in people)
    return {'is_valid': not violations, 'violations': violations, 'warnings': warnings,
            'shifts_per_person': {info.get(u, {}).get('full_name', u): n for u, n in totals.most_common()}}


def to_grid(schedule: dict[str, Any]) -> list[dict[str, str]]:
    """One row per person, one column per day, cell = 'Sáng' / 'Chiều + Tối' / '—' (what the editor shows)."""
    start = date.fromisoformat(schedule['week_start'])
    rows = []
    for e in employees():
        row = {'username': e['username'], 'Nhân viên': e['full_name'], 'Loại': e['role_vi'],
               'Ca chính': SHIFT_VI.get(e['main_shift'], '—')}
        for d in week_days(start):
            mine = tuple(s for s in SHIFTS if e['username'] in schedule['assignments'].get(d.isoformat(), {}).get(s, []))
            row[day_label(d)] = next((k for k, v in CELL_OPTIONS.items() if v == mine), ' + '.join(SHIFT_VI[s] for s in mine))
        rows.append(row)
    return rows


def from_grid(schedule: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    start = date.fromisoformat(schedule['week_start'])
    out = {d.isoformat(): {s: [] for s in SHIFTS} for d in week_days(start)}
    for row in rows:
        for d in week_days(start):
            cell = row.get(day_label(d)) or '—'
            if cell not in CELL_OPTIONS:
                raise ValueError(f"Ô '{cell}' không hợp lệ.")
            for s in CELL_OPTIONS[cell]:
                out[d.isoformat()][s].append(row['username'])
    return {**schedule, 'assignments': out}


# --- drafts, approval, publishing ---------------------------------------------------------------------------

def _plans(status=None, start: date | None = None):
    from src.engine.plan_service import list_plans
    return [p for p in list_plans(PLAN_TYPE) if (status is None or p.get('status') == status)
            and (start is None or p['schedule']['week_start'] == start.isoformat())]


def create_draft(start: date, needs=None, seed=None, by: str = '') -> dict[str, Any]:
    """AI fills the week and saves it as a draft waiting for the manager (an older draft of the week is replaced)."""
    from src.engine.plan_service import save_plan
    schedule = generate(start, needs, seed)
    for old in _plans('PENDING_APPROVAL', week_start(start)):
        old['status'] = 'SUPERSEDED'
        save_plan(old)
    plan = {'plan_id': f"LICH-{schedule['week_start'].replace('-', '')}-{uuid.uuid4().hex[:4].upper()}",
            'plan_type': PLAN_TYPE, 'status': 'PENDING_APPROVAL', 'target_date': schedule['week_end'],
            'created_at': datetime.now().isoformat(timespec='seconds'), 'created_by': by,
            'schedule': schedule, 'verification': check(schedule), 'edits': []}
    save_plan(plan)
    return plan


def update_draft(plan_id: str, rows: list[dict[str, str]], by: str = '') -> dict[str, Any]:
    from src.engine.plan_service import get_plan, save_plan
    plan = get_plan(plan_id)
    if not plan or plan.get('plan_type') != PLAN_TYPE:
        raise ValueError('Không tìm thấy bản nháp lịch.')
    if plan['status'] != 'PENDING_APPROVAL':
        raise ValueError('Lịch đã duyệt hoặc đã bị thay, không sửa được nữa.')
    plan['schedule'] = from_grid(plan['schedule'], rows)
    plan['verification'] = check(plan['schedule'])
    plan['edits'] = [*plan.get('edits', []), {'by': by, 'at': datetime.now().isoformat(timespec='seconds')}]
    save_plan(plan)
    return plan


def pending(start: date) -> dict[str, Any] | None:
    plans = _plans('PENDING_APPROVAL', week_start(start))
    return max(plans, key=lambda p: p['created_at']) if plans else None


def published(start: date) -> dict[str, Any] | None:
    plans = _plans('APPROVED', week_start(start))
    return max(plans, key=lambda p: p.get('approved_at') or p['created_at']) if plans else None


def my_shifts(username: str, start: date) -> list[dict[str, Any]]:
    plan = published(start)
    if not plan:
        return []
    out = []
    for d in week_days(week_start(start)):
        shifts = [s for s in SHIFTS if username in plan['schedule']['assignments'].get(d.isoformat(), {}).get(s, [])]
        out.append({'date': d, 'label': day_label(d), 'shifts': shifts})
    return out


# --- weekly cycle: ask for busy days (Sat → Sun 18:00), then the AI drafts the week for the manager -------------
# Times are Vietnam local time. ASK_FROM_WEEKDAY 5 = Saturday; the deadline is Sunday at DEADLINE_HOUR.

import os  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

VN = ZoneInfo('Asia/Ho_Chi_Minh')
ASK_FROM_WEEKDAY = int(os.environ.get('SCHEDULE_ASK_FROM_WEEKDAY', 5))
DEADLINE_HOUR = int(os.environ.get('SCHEDULE_DEADLINE_HOUR', 18))


def shift_times() -> dict[str, tuple[str, str]]:
    """Start/end of each shift, e.g. SHIFT_TIMES="07:00-13:00,13:00-18:00,18:00-22:30"."""
    raw = os.environ.get('SHIFT_TIMES', '07:00-13:00,13:00-18:00,18:00-22:30').split(',')
    return {code: tuple(part.strip().split('-')) for code, part in zip(SHIFTS, raw)}


def now_vn() -> datetime:
    return datetime.now(VN)


def cycle(now: datetime | None = None) -> dict[str, Any]:
    """The collection round for next week: when it opens, its deadline, whether it is open / closed."""
    now = now or now_vn()
    target = week_start(now.date()) + timedelta(days=7)
    deadline = datetime.combine(target - timedelta(days=1), datetime.min.time(), VN).replace(hour=DEADLINE_HOUR)
    opens = datetime.combine(target - timedelta(days=7 - ASK_FROM_WEEKDAY), datetime.min.time(), VN)
    return {'target_week': target, 'opens': opens, 'deadline': deadline,
            'open': opens <= now < deadline, 'closed': now >= deadline}


def _respond(username: str, week: date, status: str) -> None:
    with SessionLocal() as db:
        row = db.get(ScheduleResponse, (username, week))
        if row is None:
            db.add(ScheduleResponse(username=username, week_start=week, status=status))
        elif row.status != 'BUSY_REPORTED' or status == 'BUSY_REPORTED':
            row.status = status
        db.commit()


def confirm_no_busy(username: str, week: date) -> None:
    """The staff member says they are free all next week (busy days already reported stay)."""
    with SessionLocal() as db:
        has_busy = db.query(StaffUnavailability).filter(StaffUnavailability.username == username,
                                                        StaffUnavailability.work_date >= week,
                                                        StaffUnavailability.work_date <= week + timedelta(days=6)).count()
    _respond(username, week_start(week), 'BUSY_REPORTED' if has_busy else 'NO_BUSY')


def responses(week: date) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        got = {r.username: r.status for r in db.query(ScheduleResponse).filter(ScheduleResponse.week_start == week_start(week))}
    return [{**e, 'response': got.get(e['username'])} for e in employees()]


def auto_schedule(now: datetime | None = None) -> dict[str, Any] | None:
    """After the deadline, draft next week once (staff who did not answer are taken as free). Idempotent:
    does nothing if any schedule — draft, approved or rejected — already exists for that week."""
    c = cycle(now)
    if not c['closed'] or not employees():
        return None
    from src.engine.plan_service import list_plans
    if any(p['schedule']['week_start'] == c['target_week'].isoformat() and p.get('status') != 'SUPERSEDED'
           for p in list_plans(PLAN_TYPE)):
        return None
    silent = [r['full_name'] for r in responses(c['target_week']) if not r['response']]
    plan = create_draft(c['target_week'], by='Tuyết Vương (tự động)')
    plan['auto'] = {'at': (now or now_vn()).isoformat(timespec='minutes'), 'no_answer': silent}
    from src.engine.plan_service import save_plan
    save_plan(plan)
    return plan


def reminders(username: str, now: datetime | None = None) -> list[dict[str, Any]]:
    """What to tell a staff member now: answer the busy-days round, and their next shift."""
    now = now or now_vn()
    out = []
    c = cycle(now)
    me = next((e for e in employees() if e['username'] == username), None)
    if me is None:
        return out
    if c['open']:
        answered = next((r['response'] for r in responses(c['target_week']) if r['username'] == username), None)
        if not answered:
            out.append({'kind': 'ask_busy', 'week': c['target_week'],
                        'text': (f"Báo ngày bận tuần {c['target_week']:%d/%m} – {c['target_week'] + timedelta(days=6):%d/%m} "
                                 f"trước {DEADLINE_HOUR}:00 Chủ nhật để Tuyết Vương xếp lịch. Không báo = coi như rảnh cả tuần.")})
    times = shift_times()
    for offset in (0, 1):
        day = now.date() + timedelta(days=offset)
        plan = published(day)
        if not plan:
            continue
        for s in SHIFTS:
            if username not in plan['schedule']['assignments'].get(day.isoformat(), {}).get(s, []):
                continue
            begin = datetime.combine(day, datetime.strptime(times[s][0], '%H:%M').time(), VN)
            end = datetime.combine(day, datetime.strptime(times[s][1], '%H:%M').time(), VN)
            if begin <= now < end:
                out.append({'kind': 'on_shift', 'text': f"Bạn đang trong ca {SHIFT_VI[s].lower()} ({times[s][0]}–{times[s][1]})."})
            elif timedelta(0) < begin - now <= timedelta(hours=3):
                mins = int((begin - now).total_seconds() // 60)
                out.append({'kind': 'shift_soon', 'text': f"Sắp đến ca {SHIFT_VI[s].lower()} lúc {times[s][0]} "
                                                          f"(còn {mins // 60} giờ {mins % 60} phút)." if mins >= 60 else
                                                          f"Sắp đến ca {SHIFT_VI[s].lower()} lúc {times[s][0]} (còn {mins} phút)."})
            elif offset == 1 and now.hour >= 17:
                out.append({'kind': 'tomorrow', 'text': f"Mai ({day_label(day)}) bạn làm ca {SHIFT_VI[s].lower()} lúc {times[s][0]}."})
    return out
