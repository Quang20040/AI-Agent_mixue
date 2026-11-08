"""Chấm công: check-in / check-out only within a set distance of the shop (phone GPS), with a photo the AI
reviews, and on-time / late / early-leave worked out from the published work schedule.

Rules (times from SHIFT_TIMES, default sáng 08:00–13:00, chiều 13:00–18:00, tối 18:00–23:30):
  * check-in any time; on time up to start + 5 min, after that LATE by (now − start) minutes;
  * check-out any time; leaving up to 5 min early (ca tối: 10 min) is fine, earlier is EARLY by (end − now);
  * two adjacent shifts in a day count as one block (start of the first, end of the last);
  * no shift that day → OFF_SCHEDULE (recorded, the manager decides).
Location: the browser's GPS position must be within RADIUS of the shop point the manager set (and precise
enough). Optionally the manager can also require the shop WiFi (public IP). The AI looks at the photo
(a real person, not a screen) → AUTO_OK, otherwise NEEDS_REVIEW; the manager can approve / reject any record.
"""
from __future__ import annotations

import ipaddress
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from src.database import Base, SessionLocal, engine
from src.engine import staff_schedule as ss
from src.models import AppSetting, AttendanceCheck, AttendanceNetwork

Base.metadata.create_all(bind=engine)

ROOT = Path(__file__).resolve().parents[2]
CHECKIN_GRACE_MIN = int(os.environ.get('CHECKIN_GRACE_MINUTES', 5))
CHECKOUT_GRACE_MIN = {'CA_SANG': 5, 'CA_CHIEU': 5, 'CA_TOI': 10}
MAX_ACCURACY_M = int(os.environ.get('CHECKIN_MAX_GPS_ACCURACY_M', 150))
TIMING_VI = {'ON_TIME': 'Đúng giờ', 'LATE': 'Đi muộn', 'OK': 'Đúng giờ', 'EARLY': 'Về sớm', 'OFF_SCHEDULE': 'Ngoài lịch'}
AI_VI = {'OK': 'Ảnh hợp lệ', 'NO_PERSON': 'Không thấy người', 'SCREEN': 'Nghi chụp lại màn hình', 'UNAVAILABLE': 'AI chưa xem'}
STATUS_VI = {'AUTO_OK': 'AI duyệt', 'NEEDS_REVIEW': 'Chờ Quản lý xem', 'APPROVED': 'Quản lý duyệt', 'REJECTED': 'Không tính'}


def photo_dir() -> Path:
    path = Path(os.environ.get('ATTENDANCE_PHOTO_DIR') or ROOT / 'data' / 'attendance_photos')
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_photo(data: bytes, prefix: str) -> str:
    from src.engine.checkin_photo import shrink
    name = f'{prefix}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.jpg'
    (photo_dir() / name).write_bytes(shrink(data, 640))
    return name


def read_photo(name: str | None) -> bytes | None:
    if not name:
        return None
    path = (photo_dir() / name).resolve()
    if path.parent != photo_dir().resolve() or not path.exists():
        return None
    return path.read_bytes()


# --- settings: shop location, radius, optional WiFi ----------------------------------------------------------

def _get(key: str, default: str | None = None) -> str | None:
    with SessionLocal() as db:
        row = db.get(AppSetting, key)
        return row.value if row and row.value is not None else default


def _set(key: str, value: str | None, by: str = '') -> None:
    with SessionLocal() as db:
        db.merge(AppSetting(key=key, value=value, updated_by=by))
        db.commit()


def shop_location() -> dict[str, Any] | None:
    lat, lon = _get('attendance_lat'), _get('attendance_lon')
    if lat is None or lon is None:
        return None
    return {'lat': float(lat), 'lon': float(lon), 'radius_m': int(_get('attendance_radius_m', '100')),
            'require_wifi': _get('attendance_require_wifi', '1') == '1'}   # shop WiFi required unless turned off


