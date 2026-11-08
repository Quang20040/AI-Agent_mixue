"""Weekly schedule: main shifts preferred, busy shifts respected, ≤2 adjacent shifts/day, manager approves."""
from datetime import date, timedelta

import pytest

from src.database import SessionLocal
from src.engine import staff_schedule as ss
from src.models import StaffShiftPreference, StaffUnavailability, User

WEEK = date(2026, 11, 16)   # a Monday
PEOPLE = [('lich_an', 'Nguyễn Văn An', 'STAFF_OFFICIAL', 'CA_SANG'), ('lich_binh', 'Trần Thị Bình', 'STAFF_OFFICIAL', 'CA_CHIEU'),
          ('lich_cuong', 'Lê Văn Cường', 'STAFF_OFFICIAL', 'CA_TOI'), ('lich_dung', 'Phạm Thu Dung', 'STAFF_OFFICIAL', None),
          ('lich_em', 'Hoàng Văn Em', 'STAFF_PROBATION', 'CA_TOI'), ('lich_giang', 'Vũ Thị Giang', 'STAFF_PROBATION', 'CA_CHIEU')]


def _drop_schedules(db):
    from src.engine import plan_service
    from src.models import OperationPlan
    db.query(OperationPlan).filter(OperationPlan.plan_id.like('LICH-%')).delete(synchronize_session=False)
    plan_service._invalidate()


@pytest.fixture()
def staff():
    with SessionLocal() as db:
        _drop_schedules(db)
        db.query(StaffUnavailability).delete()
        db.query(StaffShiftPreference).delete()
        others = db.query(User).filter(User.role.in_(['STAFF_OFFICIAL', 'STAFF', 'STAFF_PROBATION'])).all()
        saved = [(u.username, u.is_active) for u in others]
        for u in others:
            u.is_active = False
        for username, name, role, _ in PEOPLE:
            db.merge(User(username=username, password_hash='x', full_name=name, role=role, is_active=True))
        db.commit()
    for username, _, _, shift in PEOPLE:
        ss.set_main_shift(username, shift, 'test')
    yield
    with SessionLocal() as db:
        for username, active in saved:
            db.get(User, username).is_active = active
        for username, *_ in PEOPLE:
            db.query(User).filter(User.username == username).delete()
        db.query(StaffUnavailability).delete()
        db.query(StaffShiftPreference).delete()
        _drop_schedules(db)
        db.commit()


def test_parse_shift_and_find_employee(staff):
    assert ss.parse_shift('ca sáng') == 'CA_SANG' and ss.parse_shift('Tối') == 'CA_TOI' and ss.parse_shift(None) is None
    assert ss.find_employee('Bình')['username'] == 'lich_binh'
    assert ss.find_employee('lê văn cường')['username'] == 'lich_cuong'
    with pytest.raises(ValueError):
        ss.find_employee('Không Ai')


def test_generated_week_obeys_hard_rules(staff):
    ss.add_busy('lich_an', [WEEK], None, 'đi học', 'test')                       # An off Monday
    ss.add_busy('lich_binh', [WEEK + timedelta(days=1)], 'CA_CHIEU', 'khám', 'test')
    for seed in range(20):
        schedule = ss.generate(WEEK, seed=seed)
        result = ss.check(schedule)
        assert result['is_valid'], result['violations']
        monday, tuesday = schedule['assignments'][WEEK.isoformat()], schedule['assignments'][(WEEK + timedelta(days=1)).isoformat()]
        assert all('lich_an' not in monday[s] for s in ss.SHIFTS)
        assert 'lich_binh' not in tuesday['CA_CHIEU']
        for day in schedule['assignments'].values():
            assert len(day['CA_SANG']) == 1 and len(day['CA_CHIEU']) == 2 and len(day['CA_TOI']) == 2
            assert all(any(u.startswith(('lich_an', 'lich_binh', 'lich_cuong', 'lich_dung')) for u in day[s]) for s in ss.SHIFTS)


def test_main_shift_is_preferred_and_load_is_spread(staff):
    schedule = ss.generate(WEEK, seed=7)
    morning = [day['CA_SANG'][0] for day in schedule['assignments'].values()]
    assert morning.count('lich_an') >= 4                                         # An's main shift is morning
    totals = ss.check(schedule)['shifts_per_person'].values()
    assert max(totals) - min(totals) <= 3


def test_needs_override_and_shortage_warning(staff):
    needs = ss.default_needs(WEEK)
    needs[WEEK.isoformat()] = {'CA_SANG': 2, 'CA_CHIEU': 3, 'CA_TOI': 2}
    schedule = ss.generate(WEEK, needs, seed=1)
    assert len(schedule['assignments'][WEEK.isoformat()]['CA_CHIEU']) == 3
    for u, *_ in PEOPLE:
        ss.add_busy(u, [WEEK + timedelta(days=6)], None, 'nghỉ', 'test')         # everybody off Sunday
    warn = ss.check(ss.generate(WEEK, seed=1))['warnings']
    assert any('CN' in w and 'thiếu' in w for w in warn)


