"""Copy a verified SQLite snapshot to an empty PostgreSQL database; never overwrite.

Stop application writers first. Back up PostgreSQL separately before applying.
Secrets and row contents are never printed or included in the verification report.
"""

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

from sqlalchemy import Integer, create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def canonical(value):
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, Decimal):
        return format(value.normalize(), 'f')
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def fingerprint(rows):
    encoded = sorted(json.dumps(canonical(dict(row)), sort_keys=True, ensure_ascii=True, allow_nan=False) for row in rows)
    digest = hashlib.sha256()
    for row in encoded:
        digest.update(row.encode('utf-8') + b'\n')
    return digest.hexdigest()


def transfer(source, target, metadata):
    """One target transaction, preflight every table, compare every copied field."""
    source_names = set(inspect(source).get_table_names()) - {'sqlite_sequence'}
    unknown = source_names - set(metadata.tables)
    if unknown:
        raise ValueError('UNSUPPORTED_SOURCE_TABLES: ' + ', '.join(sorted(unknown)))
    report = {}
    with source.connect() as origin, target.begin() as destination:
        if target.dialect.name == 'postgresql':
            destination.exec_driver_sql("SET LOCAL lock_timeout = '5000ms'")
            destination.exec_driver_sql("SET LOCAL statement_timeout = '120000ms'")
            # Acquire all locks before checking emptiness, so a concurrent writer
            # cannot change a different table after its preflight check.
            quoted = ', '.join(target.dialect.identifier_preparer.quote(table.name) for table in metadata.sorted_tables)
            destination.exec_driver_sql('LOCK TABLE ' + quoted + ' IN ACCESS EXCLUSIVE MODE')
        for table in metadata.sorted_tables:
            if destination.scalar(select(func.count()).select_from(table)):
                raise ValueError('TARGET_NOT_EMPTY: ' + table.name)
        for table in metadata.sorted_tables:
            if table.name not in source_names:
                continue
            actual_columns = {column['name'] for column in inspect(source).get_columns(table.name)}
            if actual_columns != set(table.columns.keys()):
                raise ValueError('SOURCE_SCHEMA_MISMATCH: ' + table.name)
            rows = [dict(row) for row in origin.execute(select(table)).mappings()]
            for offset in range(0, len(rows), 500):
                destination.execute(table.insert(), rows[offset:offset + 500])
            copied = [dict(row) for row in destination.execute(select(table)).mappings()]
            expected_digest = fingerprint(rows)
            if len(rows) != len(copied) or expected_digest != fingerprint(copied):
                raise ValueError('VERIFICATION_MISMATCH: ' + table.name)
            report[table.name] = {'source_count': len(rows), 'target_count': len(copied), 'sha256': expected_digest, 'verified': True}
        if target.dialect.name == 'postgresql':
            for table in metadata.sorted_tables:
                keys = list(table.primary_key.columns)
                if len(keys) == 1 and isinstance(keys[0].type, Integer) and keys[0].autoincrement is not False:
                    sequence = destination.scalar(text('SELECT pg_get_serial_sequence(:table, :column)'),
                                                  {'table': table.name, 'column': keys[0].name})
                    if sequence:
                        maximum = destination.scalar(select(func.max(keys[0])))
                        destination.execute(text('SELECT setval(CAST(:sequence AS regclass), :value, :called)'),
                                            {'sequence': sequence, 'value': max(1, maximum or 1), 'called': maximum is not None})
        sales = metadata.tables.get('sales_daily')
        if sales is not None and sales.name in source_names:
            totals = select(func.sum(sales.c.quantity_sold), func.sum(sales.c.revenue_vnd))
            before, after = origin.execute(totals).one(), destination.execute(totals).one()
            if canonical(tuple(before)) != canonical(tuple(after)):
                raise ValueError('SALES_TOTALS_MISMATCH')
            report['sales_totals'] = {'quantity': canonical(after[0]), 'revenue_vnd': canonical(after[1]), 'verified': True}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=str(ROOT / 'data' / 'beverageops.db'))
    parser.add_argument('--apply', action='store_true', help='Require stopped writers and an existing full backup')
    parser.add_argument('--output', required=True, help='New directory for SQLite snapshot and credential-free report')
    args = parser.parse_args()
    if not args.apply:
        parser.error('Use --apply only after backup and stopping application writers.')
    from src.runtime_settings import setting
    dsn = setting('DATABASE_URL')
    if not dsn or make_url(dsn).get_backend_name() != 'postgresql':
        raise ValueError('POSTGRESQL_TARGET_REQUIRED')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / 'source.sqlite'
    with sqlite3.connect(Path(args.source).resolve().as_uri() + '?mode=ro', uri=True) as source:
        with sqlite3.connect(snapshot) as backup:
            source.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or backup.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('SQLITE_INTEGRITY_FAILED')
    # Import schema without connecting to or changing the live source DB.
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    from src.database import Base
    import src.models  # noqa: F401
    source_engine = create_engine('sqlite:///' + snapshot.as_posix())
    target_engine = create_engine(dsn, connect_args={'connect_timeout': 5})
    try:
        report = transfer(source_engine, target_engine, Base.metadata)
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        (output / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding='utf-8')
        print('Migration committed; all copied fields verified.')
        for name, result in report.items():
            if isinstance(result, dict) and 'source_count' in result:
                print(f"{name}: {result['source_count']} -> {result['target_count']} OK")
        print('Report: ' + str(output / 'verification.json'))
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # SQLAlchemy driver errors can contain DSNs, statements and private rows.
        safe = str(error) if isinstance(error, ValueError) else type(error).__name__
        print('Migration stopped; application configuration unchanged. Reason: ' + safe)
        raise SystemExit(1)