def set_shop_location(lat: float, lon: float, radius_m: int, by: str = '') -> None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not 20 <= radius_m <= 1000:
        raise ValueError('Vị trí hoặc bán kính không hợp lệ (bán kính 20–1000 m).')
    _set('attendance_lat', f'{lat:.6f}', by)
    _set('attendance_lon', f'{lon:.6f}', by)
    _set('attendance_radius_m', str(int(radius_m)), by)


def set_require_wifi(on: bool, by: str = '') -> None:
    _set('attendance_require_wifi', '1' if on else '0', by)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def where(position: dict | None) -> dict[str, Any]:
    """{'ok': bool, 'distance_m', 'message'} for a browser position {'lat','lon','accuracy'}."""
    shop = shop_location()
    if shop is None:
        return {'ok': False, 'distance_m': None, 'message': 'Quản lý chưa đặt vị trí quán để chấm công.'}
    if not position or position.get('lat') is None:
        return {'ok': False, 'distance_m': None, 'message': 'Chưa lấy được vị trí — bấm “Lấy vị trí” và cho phép truy cập vị trí.'}
    d = distance_m(float(position['lat']), float(position['lon']), shop['lat'], shop['lon'])
    acc = float(position.get('accuracy') or 9999)
    if acc > MAX_ACCURACY_M:
        return {'ok': False, 'distance_m': round(d), 'message': f'Vị trí chưa đủ chính xác (sai số ~{acc:.0f} m). Bật GPS, ra gần cửa rồi lấy lại.'}
    if d > shop['radius_m']:
        return {'ok': False, 'distance_m': round(d), 'message': f"Bạn đang cách quán ~{d:.0f} m (cho phép {shop['radius_m']} m)."}
    return {'ok': True, 'distance_m': round(d), 'message': f'Đang ở quán (cách ~{d:.0f} m).'}


# --- network (optional extra check) ---------------------------------------------------------------------------------------------

def client_ip(headers: dict | None, fallback: str | None = None) -> str | None:
    """The browser's public IP: first X-Forwarded-For hop (set by the Render proxy), else the socket address."""
    headers = {str(k).lower(): v for k, v in (headers or {}).items()}
    forwarded = str(headers.get('x-forwarded-for') or '').split(',')[0].strip()
    return forwarded or headers.get('x-real-ip') or fallback


def networks() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        return [{'ip': n.ip, 'label': n.label or '', 'added_by': n.added_by or '', 'added_at': n.added_at}
                for n in db.query(AttendanceNetwork).order_by(AttendanceNetwork.added_at)]


def add_network(ip: str, label: str = '', by: str = '') -> str:
    ipaddress.ip_network(ip, strict=False)            # raises on garbage
    with SessionLocal() as db:
        db.merge(AttendanceNetwork(ip=ip.strip(), label=label[:100], added_by=by))
        db.commit()
    return ip.strip()


def remove_network(ip: str) -> None:
    with SessionLocal() as db:
        db.query(AttendanceNetwork).filter(AttendanceNetwork.ip == ip).delete()
        db.commit()


def on_shop_network(ip: str | None) -> bool:
    """True if the IP is one of the registered shop addresses (single IP, or a range like 113.22.10.0/29).
    IPv6 home connections change their last part often, so an IPv6 entry matches its /64 network."""
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for n in networks():
        net = ipaddress.ip_network(n['ip'], strict=False)
        if net.version == 6 and net.prefixlen == 128:
            net = ipaddress.ip_network(f"{n['ip']}/64", strict=False)
        if addr.version == net.version and addr in net:
            return True
    return False


# --- check-in / check-out --------------------------------------------------------------------------------

def _clock(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, datetime.strptime(hhmm, '%H:%M').time(), ss.VN)


def today_block(username: str, day: date) -> dict[str, Any] | None:
    """The person's shifts on that day in the published schedule, merged into one block."""
    plan = ss.published(day)
    if not plan:
        return None
    shifts = [s for s in ss.SHIFTS if username in plan['schedule']['assignments'].get(day.isoformat(), {}).get(s, [])]
    if not shifts:
        return None
    times = ss.shift_times()
    return {'shifts': shifts, 'start': _clock(day, times[shifts[0]][0]), 'end': _clock(day, times[shifts[-1]][1]),
            'label': ' + '.join(ss.SHIFT_VI[s] for s in shifts) + f" ({times[shifts[0]][0]}–{times[shifts[-1]][1]})"}


