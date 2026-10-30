"""Verified SQLite/JSON/media bundles. Cross-store consistency requires maintenance mode."""

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime, timezone
import uuid


def integrity(path):
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            return db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    except (sqlite3.Error, OSError):
        return False


class BackupBundle:
    def __init__(self, root, backup_dir=None):
        self.root = Path(root).resolve()
        self.directory = Path(backup_dir or self.root / "backups").resolve()
        if self.directory.is_relative_to(self.root / "data"):
            raise ValueError("Thư mục backup phải nằm ngoài data/.")

    @staticmethod
    def checksum(path):
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _target(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root / "data"):
            raise ValueError("Bundle chứa đường dẫn ngoài thư mục dữ liệu.")
        return path

    def list(self):
        return sorted([p.name for p in self.directory.glob("snapshot_*") if p.is_dir() and (p / "manifest.json").is_file()], reverse=True)

    def create(self, *, maintenance=False):
        if not maintenance:
            return False, "Cần dừng các worker ghi dữ liệu và bật --maintenance để sao lưu nhất quán."
        stamp = "snapshot_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        bundle = self.directory / stamp
        bundle.mkdir(parents=True)
        manifest = {"version": 1, "at": datetime.now(timezone.utc).isoformat(), "maintenance": True, "files": []}
        try:
            for source in sorted((self.root / "data").rglob("*")):
                if not source.is_file() or source.name.endswith(("-wal", "-shm", ".lock", ".tmp")):
                    continue
                relative = source.relative_to(self.root).as_posix()
                self._target(relative)
                destination = bundle / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                kind = "sqlite" if source.suffix in {".db", ".sqlite", ".sqlite3"} else "file"
                if kind == "sqlite":
                    if not integrity(source):
                        raise ValueError(f"SQLite integrity check không đạt: {source.name}")
                    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as source_db:
                        with sqlite3.connect(destination) as target_db:
                            source_db.backup(target_db)
                    if not integrity(destination):
                        raise ValueError("Bản sao SQLite không hợp lệ.")
                else:
                    if source.name == "shift_reports.json":
                        data = json.loads(source.read_text(encoding="utf-8"))
                        if not isinstance(data, list):
                            raise ValueError("Shift JSON không hợp lệ.")
                    shutil.copy2(source, destination)
                manifest["files"].append({"path": relative, "kind": kind, "sha256": self.checksum(destination)})
            if not manifest["files"]:
                raise ValueError("Không có tệp dữ liệu để sao lưu.")
            # Publish the manifest last; partial bundles are never listed as restorable.
            (bundle / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            return True, stamp
        except (OSError, ValueError, sqlite3.Error) as exc:
            return False, f"Sao lưu chưa hoàn tất: {exc}"

    def restore(self, stamp, *, maintenance=False):
        if not maintenance:
            return False, "Cần dừng các worker và bật --maintenance trước khi phục hồi."
        if stamp not in self.list():
            return False, "Không tìm thấy bản sao lưu hoàn tất."
        bundle = self.directory / stamp
        try:
            manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            files = manifest.get("files", [])
            if manifest.get("version") != 1 or not files:
                raise ValueError("Manifest không hợp lệ.")
            # Verify every file and every path before changing any live file.
            seen = set()
            for item in files:
                target = self._target(item["path"])
                source = (bundle / item["path"]).resolve()
                if not source.is_relative_to(bundle) or item["path"] in seen or item["kind"] not in {"sqlite", "file"}:
                    raise ValueError("Manifest có đường dẫn hoặc kiểu tệp không hợp lệ.")
                seen.add(item["path"])
                if not source.is_file() or self.checksum(source) != item["sha256"]:
                    raise ValueError("Checksum bản sao lưu không khớp; không thay đổi dữ liệu hiện tại.")
                if item["kind"] == "sqlite" and not integrity(source):
                    raise ValueError("Bản sao SQLite không hợp lệ.")
            # Preserve even corrupted live files before repairing them. This raw
            # forensic copy is deliberately not listed as a verified snapshot.
            for current in (self.root / "data").rglob("*"):
                if current.is_file():
                    self._target(current.relative_to(self.root).as_posix())
            safety = "safety_" + uuid.uuid4().hex
            shutil.copytree(self.root / "data", self.directory / safety / "data")
            for item in files:
                target = self._target(item["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle / item["path"]
                if item["kind"] == "sqlite":
                    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as source_db:
                        with sqlite3.connect(target) as target_db:
                            source_db.backup(target_db)
                else:
                    temporary = target.with_suffix(target.suffix + ".restore.tmp")
                    shutil.copy2(source, temporary)
                    temporary.replace(target)
            return True, f"Đã phục hồi. Safety snapshot: {safety}. Tệp phát sinh sau snapshot được giữ lại, không tự xóa."
        except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
            return False, f"Không hoàn tất phục hồi; giữ worker dừng và kiểm tra safety snapshot: {exc}"
