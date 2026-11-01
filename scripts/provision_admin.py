"""Provision an administrator explicitly; no default credential is installed at import."""

import argparse
from getpass import getpass
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


DEMO_PASSWORDS = ("123", "123456")


def provision_from_env(env=None):
    """First boot on a server: create the owner from OWNER_USERNAME / OWNER_INITIAL_PASSWORD.

    Never overwrites a real password: an existing account is only touched while it still
    uses a published demo password. The owner must change the initial password on first login.
    Returns a short status string (never the password).
    """
    import os
    env = os.environ if env is None else env
    username = (env.get("OWNER_USERNAME") or "").strip().lower()
    password = env.get("OWNER_INITIAL_PASSWORD") or ""
    if not username and not password:
        return "SKIPPED"
    if not re.fullmatch(r"[a-z0-9_]{3,30}", username):
        return "INVALID_USERNAME"
    if not 12 <= len(password) <= 128 or password in DEMO_PASSWORDS:
        return "WEAK_PASSWORD"
    from src.auth import check_password, hash_password
    from src.database import SessionLocal
    from src.models import User

    with SessionLocal() as db:
        account = db.get(User, username)
        if account is not None and not any(check_password(p, account.password_hash) for p in DEMO_PASSWORDS):
            return "EXISTS"
        if account is None:
            account = User(username=username)
            db.add(account)
        account.full_name = (env.get("OWNER_FULL_NAME") or "Chủ cửa hàng").strip()
        account.password_hash = hash_password(password)
        account.role = "ADMIN"
        account.is_active = True
        account.must_change_password = True
        db.commit()
    return "PROVISIONED"


def main():
    if "--from-env" in sys.argv[1:]:
        print(f"Owner bootstrap: {provision_from_env()}")
        return
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