def timing(kind: str, block: dict | None, now: datetime) -> tuple[str, int]:
    if block is None:
        return 'OFF_SCHEDULE', 0
    if kind == 'IN':
        late = (now - block['start']).total_seconds() / 60
        return ('ON_TIME', 0) if late <= CHECKIN_GRACE_MIN else ('LATE', int(late))
    early = (block['end'] - now).total_seconds() / 60
    return ('OK', 0) if early <= CHECKOUT_GRACE_MIN[block['shifts'][-1]] else ('EARLY', int(early + 0.999))


def _records(username: str, day: date) -> list[AttendanceCheck]:
    with SessionLocal() as db:
        return db.query(AttendanceCheck).filter(AttendanceCheck.username == username, AttendanceCheck.work_date == day,
                                                 AttendanceCheck.status != 'REJECTED').order_by(AttendanceCheck.at).all()


def state(username: str, now: datetime | None = None) -> dict[str, Any]:
    """What the staff page shows: today's block and whether the next action is IN or OUT."""
    now = now or ss.now_vn()
    rows = _records(username, now.date())
    last = rows[-1].kind if rows else None
    return {'block': today_block(username, now.date()), 'next': 'OUT' if last == 'IN' else 'IN',
            'records': [_row(r) for r in rows]}


def check(kind: str, username: str, photo: bytes, position: dict | None, ip: str | None = None,
          now: datetime | None = None, reviewer: Callable[[bytes], dict] | None = None) -> dict[str, Any]:
    """Record a check-in (IN) or check-out (OUT). Raises ValueError with a message the staff member sees."""
    if kind not in {'IN', 'OUT'}:
        raise ValueError('kind must be IN or OUT')
    now = now or ss.now_vn()
    place = where(position)
    if not place['ok']:
        raise ValueError(place['message'])
    shop = shop_location()
    if shop['require_wifi'] and not networks():
        raise ValueError('Quản lý chưa đăng ký WiFi của quán nên chưa chấm công được.')
    if shop['require_wifi'] and not on_shop_network(ip):
        raise ValueError('Chỉ chấm công được khi bắt WiFi của quán — tắt 4G và kết nối WiFi quán.')
    if not photo:
        raise ValueError('Chụp ảnh trước khi chấm công.')
    current = state(username, now)
    if kind != current['next']:
        raise ValueError('Bạn đã check-in rồi, lần tiếp theo là check-out.' if kind == 'IN' else 'Bạn chưa check-in hôm nay.')
    if reviewer is None:
        from src.engine.checkin_photo import review as reviewer
    ai = reviewer(photo)
    when, minutes = timing(kind, current['block'], now)
    status = 'AUTO_OK' if ai['result'] == 'OK' and when != 'OFF_SCHEDULE' else 'NEEDS_REVIEW'
    with SessionLocal() as db:
        rec = AttendanceCheck(username=username, work_date=now.date(), kind=kind, at=now.replace(tzinfo=None),
                              shift_codes=','.join(current['block']['shifts']) if current['block'] else None,
                              lat=position.get('lat'), lon=position.get('lon'), accuracy_m=int(position.get('accuracy') or 0),
                              distance_m=place['distance_m'], ip=ip, photo_path=_save_photo(photo, f'{kind.lower()}_{username}'),
                              ai_result=ai['result'], ai_reason=(ai.get('reason') or '')[:300],
                              timing=when, minutes=minutes, status=status)
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return _row(rec)


def _row(r: AttendanceCheck) -> dict[str, Any]:
    return {'id': r.id, 'username': r.username, 'date': r.work_date, 'kind': r.kind, 'at': r.at,
            'shifts': r.shift_codes.split(',') if r.shift_codes else [], 'ai': r.ai_result, 'reason': r.ai_reason or '',
            'distance_m': r.distance_m, 'timing': r.timing, 'minutes': r.minutes, 'status': r.status,
            'photo': r.photo_path, 'reviewed_by': r.reviewed_by}


