"""Chấm công: check-in / check-out only from the shop's WiFi, with a selfie the AI compares to the approved
reference photo, and on-time / late / early-leave worked out from the published work schedule.

Rules (times from SHIFT_TIMES, default sáng 08:00–13:00, chiều 13:00–18:00, tối 18:00–23:30):
  * check-in any time; on time up to start + 5 min, after that LATE by (now − start) minutes;
  * check-out any time; leaving up to 5 min early (ca tối: 10 min) is fine, earlier is EARLY by (end − now);
  * two adjacent shifts in a day count as one block (start of the first, end of the last);
  * no shift that day → OFF_SCHEDULE (recorded, the manager decides).
"WiFi of the shop" = the shop router's public IP address, registered by the manager while on that WiFi.
A phone on 4G has a carrier IP, so it is refused. The AI result (face match) sets AUTO_OK or NEEDS_REVIEW;
the manager can approve / reject any record.
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
from src.models import AttendanceNetwork, AttendanceRecord, FaceProfile

Base.metadata.create_all(bind=engine)

ROOT = Path(__file__).resolve().parents[2]
CHECKIN_GRACE_MIN = int(os.environ.get('CHECKIN_GRACE_MINUTES', 5))
CHECKOUT_GRACE_MIN = {'CA_SANG': 5, 'CA_CHIEU': 5, 'CA_TOI': 10}
TIMING_VI = {'ON_TIME': 'Đúng giờ', 'LATE': 'Đi muộn', 'OK': 'Đúng giờ', 'EARLY': 'Về sớm', 'OFF_SCHEDULE': 'Ngoài lịch'}
FACE_VI = {'MATCH': 'Khớp', 'NO_MATCH': 'Không khớp', 'UNSURE': 'Chưa chắc', 'NO_FACE': 'Không thấy mặt',
           'SPOOF': 'Nghi chụp lại màn hình', 'UNAVAILABLE': 'AI chưa so'}
STATUS_VI = {'AUTO_OK': 'AI duyệt', 'NEEDS_REVIEW': 'Chờ Quản lý xem', 'APPROVED': 'Quản lý duyệt', 'REJECTED': 'Không tính'}


def photo_dir() -> Path:
    path = Path(os.environ.get('ATTENDANCE_PHOTO_DIR') or ROOT / 'data' / 'attendance_photos')
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_photo(data: bytes, prefix: str) -> str:
    from src.engine.face_verify import shrink
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


# --- network ---------------------------------------------------------------------------------------------

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


# --- face profiles ---------------------------------------------------------------------------------------

def face_profile(username: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        p = db.get(FaceProfile, username)
        return None if p is None else {'username': p.username, 'photo': p.photo_path, 'status': p.status,
                                       'consent_at': p.consent_at, 'reviewed_by': p.reviewed_by}


def enroll(username: str, photo: bytes, consent: bool) -> dict[str, Any]:
    if not consent:
        raise ValueError('Cần đồng ý cho cửa hàng lưu ảnh khuôn mặt để chấm công.')
    name = _save_photo(photo, f'face_{username}')
    with SessionLocal() as db:
        db.merge(FaceProfile(username=username, photo_path=name, status='PENDING', consent_at=datetime.now(),
                             reviewed_by=None, reviewed_at=None))
        db.commit()
    return face_profile(username)


def review_face(username: str, approve: bool, by: str) -> None:
    with SessionLocal() as db:
        p = db.get(FaceProfile, username)
        if p is None:
            raise ValueError('Không có ảnh đăng ký.')
        p.status, p.reviewed_by, p.reviewed_at = ('APPROVED' if approve else 'REJECTED'), by, datetime.now()
        db.commit()


def delete_face(username: str) -> None:
    """Withdraw consent: the reference photo and profile are removed."""
    with SessionLocal() as db:
        p = db.get(FaceProfile, username)
        if p:
            path = photo_dir() / p.photo_path
            if path.exists():
                path.unlink()
            db.delete(p)
            db.commit()


def pending_faces() -> list[dict[str, Any]]:
    names = {e['username']: e['full_name'] for e in ss.employees()}
    with SessionLocal() as db:
        return [{'username': p.username, 'full_name': names.get(p.username, p.username), 'photo': p.photo_path}
                for p in db.query(FaceProfile).filter(FaceProfile.status == 'PENDING')]


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


def _records(username: str, day: date) -> list[AttendanceRecord]:
    with SessionLocal() as db:
        return db.query(AttendanceRecord).filter(AttendanceRecord.username == username, AttendanceRecord.work_date == day,
                                                 AttendanceRecord.status != 'REJECTED').order_by(AttendanceRecord.at).all()


def state(username: str, now: datetime | None = None) -> dict[str, Any]:
    """What the staff page shows: today's block and whether the next action is IN or OUT."""
    now = now or ss.now_vn()
    rows = _records(username, now.date())
    last = rows[-1].kind if rows else None
    return {'block': today_block(username, now.date()), 'next': 'OUT' if last == 'IN' else 'IN',
            'records': [_row(r) for r in rows]}


