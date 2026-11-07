"""Remove the simulated history, keep everything real.

Simulated (generated to exercise forecasting before the shop had real records), dated before REAL_FROM:
* sales_daily 16/07–15/10 — except 14/10, whose figures come from the real POS slip;
* purchases, stock_counts, topping_daily;
* operation_plans created during development (drafts made while testing).

Kept: accounts, menu, ingredients, recipes (from the 19 document photos), stock slips (October entries come from
the shop's own stock sheet), approved shift closings, and every record from REAL_FROM on.
A full backup zip is written first (PERSIST_DIR/backups or data/backups); the delete is one transaction.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, and_, cast, delete, func, select

REAL_FROM = date.fromisoformat(os.environ.get('REAL_DATA_FROM') or '2026-11-01')
KEEP_DAYS = (date(2026, 10, 14),)   # real POS slip + ledger photographed that day
ROOT = Path(__file__).resolve().parents[2]
LABELS = {'sales_daily': 'Bán theo món (POS mô phỏng)', 'purchases': 'Nhập hàng mô phỏng',
          'stock_counts': 'Kiểm kê mô phỏng', 'topping_daily': 'Nấu / hủy topping mô phỏng',
          'operation_plans': 'Kế hoạch nháp lúc phát triển'}


def _conditions():
    from src.models import OperationPlan, Purchase, SalesDaily, StockCount, ToppingDaily
    return {
        'sales_daily': (SalesDaily, and_(SalesDaily.business_date < REAL_FROM, SalesDaily.business_date.notin_(KEEP_DAYS))),
        'purchases': (Purchase, cast(Purchase.order_date, Date) < REAL_FROM),
        'stock_counts': (StockCount, StockCount.business_date < REAL_FROM),
        'topping_daily': (ToppingDaily, ToppingDaily.business_date < REAL_FROM),
        'operation_plans': (OperationPlan, cast(OperationPlan.created_at, DateTime) < datetime.combine(REAL_FROM, datetime.min.time())),
    }


def preview(engine=None) -> dict[str, int]:
    from src.database import engine as default
    eng = engine or default
    out = {}
    with eng.connect() as db:
        for name, (model, cond) in _conditions().items():
            out[name] = int(db.scalar(select(func.count()).select_from(model).where(cond)) or 0)
    return out


def _backup_dir() -> Path:
    base = Path(os.environ['PERSIST_DIR']) if os.environ.get('PERSIST_DIR') else ROOT / 'data'
    return base / 'backups'


def apply(actor: str, engine=None, backup: bool = True) -> dict[str, Any]:
    """Back up, then delete the simulated rows in one transaction. Returns counts and the backup path."""
    from src.database import engine as default
    eng = engine or default
    saved = None
    if backup:
        from src.engine.data_export import build_export
        tmp = build_export()
        target = _backup_dir() / f'before-purge-{datetime.now():%Y%m%d_%H%M%S}.zip'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp), target)
        saved = str(target)
    deleted = {}
    with eng.begin() as db:
        for name, (model, cond) in _conditions().items():
            deleted[name] = db.execute(delete(model).where(cond)).rowcount or 0
    record = {'at': datetime.now(timezone.utc).isoformat(), 'action': 'purge_sample_data', 'by': actor,
              'real_from': REAL_FROM.isoformat(), 'deleted': deleted, 'backup': saved}
    try:
        from src.agent.config import AgentSettings
        path = Path(AgentSettings.from_env().audit_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as audit:
            audit.write(json.dumps(record, ensure_ascii=False) + '\n')
    except OSError:
        pass
    return record
