"""Chấm công: GPS within the shop radius, AI photo check, on-time / late / early-leave rules."""
import io
from datetime import datetime, timedelta

import pytest
from PIL import Image

from src.database import SessionLocal
from src.engine import attendance as att
from src.engine import checkin_photo
from src.engine import staff_schedule as ss
from src.models import AppSetting, AttendanceCheck, AttendanceNetwork
from test_staff_schedule import WEEK, _drop_schedules, staff  # noqa: F401  (fixture)

SHOP_IP = '113.22.10.5'
SHOP = (21.012345, 105.842310)
HERE = {'lat': 21.012400, 'lon': 105.842350, 'accuracy': 20}          # ~7 m away
FAR = {'lat': 21.020000, 'lon': 105.842310, 'accuracy': 15}           # ~850 m away


def _jpg():
    out = io.BytesIO()
    Image.new('RGB', (64, 64), 'white').save(out, 'JPEG')
    return out.getvalue()


def _at(day, hh, mm=0):
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=ss.VN)


MATCH = lambda photo: {'result': 'OK', 'reason': 'có người'}  # noqa: E731
NOPE = lambda photo: {'result': 'SCREEN', 'reason': 'chụp lại màn hình'}  # noqa: E731


@pytest.fixture()
def shop(staff, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv('ATTENDANCE_PHOTO_DIR', str(tmp_path / 'att'))
    monkeypatch.setenv('SHIFT_TIMES', '08:00-13:00,13:00-18:00,18:00-23:30')
    with SessionLocal() as db:
        for model in (AttendanceCheck, AppSetting, AttendanceNetwork):
            db.query(model).delete()
        db.commit()
    att.set_shop_location(*SHOP, 100, 'quanly')
    att.set_require_wifi(False, 'quanly')          # most tests are about location / timing; WiFi has its own test
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
    yield
    with SessionLocal() as db:
        for model in (AttendanceCheck, AppSetting, AttendanceNetwork):
            db.query(model).delete()
        db.commit()


def test_network_rules():
    assert att.client_ip({'X-Forwarded-For': '1.2.3.4, 10.0.0.1'}, '10.0.0.9') == '1.2.3.4'
    assert att.client_ip({}, '10.0.0.9') == '10.0.0.9'


def test_wifi_required_by_default():
    with SessionLocal() as db:
        db.query(AppSetting).delete()
        db.commit()
    att.set_shop_location(*SHOP, 100, 'quanly')
    assert att.shop_location()['require_wifi'] is True


def test_location_radius_accuracy_and_wifi(shop):
    assert att.where(HERE)['ok'] and att.where(HERE)['distance_m'] < 20
    with pytest.raises(ValueError, match='cách quán'):
        att.check('IN', 'lich_an', _jpg(), FAR, now=_at(WEEK, 7, 55), reviewer=MATCH)
    with pytest.raises(ValueError, match='chính xác'):
        att.check('IN', 'lich_an', _jpg(), {**HERE, 'accuracy': 900}, now=_at(WEEK, 7, 55), reviewer=MATCH)
    with pytest.raises(ValueError, match='vị trí'):
        att.check('IN', 'lich_an', _jpg(), None, now=_at(WEEK, 7, 55), reviewer=MATCH)
    att.set_require_wifi(True, 'quanly')
    with pytest.raises(ValueError, match='chưa đăng ký WiFi'):
        att.check('IN', 'lich_an', _jpg(), HERE, ip=SHOP_IP, now=_at(WEEK, 7, 55), reviewer=MATCH)
    att.add_network(SHOP_IP, 'WiFi quán', 'quanly')
    with pytest.raises(ValueError, match='WiFi'):
        att.check('IN', 'lich_an', _jpg(), HERE, ip='27.72.1.1', now=_at(WEEK, 7, 55), reviewer=MATCH)   # 4G
    assert att.check('IN', 'lich_an', _jpg(), HERE, ip=SHOP_IP, now=_at(WEEK, 7, 55), reviewer=MATCH)['status'] == 'AUTO_OK'
    att.add_network('2402:800:abcd:1234::1', 'IPv6', 'quanly')
    assert att.on_shop_network('2402:800:abcd:1234:9999::77')
    with pytest.raises(ValueError):
        att.set_shop_location(*SHOP, 5000)


def test_on_time_late_and_early_rules(shop):
    rec = att.check('IN', 'lich_an', _jpg(), HERE, now=_at(WEEK, 8, 5), reviewer=MATCH)
    assert (rec['timing'], rec['minutes'], rec['status']) == ('ON_TIME', 0, 'AUTO_OK')            # 08:05 still on time
    with pytest.raises(ValueError, match='check-out'):
        att.check('IN', 'lich_an', _jpg(), HERE, now=_at(WEEK, 8, 10), reviewer=MATCH)
    out = att.check('OUT', 'lich_an', _jpg(), HERE, now=_at(WEEK, 12, 55), reviewer=MATCH)
    assert (out['timing'], out['minutes']) == ('OK', 0)                                              # 5 min early is fine
    late = att.check('IN', 'lich_cuong', _jpg(), HERE, now=_at(WEEK, 18, 12), reviewer=MATCH)
    assert (late['timing'], late['minutes']) == ('LATE', 12)
    early = att.check('OUT', 'lich_cuong', _jpg(), HERE, now=_at(WEEK, 23, 15), reviewer=MATCH)
    assert (early['timing'], early['minutes']) == ('EARLY', 15)                                      # evening: 10 min allowed
    tue = WEEK + timedelta(days=1)
    att.check('IN', 'lich_binh', _jpg(), HERE, now=_at(tue, 13, 3), reviewer=MATCH)                   # chiều + tối = one block
    ok = att.check('OUT', 'lich_binh', _jpg(), HERE, now=_at(tue, 23, 21), reviewer=MATCH)
    assert (ok['timing'], ok['minutes']) == ('OK', 0)


def test_doubtful_photo_and_off_schedule_go_to_manager(shop):
    bad = att.check('IN', 'lich_an', _jpg(), HERE, now=_at(WEEK, 7, 58), reviewer=NOPE)
    assert bad['status'] == 'NEEDS_REVIEW' and bad['ai'] == 'SCREEN'
    off = att.check('IN', 'lich_cuong', _jpg(), HERE, now=_at(WEEK + timedelta(days=3), 9), reviewer=MATCH)
    assert off['timing'] == 'OFF_SCHEDULE' and off['status'] == 'NEEDS_REVIEW'
    assert {r['id'] for r in att.needs_review()} >= {bad['id'], off['id']}
    att.review(bad['id'], False, 'quanly')
    again = att.check('IN', 'lich_an', _jpg(), HERE, now=_at(WEEK, 8, 20), reviewer=MATCH)          # rejected one doesn't count
    assert again['timing'] == 'LATE' and again['minutes'] == 20


def test_timesheet(shop, monkeypatch):
    monkeypatch.setattr(ss, 'now_vn', lambda: _at(WEEK + timedelta(days=2), 9))
    att.check('IN', 'lich_cuong', _jpg(), HERE, now=_at(WEEK, 18, 9), reviewer=MATCH)
    att.check('OUT', 'lich_cuong', _jpg(), HERE, now=_at(WEEK, 23, 0), reviewer=MATCH)
    rows = {(r['Ngày'], r['Nhân viên']): r for r in att.timesheet(WEEK, WEEK + timedelta(days=6))}
    cuong = rows[(ss.day_label(WEEK), 'Lê Văn Cường')]
    assert cuong['Muộn (phút)'] == 9 and cuong['Về sớm (phút)'] == 30
    assert rows[(ss.day_label(WEEK), 'Nguyễn Văn An')]['Trạng thái'] == 'Chưa check-in'


def test_photo_classifier_and_offline_fallback():
    assert checkin_photo.classify({'person_visible': True, 'looks_like_screen_or_print': False})['result'] == 'OK'
    assert checkin_photo.classify({'person_visible': False, 'looks_like_screen_or_print': False})['result'] == 'NO_PERSON'
    assert checkin_photo.classify({'person_visible': True, 'looks_like_screen_or_print': True})['result'] == 'SCREEN'
    assert checkin_photo.review(_jpg())['result'] == 'UNAVAILABLE'                                  # AI off in tests


def test_pages_render(shop):
    from src.auth import SCHEDULE_PAGE
    from test_e2e_staff_manager import _open
    app = _open('quick_login_owner')
    app.radio(key='main_navigation').set_value(SCHEDULE_PAGE).run()
    assert not app.exception, app.exception
    assert any('Bảng công' in m.value for m in app.markdown)


def test_ai_answer_parsing_and_model_fallback(monkeypatch):
    calls = []

    def fake_ask(model, key, image):
        calls.append(model)
        if model == 'm1':
            raise RuntimeError('HTTP 429: quota')
        return {'person_visible': True, 'looks_like_screen_or_print': False, 'indoor_shop_like': True, 'reason': 'ok'}, {}
    monkeypatch.setattr(checkin_photo, 'available', lambda: True)
    monkeypatch.setattr(checkin_photo, '_ask', fake_ask)
    monkeypatch.setenv('CHECKIN_PHOTO_MODEL', '')
    monkeypatch.setattr('src.engine.vision_ocr.ocr_model_chain', lambda cfg: ['m1', 'm2'])
    assert checkin_photo.review(_jpg())['result'] == 'OK' and calls == ['m1', 'm2']


def test_manager_can_ask_ai_again(shop):
    down = att.check('IN', 'lich_an', _jpg(), HERE, now=_at(WEEK, 7, 58),
                     reviewer=lambda p: {'result': 'UNAVAILABLE', 'reason': 'AI lỗi'})
    assert down['status'] == 'NEEDS_REVIEW'
    again = att.rereview(down['id'], reviewer=MATCH)
    assert again['status'] == 'AUTO_OK' and again['ai'] == 'OK'


def test_photo_is_stamped_with_time_and_place(shop):
    seen = {}

    def spy(photo):
        seen['photo'] = photo
        return {'result': 'OK', 'reason': ''}
    rec = att.check('IN', 'lich_an', _jpg(), HERE, now=_at(WEEK, 8, 12), reviewer=spy)
    saved = att.read_photo(rec['photo'])
    assert saved == seen['photo']                                   # the AI sees the stamped photo too
    img = Image.open(io.BytesIO(saved))
    band = img.crop((0, img.height - 10, img.width, img.height)).convert('L')
    assert sum(band.getdata()) / (band.width * band.height) < 200   # dark caption band at the bottom (white input)
    assert att.day_records(WEEK)[0]['id'] == rec['id']
