"""One-click export of everything the shop has written: database, shift reports, photos, chat history, audit.

The paths are the live ones (PERSIST_DIR on a server, data/ locally). SQLite files are copied with SQLite's own
backup API, so a database being written while the export runs is still consistent. The archive carries a
manifest with a SHA-256 per file; scripts/restore_export.py checks it before restoring.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sources() -> dict[str, Path]:
    """name in the archive -> live path."""
    from src.agent.config import AgentSettings
    from src.database import DATABASE_URL
    from src.engine import shift_service
    from src.engine.llm_usage import db_path
    cfg = AgentSettings.from_env()
    out: dict[str, Path] = {}
    if DATABASE_URL.startswith('sqlite:///'):
        out['beverageops.db'] = Path(DATABASE_URL.removeprefix('sqlite:///'))
    out['shift_reports.json'] = shift_service.SHIFT_DATA_FILE
    out['agent_private/ocr_user_edits.jsonl'] = shift_service.OCR_EDITS_LOG_FILE
    out['agent_private/checkpoints.sqlite'] = Path(cfg.checkpoint_path)
    out['agent_private/audit.jsonl'] = Path(cfg.audit_path)
    out['agent_private/llm_usage.db'] = db_path()
    out['shift_uploads'] = shift_service.SHIFT_UPLOADS_DIR
    out['chat_attachments'] = Path(os.environ.get('CHAT_ATTACHMENTS_DIR') or ROOT / 'data' / 'shift_photos' / 'chat_attachments')
    return out


def _sqlite_copy(src: Path, dst: Path) -> None:
    with sqlite3.connect(src.resolve().as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(dst) as target:
        source.backup(target)


def _dump_tables(zf: zipfile.ZipFile, manifest: dict) -> None:
    """PostgreSQL (or any non-file database): every ORM table as CSV, plus the row counts."""
    import csv
    import io

    from sqlalchemy import select

    from src.database import Base, engine
    import src.models  # noqa: F401
    with engine.connect() as db:
        for table in Base.metadata.sorted_tables:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(table.columns.keys())
            count = 0
            for row in db.execute(select(table)):
                writer.writerow(['' if v is None else v for v in row])
                count += 1
            data = buf.getvalue().encode('utf-8')
            name = f'database/{table.name}.csv'
            zf.writestr(name, data)
            manifest['files'].append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'rows': count})


def build_export() -> Path:
    """Write a zip to a temporary file and return its path (the caller deletes it)."""
    manifest = {'version': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'files': []}
    fd, name = tempfile.mkstemp(prefix='beverageops-export-', suffix='.zip')
    os.close(fd)
    out = Path(name)
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for arc, path in sources().items():
            files = sorted(p for p in path.rglob('*') if p.is_file()) if path.is_dir() else ([path] if path.is_file() else [])
            for f in files:
                rel = arc if f == path else f'{arc}/{f.relative_to(path).as_posix()}'
                if f.suffix in {'.db', '.sqlite', '.sqlite3'}:
                    copy = Path(tmp) / hashlib.sha1(rel.encode()).hexdigest()
                    _sqlite_copy(f, copy)
                    f = copy
                digest = hashlib.sha256(f.read_bytes()).hexdigest()
                zf.write(f, rel)
                manifest['files'].append({'path': rel, 'sha256': digest, 'bytes': f.stat().st_size})
        from src.database import DATABASE_URL
        if not DATABASE_URL.startswith('sqlite:///'):
            manifest['database'] = 'postgresql'
            _dump_tables(zf, manifest)
        zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=1))
    return out


def export_bytes() -> tuple[bytes, str]:
    path = build_export()
    try:
        stamp = datetime.now().strftime('%Y%m%d_%H%M')
        return path.read_bytes(), f'beverageops_backup_{stamp}.zip'
    finally:
        path.unlink(missing_ok=True)


def verify(zip_path: Path) -> list[str]:
    """Problems found in an export (empty list = every file matches its checksum)."""
    problems = []
    with zipfile.ZipFile(zip_path) as zf:
        manifest = json.loads(zf.read('manifest.json'))
        for entry in manifest['files']:
            if hashlib.sha256(zf.read(entry['path'])).hexdigest() != entry['sha256']:
                problems.append(entry['path'])
    return problems
