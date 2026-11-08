"""Chấm công: shop WiFi only, approved face, AI face check, on-time / late / early-leave rules."""
import io
from datetime import datetime, timedelta

import pytest
from PIL import Image

from src.database import SessionLocal
from src.engine import attendance as att
from src.engine import face_verify
from src.engine import staff_schedule as ss
from src.models import AttendanceNetwork, AttendanceRecord, FaceProfile
from test_staff_schedule import WEEK, _drop_schedules, staff  # noqa: F401  (fixture)

SHOP_IP = '113.22.10.5'


def _jpg():
    out = io.BytesIO()
    Image.new('RGB', (64, 64), 'white').save(out, 'JPEG')
    return out.getvalue()


def _at(day, hh, mm=0):
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=ss.VN)


MATCH = lambda ref, live: {'result': 'MATCH', 'confidence': 0.95, 'reason': 'cùng người'}  # noqa: E731
NOPE = lambda ref, live: {'result': 'NO_MATCH', 'confidence': 0.9, 'reason': 'khác người'}  # noqa: E731


@pytest.fixture()
def shop(staff, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv('ATTENDANCE_PHOTO_DIR', str(tmp_path / 'att'))
    monkeypatch.setenv('SHIFT_TIMES', '08:00-13:00,13:00-18:00,18:00-23:30')
    with SessionLocal() as db:
        for model in (AttendanceRecord, FaceProfile, AttendanceNetwork):
            db.query(model).delete()
        db.commit()
    att.add_network(SHOP_IP, 'WiFi quán', 'quanly')
    # one-week schedule: An morning Mon, Cường evening Mon, Bình chiều+tối Tue
    plan = ss.create_draft(WEEK, seed=1, by='quanly')
    a = plan['schedule']['assignments']
    for day in a.values():
        for s in ss.SHIFTS:
            day[s] = []
    mon, tue = WEEK.isoformat(), (WEEK + timedelta(days=1)).isoformat()
    a[mon]['CA_SANG'], a[mon]['CA_TOI'] = ['lich_an'], ['lich_cuong']
    a[tue]['CA_CHIEU'], a[tue]['CA_TOI'] = ['lich_binh'], ['lich_binh']
    from src.engine.plan_service import save_plan
    plan['status'], plan['approved_by'] = 'APPROVED', 'Quản lý'
    save_plan(plan)
    for u in ('lich_an', 'lich_binh', 'lich_cuong'):
        att.enroll(u, _jpg(), True)
        att.review_face(u, True, 'quanly')
    yield
    with SessionLocal() as db:
        for model in (AttendanceRecord, FaceProfile, AttendanceNetwork):
            db.query(model).delete()
        db.commit()


def test_network_rules():
    assert att.client_ip({'X-Forwarded-For': '1.2.3.4, 10.0.0.1'}, '10.0.0.9') == '1.2.3.4'
    assert att.client_ip({}, '10.0.0.9') == '10.0.0.9'


def test_only_shop_wifi_and_approved_face(shop):
    with pytest.raises(ValueError, match='WiFi'):
        att.check('IN', 'lich_an', _jpg(), '27.72.1.1', _at(WEEK, 7, 55), compare=MATCH)      # 4G
    assert att.on_shop_network(SHOP_IP) and not att.on_shop_network(None)
    att.add_network('2402:800:abcd:1234::1', 'IPv6', 'quanly')
    assert att.on_shop_network('2402:800:abcd:1234:9999::77')                                  # same /64
    att.enroll('lich_dung', _jpg(), True)
    with pytest.raises(ValueError, match='chưa có ảnh'):
        att.check('IN', 'lich_dung', _jpg(), SHOP_IP, _at(WEEK, 8), compare=MATCH)
    with pytest.raises(ValueError, match='đồng ý'):
        att.enroll('lich_dung', _jpg(), False)


def test_on_time_late_and_early_rules(shop):
    rec = att.check('IN', 'lich_an', _jpg(), SHOP_IP, _at(WEEK, 8, 5), compare=MATCH)
    assert (rec['timing'], rec['minutes'], rec['status']) == ('ON_TIME', 0, 'AUTO_OK')            # 08:05 still on time
    with pytest.raises(ValueError, match='check-out'):
        att.check('IN', 'lich_an', _jpg(), SHOP_IP, _at(WEEK, 8, 10), compare=MATCH)
    out = att.check('OUT', 'lich_an', _jpg(), SHOP_IP, _at(WEEK, 12, 55), compare=MATCH)
    assert (out['timing'], out['minutes']) == ('OK', 0)                                              # 5 min early is fine
    late = att.check('IN', 'lich_cuong', _jpg(), SHOP_IP, _at(WEEK, 18, 12), compare=MATCH)
    assert (late['timing'], late['minutes']) == ('LATE', 12)
    early = att.check('OUT', 'lich_cuong', _jpg(), SHOP_IP, _at(WEEK, 23, 15), compare=MATCH)
    assert (early['timing'], early['minutes']) == ('EARLY', 15)                                      # evening: 10 min allowed
    tue = WEEK + timedelta(days=1)
    att.check('IN', 'lich_binh', _jpg(), SHOP_IP, _at(tue, 13, 3), compare=MATCH)                   # chiều + tối = one block
    ok = att.check('OUT', 'lich_binh', _jpg(), SHOP_IP, _at(tue, 23, 21), compare=MATCH)
    assert (ok['timing'], ok['minutes']) == ('OK', 0)


def test_face_mismatch_and_off_schedule_go_to_manager(shop):
    bad = att.check('IN', 'lich_an', _jpg(), SHOP_IP, _at(WEEK, 7, 58), compare=NOPE)
    assert bad['status'] == 'NEEDS_REVIEW' and bad['face'] == 'NO_MATCH'
    off = att.check('IN', 'lich_cuong', _jpg(), SHOP_IP, _at(WEEK + timedelta(days=3), 9), compare=MATCH)
    assert off['timing'] == 'OFF_SCHEDULE' and off['status'] == 'NEEDS_REVIEW'
    assert {r['id'] for r in att.needs_review()} >= {bad['id'], off['id']}
    att.review(bad['id'], False, 'quanly')
    again = att.check('IN', 'lich_an', _jpg(), SHOP_IP, _at(WEEK, 8, 20), compare=MATCH)          # rejected one doesn't count
    assert again['timing'] == 'LATE' and again['minutes'] == 20


def test_timesheet(shop, monkeypatch):
    monkeypatch.setattr(ss, 'now_vn', lambda: _at(WEEK + timedelta(days=2), 9))
    att.check('IN', 'lich_cuong', _jpg(), SHOP_IP, _at(WEEK, 18, 9), compare=MATCH)
    att.check('OUT', 'lich_cuong', _jpg(), SHOP_IP, _at(WEEK, 23, 0), compare=MATCH)
    rows = {(r['Ngày'], r['Nhân viên']): r for r in att.timesheet(WEEK, WEEK + timedelta(days=6))}
    cuong = rows[(ss.day_label(WEEK), 'Lê Văn Cường')]
    assert cuong['Muộn (phút)'] == 9 and cuong['Về sớm (phút)'] == 30
    assert rows[(ss.day_label(WEEK), 'Nguyễn Văn An')]['Trạng thái'] == 'Chưa check-in'


def test_face_classifier_and_offline_fallback(monkeypatch):
    assert face_verify.classify({'face_visible': True, 'same_person': True, 'confidence': 0.9})['result'] == 'MATCH'
    assert face_verify.classify({'face_visible': True, 'same_person': True, 'confidence': 0.6})['result'] == 'UNSURE'
    assert face_verify.classify({'face_visible': True, 'same_person': False, 'confidence': 0.95})['result'] == 'NO_MATCH'
    assert face_verify.classify({'face_visible': False})['result'] == 'NO_FACE'
    assert face_verify.classify({'face_visible': True, 'same_person': True, 'confidence': 0.99,
                                 'looks_like_screen_or_print': True})['result'] == 'SPOOF'
    assert face_verify.compare(_jpg(), _jpg())['result'] == 'UNAVAILABLE'                       # AI off in tests


def test_pages_render(shop):
    from src.auth import SCHEDULE_PAGE
    from test_e2e_staff_manager import _open
    app = _open('quick_login_owner')
    app.radio(key='main_navigation').set_value(SCHEDULE_PAGE).run()
    assert not app.exception, app.exception
    assert any('Bảng công' in m.value for m in app.markdown)
