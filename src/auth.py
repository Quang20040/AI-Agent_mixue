"""Hệ thống Quản lý Người dùng & Phân quyền (RBAC) - Mixue 39 Tôn Quang Phiệt.

Phân quyền 2 cấp độ:
1. ADMIN (Chủ cửa hàng & Quản lý):
   - Toàn quyền kiểm tra số liệu, xem toàn bộ báo cáo, doanh thu, dự báo, kiểm kê, đơn nhập hàng, duyệt kế hoạch.
   - Quản lý danh sách nhân viên, đăng ký tài khoản mới, reset mật khẩu nhân viên về 123456.
   - Toàn quyền chat với Tuyết Vương AI về mọi tác vụ vận hành & kinh doanh.
2. STAFF (Nhân viên chính thức & Nhân viên thử việc/mới):
   - Chỉ được xem thực đơn, công thức sản phẩm (BOM) và giải mã tem dán ly.
   - Đăng nhập lần đầu bắt buộc phải đổi mật khẩu riêng gồm đúng 6 chữ số.
   - Bị ẩn các trang quản trị: Báo cáo & Kho, Dự báo, Sơ chế mẻ lớn, Đơn nhập hàng PO, Quản lý nhân viên.
   - Chat với Tuyết Vương AI: CHỈ được hỏi về công thức pha chế hoặc hướng dẫn sơ chế nguyên liệu.
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from src.database import Base, SessionLocal, engine
from src.models import LoginThrottle, User
from src.runtime_settings import demo_enabled
from sqlalchemy import case, update

# Đảm bảo bảng người dùng luôn tồn tại trong DB
Base.metadata.create_all(bind=engine)

CHAT_PAGE = "💬 Tuyết Vương AI"
OCR_PAGE = "📸 Chốt ca & OCR"
SCHEDULE_PAGE = "📅 Lịch làm"

# Two technical pillars of the thesis, shown first on every navigation surface.
CORE_PAGES: tuple[str, ...] = (CHAT_PAGE, OCR_PAGE)
# Deterministic tools that feed the agent and reconciliation with data.
SUPPORT_PAGES: tuple[str, ...] = ("Báo cáo & kho", "Dự báo", "Sơ chế", "Nhập hàng", "Tem & công thức", SCHEDULE_PAGE)
AI_TECH_PAGE = "🛠️ Kỹ thuật AI"
ADMIN_ONLY_PAGES: tuple[str, ...] = ("👥 Quản lý nhân viên", AI_TECH_PAGE)

ADMIN_PAGES: list[str] = [
    "Trang chủ",
    CHAT_PAGE,
    OCR_PAGE,
    "Báo cáo & kho",
    "Dự báo",
    "Sơ chế",
    "Nhập hàng",
    "Tem & công thức",
    SCHEDULE_PAGE,
    "👥 Quản lý nhân viên",
    AI_TECH_PAGE,
]

STAFF_OFFICIAL_PAGES: list[str] = [
    "Trang chủ",
    CHAT_PAGE,
    OCR_PAGE,
    "Báo cáo & kho",
    "Tem & công thức",
    SCHEDULE_PAGE,
]

STAFF_PROBATION_PAGES: list[str] = [
    "Trang chủ",
    CHAT_PAGE,
    "Tem & công thức",
    SCHEDULE_PAGE,
]


def page_group(page: str) -> str:
    """Navigation group of a page: 'home', 'core', 'support' or 'admin'."""
    if page in CORE_PAGES:
        return "core"
    if page in SUPPORT_PAGES:
        return "support"
    if page in ADMIN_ONLY_PAGES:
        return "admin"
    return "home"


def hash_password(password: str, salt: str | None = None) -> str:
    """Tạo mã băm bảo mật PBKDF2-HMAC-SHA256 với Salt ngẫu nhiên 16 bytes (chuẩn NIST/OWASP)."""
    clean_pw = password.strip()
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", clean_pw.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"pbkdf2_sha256$100000${salt}${key.hex()}"


def check_password(plain_password: str, hashed_password: str) -> bool:
    """Kiểm tra mật khẩu bảo mật chống timing attack và bẻ khóa Rainbow table.
    Hỗ trợ cả chuẩn PBKDF2 mới và chuẩn SHA-256 cũ (backward-compatible).
    Tuyệt đối không cho phép plaintext fallback.
    """
    if not hashed_password or not plain_password:
        return False
    clean_plain = plain_password.strip()

    # 1. Định dạng PBKDF2 chuẩn bảo mật mới: pbkdf2_sha256$iterations$salt$hash
    if hashed_password.startswith("pbkdf2_sha256$"):
        parts = hashed_password.split("$")
        if len(parts) == 4:
            try:
                iterations = int(parts[1])
                salt = parts[2]
                stored_hash = parts[3]
                calculated = hashlib.pbkdf2_hmac("sha256", clean_plain.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
                return secrets.compare_digest(calculated, stored_hash)
            except Exception:
                return False

    # 2. Định dạng SHA-256 cũ (chuyển tiếp an toàn cho tài khoản hiện có trong DB)
    if len(hashed_password) == 64 and re.fullmatch(r"[0-9a-fA-F]{64}", hashed_password):
        legacy_hash = hashlib.sha256(clean_plain.encode("utf-8")).hexdigest()
        return secrets.compare_digest(legacy_hash, hashed_password)

    return False


def _owner_usernames() -> set[str]:
    """Accounts shown as the shop owner; other ADMIN accounts are shown as managers (same permissions)."""
    import os
    names = {"chucuahang", (os.environ.get("OWNER_USERNAME") or "").strip().lower()}
    return {n for n in names if n}


def _get_role_metadata(role: str, username: str | None = None) -> dict[str, str]:
    """Cung cấp metadata chức danh và huy hiệu theo vai trò."""
    r = (role or "").strip().upper()
    if r == "ADMIN" and username and username.strip().lower() not in _owner_usernames():
        r = "MANAGER"
    if r in ("ADMIN", "OWNER"):
        return {
            "title": "Chủ quán (Owner / Admin)",
            "badge": "👑 Chủ Cửa Hàng (Admin)",
            "description": "Toàn quyền quản trị, kiểm soát doanh thu, đối soát kho và phê duyệt vận hành."
        }
    if r in ("MANAGER",):
        return {
            "title": "Quản lý điều hành (Manager / Admin)",
            "badge": "🛡️ Quản Lý Cửa Hàng (Admin)",
            "description": "Toàn quyền vận hành: xem báo cáo, dự báo, ký duyệt đơn nhập và phiếu kho."
        }
    if r in ("STAFF_PROBATION", "PROBATION", "TRAINEE"):
        return {
            "title": "Nhân viên thử việc (Probationary Staff)",
            "badge": "🌱 Nhân Viên Thử Việc (Trainee)",
            "description": "Học việc, tra cứu công thức pha chế, giải mã tem dán ly và SOP sơ chế."
        }
    # Mặc định là nhân viên chính thức
    return {
        "title": "Nhân viên pha chế (Official Barista)",
        "badge": "☕ Nhân Viên Chính Thức (Staff)",
        "description": "Tra cứu công thức pha chế, giải mã tem dán ly và hướng dẫn sơ chế nguyên liệu."
    }


def init_db_users():
    """Khởi tạo các tài khoản chuẩn chi nhánh Mixue 39 Tôn Quang Phiệt nếu cơ sở dữ liệu chưa có."""
    if not demo_enabled():
        return
    db = SessionLocal()
    try:
        count = db.query(User).count()
        if count == 0:
            default_users = [
                # 1. Chủ quán
                User(
                    username="chucuahang",
                    password_hash=hash_password("123"),
                    full_name="Nguyễn Hạnh Chi",
                    phone="0987654321",
                    role="ADMIN",
                    is_active=True,
                    must_change_password=False,
                    created_at=datetime.now()
                ),
                # 2. Quản lý
                User(
                    username="quanly",
                    password_hash=hash_password("123"),
                    full_name="Bùi Văn Quang",
                    phone="0912345678",
                    role="ADMIN",
                    is_active=True,
                    must_change_password=False,
                    created_at=datetime.now()
                ),
                # 3. Nhân viên chính thức (tài khoản demo chi nhánh)
                User(
                    username="nhanvien",
                    password_hash=hash_password("123"),
                    full_name="Lê Thị Thảo (Quầy Bar)",
                    phone="0905111222",
                    role="STAFF",
                    is_active=True,
                    must_change_password=False,
                    created_at=datetime.now()
                ),
                # 4. Nhân viên thử việc (mới)
                User(
                    username="nhanvien_moi",
                    password_hash=hash_password("123456"),
                    full_name="Trần Văn Nam (Thử việc)",
                    phone="0934555666",
                    role="STAFF_PROBATION",
                    is_active=True,
                    must_change_password=True,
                    created_at=datetime.now()
                ),
            ]
            db.add_all(default_users)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[auth] Lỗi khởi tạo users: {e}")
    finally:
        db.close()


# Tự động nạp tài khoản ban đầu nếu chưa có
init_db_users()


def verify_user(username: str, password: str) -> dict[str, Any] | None:
    """Xác thực thông tin đăng nhập từ cơ sở dữ liệu."""
    if not username or not password:
        return None
    clean_user = username.strip().lower()
    clean_pass = password.strip()
    aliases = {'owner': 'chucuahang', 'manager': 'quanly', 'staff': 'nhanvien'}
    clean_user = aliases.get(clean_user, clean_user)
    if len(clean_user) > 50:
        return None

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        throttle = db.get(LoginThrottle, clean_user)
        if throttle and throttle.blocked_until and throttle.blocked_until > now:
            return None
        if throttle and (throttle.blocked_until or now - throttle.last_attempt_at > timedelta(minutes=5)):
            throttle.failed_attempts = 0
            throttle.blocked_until = None
            db.commit()
        user = db.query(User).filter(User.username == clean_user, User.is_active).first()
        if not user:
            # Fallback tài khoản bí danh cũ nếu có
            alias_map = {"owner": "chucuahang", "manager": "quanly", "staff": "nhanvien"}
            if clean_user in alias_map:
                user = db.query(User).filter(User.username == alias_map[clean_user], User.is_active).first()

        valid = bool(user and check_password(clean_pass, user.password_hash))
        if user and normalize_role(user.role) not in {'ADMIN', 'MANAGER', 'OWNER', 'STAFF_OFFICIAL', 'STAFF_PROBATION'}:
            valid = False
        # Previously seeded demo credentials remain disabled outside explicit demo.
        if not demo_enabled() and clean_pass in {'123', '123456'}:
            valid = False
        if valid:
            if throttle:
                db.delete(throttle)
                db.commit()
            # Tự động nâng cấp hash mật khẩu cũ sang chuẩn PBKDF2 nếu chưa nâng cấp
            if not user.password_hash.startswith("pbkdf2_"):
                try:
                    user.password_hash = hash_password(clean_pass)
                    db.commit()
                except Exception:
                    db.rollback()

            meta = _get_role_metadata(user.role, user.username)
            return {
                "username": user.username,
                "name": user.full_name,
                "phone": user.phone or "",
                "role": user.role,
                "title": meta["title"],
                "badge": meta["badge"],
                "description": meta["description"],
                "must_change_password": bool(user.must_change_password),
                "is_active": bool(user.is_active)
            }
        dialect = db.get_bind().dialect.name
        if dialect == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        db.execute(insert(LoginThrottle).values(username=clean_user, failed_attempts=0, last_attempt_at=now)
                   .on_conflict_do_nothing(index_elements=['username']))
        db.execute(update(LoginThrottle).where(LoginThrottle.username == clean_user).values(
            failed_attempts=LoginThrottle.failed_attempts + 1,
            last_attempt_at=now,
            blocked_until=case((LoginThrottle.failed_attempts + 1 >= 8, now + timedelta(seconds=60)),
                               else_=LoginThrottle.blocked_until)))
        db.commit()
        return None
    finally:
        db.close()


def is_admin_role(role: str) -> bool:
    """Kiểm tra role có thuộc nhóm Quản trị / Chủ quán hay không."""
    if not role:
        return False
    return role.strip().upper() in ("ADMIN", "MANAGER", "OWNER")


def normalize_role(role: str) -> str:
    role = (role or "").strip().upper()
    return {"STAFF": "STAFF_OFFICIAL", "PROBATION": "STAFF_PROBATION", "TRAINEE": "STAFF_PROBATION"}.get(role, role)


def is_staff_role(role: str) -> bool:
    """Kiểm tra role có phải Nhân viên hay không (cả chính thức và thử việc)."""
    if not role:
        return False
    return role.strip().upper() in ("STAFF", "STAFF_OFFICIAL", "STAFF_PROBATION", "TRAINEE")


def get_allowed_pages(role: str) -> list[str]:
    """Trả về danh sách các tab được phép truy cập theo phân quyền."""
    r = (role or "").strip().upper()
    if is_admin_role(r):
        return ADMIN_PAGES
    if r in ("STAFF_PROBATION", "PROBATION", "TRAINEE"):
        return STAFF_PROBATION_PAGES
    if normalize_role(r) == 'STAFF_OFFICIAL':
        return STAFF_OFFICIAL_PAGES
    return []


def can_access_page(role: str, page_name: str) -> bool:
    """Kiểm tra một vai trò có quyền xem trang cụ thể hay không."""
    allowed = get_allowed_pages(role)
    return page_name in allowed


def change_user_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """Đổi mật khẩu cho người dùng. Bắt buộc mật khẩu mới phải gồm đúng 6 chữ số và khác 123456."""
    clean_user = username.strip().lower()
    clean_old = old_password.strip()
    clean_new = new_password.strip()

    # Kiểm tra quy tắc 6 chữ số
    if demo_enabled() and not re.match(r"^\d{6}$", clean_new):
        return False, "Mật khẩu mới không hợp lệ! Mật khẩu phải bao gồm đúng 6 chữ số (ví dụ: 686868, 112233)."
    if not demo_enabled() and not 12 <= len(clean_new) <= 128:
        return False, 'Mật khẩu mới phải có từ 12 đến 128 ký tự.'

    if clean_new == "123456":
        return False, "Mật khẩu mới không được trùng với mật khẩu mặc định 123456! Vui lòng chọn 6 chữ số khác."

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == clean_user).first()
        if not user:
            return False, "Tài khoản người dùng không tồn tại!"

        # Xác thực mật khẩu cũ
        valid_old = check_password(clean_old, user.password_hash)
        if not valid_old:
            return False, "Mật khẩu hiện tại không chính xác!"

        # Cập nhật mật khẩu mới và tắt cờ bắt buộc đổi mật khẩu
        user.password_hash = hash_password(clean_new)
        user.must_change_password = False
        user.updated_at = datetime.now()
        db.commit()
        return True, 'Đổi mật khẩu thành công!'
    except Exception as e:
        db.rollback()
        return False, f"Lỗi hệ thống khi cập nhật mật khẩu: {e!s}"
    finally:
        db.close()


def create_employee(admin_username: str, username: str, full_name: str, phone: str, role: str) -> tuple[bool, str]:
    """Đăng ký tài khoản nhân viên mới (Chỉ dành cho Admin/Quản lý). Mật khẩu mặc định là 123456."""
    clean_user = username.strip().lower()
    clean_name = full_name.strip()
    clean_phone = phone.strip()
    clean_role = role.strip().upper()

    if not re.match(r"^[a-z0-9_]{3,30}$", clean_user):
        return False, "Tên đăng nhập không hợp lệ! Phải từ 3-30 ký tự, chỉ gồm chữ thường không dấu, số hoặc dấu gạch dưới (_)."

    if len(clean_name) < 2:
        return False, "Họ và tên nhân viên không được để trống!"

    if clean_role not in ("STAFF_OFFICIAL", "STAFF_PROBATION", "ADMIN"):
        clean_role = "STAFF_OFFICIAL"

    db = SessionLocal()
    try:
        actor = db.get(User, admin_username.strip().lower())
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, "Chỉ quản lý đang hoạt động được quản lý nhân viên."
        exists = db.query(User).filter(User.username == clean_user).first()
        if exists:
            return False, f"Tên đăng nhập '{clean_user}' đã tồn tại trong hệ thống. Vui lòng chọn tên khác!"

        temporary_password = '123456' if demo_enabled() else secrets.token_urlsafe(16)
        new_emp = User(
            username=clean_user,
            password_hash=hash_password(temporary_password),
            full_name=clean_name,
            phone=clean_phone,
            role=clean_role,
            is_active=True,
            must_change_password=True,
            created_at=datetime.now()
        )
        db.add(new_emp)
        db.commit()
        return True, f"Tạo tài khoản nhân viên '{clean_user}' thành công! Mật khẩu tạm: {temporary_password} (Bắt buộc đổi khi đăng nhập)."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi cơ sở dữ liệu khi tạo nhân viên: {e!s}"
    finally:
        db.close()


def reset_employee_password(admin_username: str, target_username: str) -> tuple[bool, str]:
    """Reset mật khẩu của nhân viên về mặc định 123456 và bật lại cờ bắt buộc đổi mật khẩu."""
    clean_target = target_username.strip().lower()

    db = SessionLocal()
    try:
        actor = db.get(User, admin_username.strip().lower())
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, "Chỉ quản lý đang hoạt động được quản lý nhân viên."
        user = db.query(User).filter(User.username == clean_target).first()
        if not user:
            return False, f"Không tìm thấy tài khoản nhân viên '{clean_target}'."

        temporary_password = '123456' if demo_enabled() else secrets.token_urlsafe(16)
        user.password_hash = hash_password(temporary_password)
        user.must_change_password = True
        user.updated_at = datetime.now()
        db.commit()
        return True, f"Đã reset mật khẩu của '{clean_target}'. Mật khẩu tạm: {temporary_password}. Bắt buộc đổi khi đăng nhập lại."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi cơ sở dữ liệu khi reset mật khẩu: {e!s}"
    finally:
        db.close()


def get_all_employees() -> list[dict[str, Any]]:
    """Lấy danh sách toàn bộ tài khoản nhân viên phục vụ màn hình Quản lý nhân viên của Admin."""
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        result = []
        for u in users:
            meta = _get_role_metadata(u.role, u.username)
            result.append({
                "username": u.username,
                "full_name": u.full_name,
                "phone": u.phone or "—",
                "role": u.role,
                "role_badge": meta["badge"],
                "role_title": meta["title"],
                "must_change_password": u.must_change_password,
                "is_active": u.is_active,
                "created_at": u.created_at.strftime("%d/%m/%Y %H:%M") if u.created_at else "—",
                "updated_at": u.updated_at.strftime("%d/%m/%Y %H:%M") if u.updated_at else "—",
            })
        return result
    finally:
        db.close()


def update_employee(admin_username: str, target_username: str, full_name: str, phone: str,
                    role: str, is_active: bool = True) -> tuple[bool, str]:
    """Update personnel with the same authorization and role rules as creation."""
    clean_role = normalize_role(role)
    if len(full_name.strip()) < 2 or clean_role not in ("STAFF_OFFICIAL", "STAFF_PROBATION", "ADMIN", "MANAGER", "OWNER"):
        return False, "Họ tên hoặc vai trò không hợp lệ."
    with SessionLocal() as db:
        actor = db.get(User, admin_username.strip().lower())
        user = db.get(User, target_username)
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, "Chỉ quản lý đang hoạt động được quản lý nhân viên."
        if not user:
            return False, "Không tìm thấy nhân viên."
        if user.username == actor.username and (not is_active or not is_admin_role(clean_role)):
            return False, "Không thể tự khóa hoặc hạ quyền tài khoản đang sử dụng."
        if user.is_active and is_admin_role(user.role) and (not is_active or not is_admin_role(clean_role)):
            other_admins = [u for u in db.query(User).filter(User.is_active).all()
                            if u.username != user.username and is_admin_role(u.role)]
            if not other_admins:
                return False, "Phải giữ lại ít nhất một quản lý đang hoạt động."
        user.full_name, user.phone, user.role = full_name.strip(), phone.strip(), clean_role
        user.is_active = is_active
        db.commit()
        return True, "Đã lưu thông tin nhân viên."


def delete_employee(admin_username: str, target_username: str) -> tuple[bool, str]:
    """Remove an employee account; operational audit names remain in history."""
    with SessionLocal() as db:
        actor = db.get(User, admin_username.strip().lower())
        user = db.get(User, target_username)
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, "Chỉ quản lý đang hoạt động được quản lý nhân viên."
        if not user:
            return False, "Không tìm thấy nhân viên."
        if user.username == actor.username:
            return False, "Không thể xóa tài khoản đang sử dụng."
        db.delete(user)
        db.commit()
        return True, "Đã xóa tài khoản nhân viên. Lịch sử vận hành được giữ lại."
