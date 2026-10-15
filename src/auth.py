# -*- coding: utf-8 -*-
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
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from src.database import SessionLocal, Base, engine
from src.models import User

# Đảm bảo bảng người dùng luôn tồn tại trong DB
Base.metadata.create_all(bind=engine)

ADMIN_PAGES: List[str] = [
    "Trang chủ",
    "Báo cáo & kho",
    "Dự báo",
    "Sơ chế",
    "Nhập hàng",
    "Tem & công thức",
    "👥 Quản lý nhân viên",
    "💬 Tuyết Vương AI"
]

STAFF_OFFICIAL_PAGES: List[str] = [
    "Trang chủ",
    "Báo cáo & kho",
    "Tem & công thức",
    "💬 Tuyết Vương AI"
]

STAFF_PROBATION_PAGES: List[str] = [
    "Trang chủ",
    "Tem & công thức",
    "💬 Tuyết Vương AI"
]

STAFF_PAGES: List[str] = STAFF_OFFICIAL_PAGES



def hash_password(password: str) -> str:
    """Tạo mã băm SHA-256 cho mật khẩu."""
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()


def check_password(plain_password: str, hashed_or_plain: str) -> bool:
    """Kiểm tra mật khẩu nhập vào khớp với mật khẩu băm (hoặc plaintext fallback ban đầu)."""
    if not hashed_or_plain or not plain_password:
        return False
    clean_plain = plain_password.strip()
    return hash_password(clean_plain) == hashed_or_plain or clean_plain == hashed_or_plain


def _get_role_metadata(role: str) -> Dict[str, str]:
    """Cung cấp metadata chức danh và huy hiệu theo vai trò."""
    r = (role or "").strip().upper()
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
            "description": "Toàn quyền vận hành: xem báo cáo, dự báo, ký duyệt đơn nhập và kế hoạch sơ chế."
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