def check(kind: str, username: str, selfie: bytes, ip: str | None, now: datetime | None = None,
          compare: Callable[[bytes, bytes], dict] | None = None) -> dict[str, Any]:
    """Record a check-in (IN) or check-out (OUT). Raises ValueError with a message the staff member sees."""
    if kind not in {'IN', 'OUT'}:
        raise ValueError('kind must be IN or OUT')
    now = now or ss.now_vn()
    if not on_shop_network(ip):
        raise ValueError('Chỉ chấm công được khi bắt WiFi của quán (đang không ở mạng của quán — tắt 4G và kết nối WiFi quán).')
    profile = face_profile(username)
    if not profile or profile['status'] != 'APPROVED':
        raise ValueError('Bạn chưa có ảnh khuôn mặt được Quản lý duyệt — đăng ký ở mục Chấm công trước.')
    current = state(username, now)
    if kind != current['next']:
        raise ValueError('Bạn đã check-in rồi, lần tiếp theo là check-out.' if kind == 'IN' else 'Bạn chưa check-in hôm nay.')
    if compare is None:
        from src.engine.face_verify import compare
    face = compare(read_photo(profile['photo']) or b'', selfie)
    when, minutes = timing(kind, current['block'], now)
    status = 'AUTO_OK' if face['result'] == 'MATCH' and when != 'OFF_SCHEDULE' else 'NEEDS_REVIEW'
    with SessionLocal() as db:
        rec = AttendanceRecord(username=username, work_date=now.date(), kind=kind, at=now.replace(tzinfo=None),
                               shift_codes=','.join(current['block']['shifts']) if current['block'] else None, ip=ip,
                               photo_path=_save_photo(selfie, f'{kind.lower()}_{username}'), face_result=face['result'],
                               face_confidence=face.get('confidence'), face_reason=(face.get('reason') or '')[:300],
                               timing=when, minutes=minutes, status=status)
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return _row(rec)


def _row(r: AttendanceRecord) -> dict[str, Any]:
    return {'id': r.id, 'username': r.username, 'date': r.work_date, 'kind': r.kind, 'at': r.at,
            'shifts': r.shift_codes.split(',') if r.shift_codes else [], 'face': r.face_result,
            'confidence': float(r.face_confidence) if r.face_confidence is not None else None,
            'reason': r.face_reason or '', 'timing': r.timing, 'minutes': r.minutes, 'status': r.status,
            'photo': r.photo_path, 'reviewed_by': r.reviewed_by}


def review(record_id: int, approve: bool, by: str) -> None:
    with SessionLocal() as db:
        r = db.get(AttendanceRecord, record_id)
        if r is None:
            raise ValueError('Không tìm thấy lượt chấm công.')
        r.status, r.reviewed_by, r.reviewed_at = ('APPROVED' if approve else 'REJECTED'), by, datetime.now()
        db.commit()


def needs_review() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        return [_row(r) for r in db.query(AttendanceRecord).filter(AttendanceRecord.status == 'NEEDS_REVIEW')
                .order_by(AttendanceRecord.at.desc()).limit(100)]


def timesheet(start: date, end: date) -> list[dict[str, Any]]:
    """One row per person per day that had a shift or a record: in/out times, late / early minutes."""
    names = {e['username']: e['full_name'] for e in ss.employees()}
    with SessionLocal() as db:
        recs = [_row(r) for r in db.query(AttendanceRecord).filter(AttendanceRecord.work_date >= start,
                AttendanceRecord.work_date <= end, AttendanceRecord.status != 'REJECTED').order_by(AttendanceRecord.at)]
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