def test_edit_grid_then_rules_block_bad_edits(staff):
    plan = ss.create_draft(WEEK, seed=3, by='quanly')
    assert plan['status'] == 'PENDING_APPROVAL' and plan['verification']['is_valid']
    rows = ss.to_grid(plan['schedule'])
    an = next(r for r in rows if r['username'] == 'lich_an')
    an[ss.day_label(WEEK)] = 'Chiều + Tối'
    edited = ss.update_draft(plan['plan_id'], rows, 'quanly')
    assert 'lich_an' in edited['schedule']['assignments'][WEEK.isoformat()]['CA_TOI']
    ss.add_busy('lich_an', [WEEK], 'CA_TOI', '', 'test')
    bad = ss.update_draft(plan['plan_id'], rows, 'quanly')
    assert not bad['verification']['is_valid']
    second = ss.create_draft(WEEK, seed=4, by='quanly')
    from src.engine.plan_service import get_plan
    assert get_plan(plan['plan_id'])['status'] == 'SUPERSEDED' and ss.pending(WEEK)['plan_id'] == second['plan_id']


def test_approval_publishes_to_staff(staff):
    from src.agent.config import AgentSettings
    from src.agent.mixue_agent import MixueOperationsAgent
    plan = ss.create_draft(WEEK, seed=5, by='quanly')
    assert ss.my_shifts('lich_an', WEEK) == [] or ss.published(WEEK)['plan_id'] != plan['plan_id']
    agent = MixueOperationsAgent(settings=AgentSettings.from_env().model_copy(update={'llm_enabled': False}))
    try:
        assert agent.tool_approve_plan(plan['plan_id'], 'STAFF_OFFICIAL', 'x')['status'] == 'UNAUTHORIZED'
        assert agent.tool_approve_plan(plan['plan_id'], 'MANAGER', 'Quản lý')['status'] == 'SUCCESS'
    finally:
        agent.close()
    assert ss.published(WEEK)['plan_id'] == plan['plan_id']
    mine = ss.my_shifts('lich_an', WEEK)
    assert len(mine) == 7 and sum(len(d['shifts']) for d in mine) >= 1


def test_schedule_page_generate_approve_and_staff_sees_it(staff, monkeypatch):
    from src.auth import SCHEDULE_PAGE
    from test_e2e_staff_manager import _open
    monkeypatch.setattr('src.engine.stock_matrix.today_vn', lambda: WEEK - timedelta(days=3))
    app = _open('quick_login_owner')
    app.radio(key='main_navigation').set_value(SCHEDULE_PAGE).run()
    assert not app.exception, app.exception
    app.button(key='sched_generate').click().run()
    assert not app.exception, app.exception
    draft = ss.pending(WEEK)
    assert draft and any('AI đã xếp' in s.value for s in app.success)
    app.button(key='sched_approve').click().run()
    assert not app.exception, app.exception
    assert ss.published(WEEK)['plan_id'] == draft['plan_id']


def test_staff_tools_respect_roles(staff, monkeypatch):
    from src.agent import schedule_tools as st_tools
    from src.agent.graph_runtime import Actor
    monkeypatch.setattr('src.engine.stock_matrix.today_vn', lambda: WEEK - timedelta(days=3))

    class Svc:
        _current_actor = Actor('lich_em', 'Hoàng Văn Em', 'STAFF_PROBATION')
    svc = Svc()
    assert st_tools.create_schedule(svc)['status'] == 'UNAUTHORIZED'
    assert st_tools.set_main_shift(svc, 'Bình', 'sáng')['status'] == 'UNAUTHORIZED'
    assert st_tools.report_busy(svc, WEEK, employee='Bình')['status'] == 'UNAUTHORIZED'
    ok = st_tools.report_busy(svc, WEEK + timedelta(days=2), shift='tối', reason='thi')
    assert ok['status'] == 'SUCCESS' and ok['employee'] == 'Hoàng Văn Em'
    svc._current_actor = Actor('quanly', 'Quản lý', 'MANAGER')
    assert st_tools.set_main_shift(svc, 'Dung', 'chiều')['status'] == 'SUCCESS'
    res = st_tools.create_schedule(svc, week_of=WEEK, needs=[{'day': WEEK, 'shift': 'chiều', 'people': 3}])
    assert res['status'] == 'PENDING_APPROVAL' and len(ss.pending(WEEK)['schedule']['assignments'][WEEK.isoformat()]['CA_CHIEU']) == 3
    wed = ss.pending(WEEK)['schedule']['assignments'][(WEEK + timedelta(days=2)).isoformat()]
    assert 'lich_em' not in wed['CA_TOI']
    view = st_tools.view_schedule(svc, week_of=WEEK)
    assert view['draft']['plan_id'] == res['plan_id'] and view['published_table'] is None


def test_chat_shows_my_schedule_and_staff_page(staff, monkeypatch):
    from src.agent.config import AgentSettings
    from src.agent.mixue_agent import MixueOperationsAgent
    monkeypatch.setattr('src.engine.stock_matrix.today_vn', lambda: WEEK + timedelta(days=1))
    plan = ss.create_draft(WEEK, seed=2, by='quanly')
    agent = MixueOperationsAgent(settings=AgentSettings.from_env().model_copy(update={'llm_enabled': False}))
    try:
        agent.tool_approve_plan(plan['plan_id'], 'MANAGER', 'Quản lý')
        reply = agent.process_query('lịch làm tuần này của tôi', 'STAFF_OFFICIAL', 'Nguyễn Văn An', user_id='lich_an')
    finally:
        agent.close()
    assert reply['tool_called'] == 'get_work_schedule' and 'Ca của bạn' in reply['text']


def test_staff_page_and_home_card_render():
    from src.auth import SCHEDULE_PAGE
    from test_e2e_staff_manager import _open
    app = _open('quick_login_staff')
    assert not app.exception, app.exception
    assert any('Lịch làm tuần này' in m.value for m in app.markdown)
    app.radio(key='main_navigation').set_value(SCHEDULE_PAGE).run()
    assert not app.exception, app.exception
