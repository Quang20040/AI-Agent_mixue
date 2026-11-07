"""Container start-up when DATABASE_URL points at PostgreSQL.

1. Create the tables (idempotent).
2. If PostgreSQL is still empty, copy the shop's SQLite database into it once — the live file on the
   persistent disk (PERSIST_DIR/beverageops.db) if there is one, otherwise the bundled seed with sample
   transactions removed (unless KEEP_SAMPLE_DATA=true). Every copied field is verified
   (scripts/migrate_sqlite_to_postgres.py); the SQLite file is left untouched as a fallback.
3. If PostgreSQL already has data, do nothing.

Prints table counts only — never the connection string or row contents.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from sqlalchemy import func, select

    from src.database import Base, DATABASE_URL, engine
    import src.models  # noqa: F401  (registers the tables)
    if engine.dialect.name != 'postgresql':
        print('[pg] DATABASE_URL is not PostgreSQL; nothing to do')
        return 0
    Base.metadata.create_all(engine)
    with engine.connect() as db:
        rows = sum(db.scalar(select(func.count()).select_from(t)) or 0 for t in Base.metadata.sorted_tables)
    if rows:
        print(f'[pg] PostgreSQL already holds data ({rows} rows); no migration')
        return 0
    persist = os.environ.get('PERSIST_DIR')
    source = Path(persist) / 'beverageops.db' if persist else ROOT / 'data' / 'beverageops.db'
    work = Path(tempfile.mkdtemp(prefix='pg-bootstrap-'))
    if not source.is_file():
        seed = Path('/opt/seed_data/beverageops.db')
        if not seed.is_file():
            print('[pg] empty PostgreSQL and no SQLite to copy; starting empty')
            return 0
        source = work / 'seed.db'
        shutil.copy2(seed, source)
        if os.environ.get('KEEP_SAMPLE_DATA', 'false') != 'true':
            subprocess.run([sys.executable, str(ROOT / 'scripts' / 'clean_demo_transactions.py'), '--apply',
                            '--db', f'sqlite:///{source}', '--shift-file', str(work / 'unused.json')], check=True)
    report_dir = (Path(persist) if persist else ROOT / 'data') / 'migrations' / datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    report_dir.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'DATABASE_URL': DATABASE_URL}
    print(f'[pg] copying {source.name} into PostgreSQL (verified, one transaction)…', flush=True)
    done = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'migrate_sqlite_to_postgres.py'), '--apply',
                           '--source', str(source), '--output', str(report_dir)], env=env)
    shutil.rmtree(work, ignore_errors=True)
    return done.returncode


if __name__ == '__main__':
    sys.exit(main())
