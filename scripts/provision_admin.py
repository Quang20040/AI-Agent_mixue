"""Provision an administrator explicitly; no default credential is installed at import."""

import argparse
from getpass import getpass
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description="Tạo tài khoản quản lý đầu tiên hoặc đặt lại mật khẩu quản lý.")
    parser.add_argument("username")
    parser.add_argument("--name", required=True)
    parser.add_argument("--reset-existing", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_]{3,30}", args.username):
        parser.error("Tên tài khoản phải có 3–30 ký tự chữ thường, số hoặc gạch dưới.")
    password = getpass("Mật khẩu mới (12–128 ký tự): ")
    if not 12 <= len(password) <= 128 or password != getpass("Nhập lại mật khẩu: "):
        parser.error("Mật khẩu không hợp lệ hoặc xác nhận không khớp.")
    from src.auth import hash_password
    from src.database import SessionLocal
    from src.models import User

    with SessionLocal() as db:
        account = db.get(User, args.username)
        if account and not args.reset_existing:
            parser.error("Tài khoản đã tồn tại; dùng --reset-existing nếu chủ động đặt lại.")
        if account is None:
            account = User(username=args.username)
            db.add(account)
        account.full_name = args.name
        account.password_hash = hash_password(password)
        account.role = "ADMIN"
        account.is_active = True
        account.must_change_password = False
        db.commit()
    print("Đã cấp tài khoản quản lý. Mật khẩu không được ghi vào log hoặc tham số dòng lệnh.")


if __name__ == "__main__":
    main()