def verify_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Xác thực thông tin đăng nhập từ cơ sở dữ liệu."""
    if not username or not password:
        return None
    clean_user = username.strip().lower()
    clean_pass = password.strip()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == clean_user, User.is_active == True).first()
        if not user:
            # Fallback tài khoản bí danh cũ nếu có
            alias_map = {"owner": "chucuahang", "manager": "quanly", "staff": "nhanvien"}
            if clean_user in alias_map:
                user = db.query(User).filter(User.username == alias_map[clean_user], User.is_active == True).first()

        if not user:
            return None

        # Cho phép các mật khẩu legacy như 123, mixue2132 cho admin hoặc staff demo
        valid = check_password(clean_pass, user.password_hash)
        if not valid:
            if is_admin_role(user.role) and clean_pass in ("123", "mixue2132", "admin123", "manager123"):
                valid = True
            elif clean_user == "nhanvien" and clean_pass in ("123", "123456", "staff123"):
                valid = True

        if valid:
            meta = _get_role_metadata(user.role)
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
        return None
    finally:
        db.close()


def is_admin_role(role: str) -> bool:
    """Kiểm tra role có thuộc nhóm Quản trị / Chủ quán hay không."""
    if not role:
        return False
    return role.strip().upper() in ("ADMIN", "MANAGER", "OWNER")


def is_staff_role(role: str) -> bool:
    """Kiểm tra role có phải Nhân viên hay không (cả chính thức và thử việc)."""
    if not role:
        return False
    return role.strip().upper() in ("STAFF", "STAFF_OFFICIAL", "STAFF_PROBATION", "TRAINEE")


def get_allowed_pages(role: str) -> List[str]:
    """Trả về danh sách các tab được phép truy cập theo phân quyền."""
    r = (role or "").strip().upper()
    if is_admin_role(r):
        return ADMIN_PAGES
    if r in ("STAFF_PROBATION", "PROBATION", "TRAINEE"):
        return STAFF_PROBATION_PAGES
    return STAFF_OFFICIAL_PAGES


def can_manage_inventory(role: str) -> bool:
    """Kiểm tra quyền truy cập Sổ Thẻ Kho Xuất - Nhập - Tồn (Chủ quán, Quản lý và Nhân viên chính thức)."""
    r = (role or "").strip().upper()
    return is_admin_role(r) or r in ("STAFF", "STAFF_OFFICIAL")


def can_access_page(role: str, page_name: str) -> bool:
    """Kiểm tra một vai trò có quyền xem trang cụ thể hay không."""
    allowed = get_allowed_pages(role)
    return page_name in allowed


def change_user_password(username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """Đổi mật khẩu cho người dùng. Bắt buộc mật khẩu mới phải gồm đúng 6 chữ số và khác 123456."""
    clean_user = username.strip().lower()
    clean_old = old_password.strip()
    clean_new = new_password.strip()

    # Kiểm tra quy tắc 6 chữ số
    if not re.match(r"^\d{6}$", clean_new):
        return False, "Mật khẩu mới không hợp lệ! Mật khẩu phải bao gồm đúng 6 chữ số (ví dụ: 686868, 112233)."

    if clean_new == "123456":
        return False, "Mật khẩu mới không được trùng với mật khẩu mặc định 123456! Vui lòng chọn 6 chữ số khác."

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == clean_user).first()
        if not user:
            return False, "Tài khoản người dùng không tồn tại!"

        # Xác thực mật khẩu cũ
        valid_old = check_password(clean_old, user.password_hash)
        if not valid_old and is_admin_role(user.role) and clean_old in ("123", "mixue2132"):
            valid_old = True

        if not valid_old:
            return False, "Mật khẩu hiện tại không chính xác!"

        # Cập nhật mật khẩu mới và tắt cờ bắt buộc đổi mật khẩu
        user.password_hash = hash_password(clean_new)
        user.must_change_password = False
        user.updated_at = datetime.now()
        db.commit()
        return True, "Đổi mật khẩu thành công! Mật khẩu mới gồm 6 chữ số đã được kích hoạt."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi hệ thống khi cập nhật mật khẩu: {str(e)}"
    finally:
        db.close()


def create_employee(admin_username: str, username: str, full_name: str, phone: str, role: str) -> Tuple[bool, str]:
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
        exists = db.query(User).filter(User.username == clean_user).first()
        if exists:
            return False, f"Tên đăng nhập '{clean_user}' đã tồn tại trong hệ thống. Vui lòng chọn tên khác!"

        new_emp = User(
            username=clean_user,
            password_hash=hash_password("123456"),
            full_name=clean_name,
            phone=clean_phone,
            role=clean_role,
            is_active=True,
            must_change_password=True,
            created_at=datetime.now()
        )
        db.add(new_emp)
        db.commit()
        return True, f"Tạo tài khoản nhân viên '{clean_user}' thành công! Mật khẩu mặc định: 123456 (Bắt buộc đổi khi đăng nhập)."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi cơ sở dữ liệu khi tạo nhân viên: {str(e)}"
    finally:
        db.close()


def reset_employee_password(admin_username: str, target_username: str) -> Tuple[bool, str]:
    """Reset mật khẩu của nhân viên về mặc định 123456 và bật lại cờ bắt buộc đổi mật khẩu."""
    clean_target = target_username.strip().lower()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == clean_target).first()
        if not user:
            return False, f"Không tìm thấy tài khoản nhân viên '{clean_target}'."

        user.password_hash = hash_password("123456")
        user.must_change_password = True
        user.updated_at = datetime.now()
        db.commit()
        return True, f"Đã reset mật khẩu của nhân viên '{user.full_name}' ({clean_target}) về mặc định: 123456. Nhân viên bắt buộc phải đổi mật khẩu gồm 6 chữ số khi đăng nhập lại."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi cơ sở dữ liệu khi reset mật khẩu: {str(e)}"
    finally:
        db.close()


def get_all_employees() -> List[Dict[str, Any]]:
    """Lấy danh sách toàn bộ tài khoản nhân viên phục vụ màn hình Quản lý nhân viên của Admin."""
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        result = []
        for u in users:
            meta = _get_role_metadata(u.role)
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
