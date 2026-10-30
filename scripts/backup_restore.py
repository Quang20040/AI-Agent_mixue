"""Offline verified backups covering SQLite, shift JSON, checkpoints and uploaded media."""

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from src.engine.backup_bundle import BackupBundle, integrity
from src.runtime_settings import setting

BACKUP_DIR = REPO_ROOT / "backups"


def verify_integrity(db_path):
    return integrity(Path(db_path))


def _check_backend():
    if setting("DATABASE_URL", "").startswith(("postgres", "postgresql")):
        raise ValueError("PostgreSQL cần pg_dump/restore riêng; công cụ này chỉ phục hồi SQLite và dữ liệu file.")
    configured = setting("DATABASE_URL")
    if configured:
        from sqlalchemy.engine import make_url

        path = make_url(configured).database
        if not path or path == ":memory:" or not Path(path).resolve().is_relative_to(REPO_ROOT / "data"):
            raise ValueError("DATABASE_URL ngoài data/ cần quy trình backup riêng; không sao lưu nhầm DB mặc định.")
    for name in ("AGENT_CHECKPOINT_PATH", "AGENT_CONVERSATION_PATH"):
        value = setting(name)
        if value and not Path(value).resolve().is_relative_to(REPO_ROOT / "data"):
            raise ValueError("Datastore ngoài data/ cần quy trình backup riêng.")


def create_backup(*, maintenance=False):
    _check_backend()
    return BackupBundle(REPO_ROOT, BACKUP_DIR).create(maintenance=maintenance)


def list_backups():
    return BackupBundle(REPO_ROOT, BACKUP_DIR).list()


def restore_backup(stamp, *, maintenance=False):
    _check_backend()
    return BackupBundle(REPO_ROOT, BACKUP_DIR).restore(stamp, maintenance=maintenance)


def main():
    parser = argparse.ArgumentParser(description="Backup/restore trong thời gian bảo trì; dừng worker ghi trước khi chạy.")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--restore")
    parser.add_argument("--maintenance", action="store_true", help="Xác nhận các worker đã dừng ghi dữ liệu")
    args = parser.parse_args()
    if args.list:
        print("\n".join(list_backups()) or "Chưa có bundle hoàn tất.")
        return
    try:
        ok, message = (
            restore_backup(args.restore, maintenance=args.maintenance) if args.restore else create_backup(maintenance=args.maintenance)
        )
    except ValueError as exc:
        ok, message = False, str(exc)
    print(message)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