def review(record_id: int, approve: bool, by: str) -> None:
    with SessionLocal() as db:
        r = db.get(AttendanceCheck, record_id)
        if r is None:
            raise ValueError('Không tìm thấy lượt chấm công.')
        r.status, r.reviewed_by, r.reviewed_at = ('APPROVED' if approve else 'REJECTED'), by, datetime.now()
        db.commit()


def rereview(record_id: int, reviewer: Callable[[bytes], dict] | None = None) -> dict[str, Any]:
    """Ask the AI again for a record it could not look at (e.g. AI was down); may turn it into AUTO_OK."""
    if reviewer is None:
        from src.engine.checkin_photo import review as reviewer
    with SessionLocal() as db:
        r = db.get(AttendanceCheck, record_id)
        if r is None or r.status != 'NEEDS_REVIEW':
            raise ValueError('Lượt này không chờ duyệt.')
        ai = reviewer(read_photo(r.photo_path) or b'')
        r.ai_result, r.ai_reason = ai['result'], (ai.get('reason') or '')[:300]
        if ai['result'] == 'OK' and r.timing != 'OFF_SCHEDULE':
            r.status = 'AUTO_OK'
        db.commit()
        db.refresh(r)
        return _row(r)


def needs_review() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        return [_row(r) for r in db.query(AttendanceCheck).filter(AttendanceCheck.status == 'NEEDS_REVIEW')
                .order_by(AttendanceCheck.at.desc()).limit(100)]


def timesheet(start: date, end: date) -> list[dict[str, Any]]:
    """One row per person per day that had a shift or a record: in/out times, late / early minutes."""
    names = {e['username']: e['full_name'] for e in ss.employees()}
    with SessionLocal() as db:
        recs = [_row(r) for r in db.query(AttendanceCheck).filter(AttendanceCheck.work_date >= start,
                AttendanceCheck.work_date <= end, AttendanceCheck.status != 'REJECTED').order_by(AttendanceCheck.at)]
    days: dict[tuple[str, date], dict[str, Any]] = {}
    d = start
    while d <= end:
        for e in ss.employees():
            block = today_block(e['username'], d)
            if block:
                days[(e['username'], d)] = {'username': e['username'], 'date': d, 'block': block['label'], 'in': None, 'out': None}
        d += timedelta(days=1)
    for r in recs:
        row = days.setdefault((r['username'], r['date']), {'username': r['username'], 'date': r['date'], 'block': 'Ngoài lịch',
                                                           'in': None, 'out': None})
        slot = 'in' if r['kind'] == 'IN' else 'out'
        if r['kind'] == 'IN' and row['in'] is None or r['kind'] == 'OUT':
            row[slot] = r
    out = []
    for (u, d), row in sorted(days.items(), key=lambda kv: (kv[0][1], names.get(kv[0][0], kv[0][0]))):
        i, o = row['in'], row['out']
        missing = 'Chưa check-in' if not i and d <= ss.now_vn().date() else ''
        out.append({'Ngày': ss.day_label(d), 'Nhân viên': names.get(u, u), 'Ca': row['block'],
                    'Vào': f"{i['at']:%H:%M}" if i else '—', 'Muộn (phút)': i['minutes'] if i and i['timing'] == 'LATE' else 0,
                    'Ra': f"{o['at']:%H:%M}" if o else '—', 'Về sớm (phút)': o['minutes'] if o and o['timing'] == 'EARLY' else 0,
                    'Trạng thái': ' · '.join(x for x in (
                        missing,
                        TIMING_VI[i['timing']] if i and i['timing'] in ('LATE', 'OFF_SCHEDULE') else '',
                        'Về sớm' if o and o['timing'] == 'EARLY' else '',
                        'Chờ duyệt' if any(x and x['status'] == 'NEEDS_REVIEW' for x in (i, o)) else '') if x) or 'Đủ công'})
    return out
