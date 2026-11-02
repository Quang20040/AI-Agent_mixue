"""Remove sample/demo transactions, keep master data.

Kept: users, menu_items, ingredients, recipe_bom (and login throttles).
Removed: sales_daily, purchases, stock_counts, topping_daily, daily_stock_movements, shift_reports,
operation_plans, and the shift report JSON file.

    python scripts/clean_demo_transactions.py                 # dry run: counts only
    python scripts/clean_demo_transactions.py --apply         # back up, then delete
    python scripts/clean_demo_transactions.py --apply --db sqlite:///path.db --shift-file path.json

A copy of the SQLite file and the JSON file is written next to them (*.bak-YYYYmmdd-HHMMSS) before deleting.
"""
import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
TRANSACTION_TABLES = ('sales_daily', 'purchases', 'stock_counts', 'topping_daily', 'daily_stock_movements',
                      'shift_reports', 'operation_plans')
MASTER_TABLES = ('users', 'menu_items', 'ingredients', 'recipe_bom')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', default=None, help='Database URL (default: DATABASE_URL or data/beverageops.db)')
    parser.add_argument('--shift-file', default=None, help='Shift report JSON (default: SHIFT_DATA_FILE or data/shift_reports.json)')
    parser.add_argument('--apply', action='store_true', help='Actually delete (otherwise only report counts)')
    args = parser.parse_args(argv)

    import os
    url = args.db or os.environ.get('DATABASE_URL') or f"sqlite:///{(ROOT / 'data' / 'beverageops.db').as_posix()}"
    shift_file = Path(args.shift_file or os.environ.get('SHIFT_DATA_FILE') or ROOT / 'data' / 'shift_reports.json')
    engine = create_engine(url)
    present = set(inspect(engine).get_table_names())
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')

    with engine.connect() as conn:
        counts = {t: conn.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar() for t in TRANSACTION_TABLES if t in present}
        kept = {t: conn.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar() for t in MASTER_TABLES if t in present}
    try:
        reports = json.loads(shift_file.read_text(encoding='utf-8')) if shift_file.exists() else []
    except ValueError:
        reports = []
    print('Sẽ xóa:' if args.apply else 'Chạy thử (thêm --apply để xóa thật):')
    for table, n in counts.items():
        print(f'  {table}: {n} dòng')
    print(f'  {shift_file.name}: {len(reports)} báo cáo ca')
    print('Giữ nguyên: ' + ', '.join(f'{t} ({n})' for t, n in kept.items()))
    if not args.apply:
        return 0

    if url.startswith('sqlite:///'):
        db_path = Path(url.removeprefix('sqlite:///'))
        if db_path.exists():
            shutil.copy2(db_path, db_path.with_name(f'{db_path.name}.bak-{stamp}'))
    if shift_file.exists():
        shutil.copy2(shift_file, shift_file.with_name(f'{shift_file.name}.bak-{stamp}'))
    with engine.begin() as conn:
        for table in counts:
            conn.execute(text(f'DELETE FROM {table}'))
    shift_file.parent.mkdir(parents=True, exist_ok=True)
    shift_file.write_text('[]', encoding='utf-8')
    print('Đã xóa giao dịch mẫu; dữ liệu nền vẫn giữ nguyên.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
