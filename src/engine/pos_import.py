"""Import the POS "Thống kê số lượng sản phẩm" slips (one CSV per day in data/pos_daily) into sales_daily.

Each CSV is a line-by-line transcription of the slip: name, category, quantity, amount_vnd. On import:
  * every POS name is mapped to a menu SKU (POS_TO_SKU); products the menu did not have yet (matcha ice
    cream, Americano Cam/Chanh, honey teas, toppings, …) are created as new SKUs (NEW_SKUS);
  * rows that land on the same SKU (e.g. "Trà Sữa Trân Châu" and "Trà Sữa Trân Châu (MT)") are summed;
  * a complete day must reconcile with the slip footer in manifest.json (item count without toppings,
    revenue with toppings) or it is refused; an incomplete day is stored as verification_status='pending';
  * the day's rows for the store are replaced, so re-importing is safe. A file is only re-imported when its
    content changes (hash kept in app_settings), so sync() can run at every server start.

Run by hand:  python -m src.engine.pos_import [--check]
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
TOPPING = 'TOPPING'

POS_TO_SKU = {
    'Nước Chanh Tươi Lạnh': 'THQ1', 'Trà Xanh Chanh': 'THQ2', 'Trà Xanh Hoa Đào': 'THQ3',
    'Trà Đào Bigsize': 'THQ4', 'Trà Đào Dâu Tây': 'THQ5', 'Trà Cam Dâu Tây': 'THQ6',
    'Trà Cam Vàng 9999': 'THQ7', 'Chanh Leo Bách Hương': 'THQ9', 'Trà Xoài Chanh Leo': 'THQ10',
    'Trà Chanh Lô Hội': 'THQ11', 'Liên Minh Cam Xoài': 'THQ12',
    'Trà Sữa Trân Châu': 'TS1', 'Trà Sữa Trân Châu Đường Đen': 'TS2', 'Trà Sữa 2J': 'TS3',
    'Trà Sữa Thạch Dừa': 'TS4', 'Trà Sữa Thạch Đường Đen': 'TS5', 'Trà sữa O-coco': 'TS6',
    'Trà Sữa 2J (Size L)': 'TS8', 'Trà Sữa Thạch Dừa (Size L)': 'TS9',
    'Trà Sữa Thạch Đường Đen (Size L)': 'TS10', 'Trà Sữa Bá Vương': 'TS11',
    'Sữa Thạch Dâu Tây': 'ST1', 'Dương Chi Cam Lộ': 'ST3',
    'Cafe Latte Kem Tươi': 'CF1', 'Cafe Latte': 'CF2', 'Americano': 'CF3',
    'Kem Ốc Quế Nguyên Vị': 'DK1', '(ZLP) Kem Ốc Quế Nguyên Vị': 'DK1',
    'Super Sundae Dâu Tây': 'DK2', 'Super Sundae Đào Hồng': 'DK4', 'Super Sundae Đào Vàng': 'DK5',
    'Super Sundae O-coco': 'DK6', 'Lucky Sundae Dâu Tây': 'DK7', 'Lucky Sundae O-coco': 'DK8',
    'Super Sundae Trân Châu Đường Đen': 'DK9', 'Super Sundae Xoài': 'DK10',
}

# POS name → (sku_id, menu name, variant, list price). Price = what the slip shows for one plain item.
NEW_SKUS = {
    'Kem Ốc Quế Matcha': ('DK11', 'Kem ốc quế Matcha', None, 13000),
    'Kem Ốc Quế Matcha Mix': ('DK12', 'Kem ốc quế Matcha Mix', None, 13000),
    'Super Sundae O-Coco Matcha (Kem Matcha)': ('DK13', 'Super sundae Ococo Matcha (kem Matcha)', 'U', 25000),
    'Super Sundae O-coco Matcha (Kem Mix)': ('DK14', 'Super sundae Ococo Matcha (kem Mix)', 'U', 25000),
    'Sữa Tươi Matcha': ('TS12', 'Sữa tươi Matcha', 'M', 25000),
    'Trà Sữa Hoa Nhài': ('TS13', 'Trà sữa hoa nhài', 'M', 20000),
    'Trà Sữa Trân Châu (Size L)': ('TS14', 'Trà sữa trân châu size L', 'L', 30000),
    'Trà Việt Quất Triple Kill': ('THQ13', 'Trà Việt Quất Triple Kill', 'L', 26000),
    'Americano Cam': ('CF4', 'Americano cam', 'M', 28000),
    'Americano Chanh': ('CF5', 'Americano chanh', 'M', 28000),
    'Hồng Trà Mật Ong': ('TNC1', 'Hồng trà mật ong', 'M', 15000),
    'Trà Nhài Mật Ong': ('TNC2', 'Trà nhài mật ong', 'M', 15000),
    'Móc Chìa Khóa Tuyết Vương - Hổ Vàng': ('LN1', 'Móc chìa khóa Tuyết Vương - Hổ Vàng', None, 100000),
    'Trân châu': ('TP1', 'Topping trân châu', None, 3000),
    'Trân châu trắng': ('TP2', 'Topping trân châu trắng', None, 3000),
    'Thạch dừa': ('TP3', 'Topping thạch dừa', None, 3000),
    'Thạch đào': ('TP4', 'Topping thạch đào', None, 3000),
    'Lô hội': ('TP5', 'Topping lô hội', None, 3000),
    'Vụn ốc quế': ('TP6', 'Topping vụn ốc quế', None, 3000),
    'Vụn oreo': ('TP7', 'Topping vụn oreo', None, 3000),
    'Thạch đường đen': ('TP8', 'Topping thạch đường đen', None, 3000),
}


def folder() -> Path:
    return Path(os.environ.get('POS_DAILY_DIR') or ROOT / 'data' / 'pos_daily')


def manifest(path: Path | None = None) -> dict:
    f = (path or folder()) / 'manifest.json'
    return {k: v for k, v in json.loads(f.read_text(encoding='utf-8')).items() if not k.startswith('_')} if f.exists() else {}


def sku_for(name: str) -> str:
    name = name.strip()
    if name in POS_TO_SKU:
        return POS_TO_SKU[name]
    if name in NEW_SKUS:
        return NEW_SKUS[name][0]
    raise ValueError(f'Món POS chưa có mã: {name!r} — thêm vào POS_TO_SKU hoặc NEW_SKUS')


def read_day(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding='utf-8-sig', newline='') as fh:
        return [{'name': r['name'].strip(), 'category': r['category'].strip(),
                 'quantity': int(r['quantity']), 'amount_vnd': int(r['amount_vnd'])} for r in csv.DictReader(fh)]


def totals(rows: list[dict]) -> dict:
    """Footer figures as the POS prints them: items exclude toppings, revenue includes them; per category too."""
    by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        by_cat[r['category']][0] += r['quantity']
        by_cat[r['category']][1] += r['amount_vnd']
    return {'items': sum(v[0] for k, v in by_cat.items() if k != TOPPING),
            'revenue_vnd': sum(v[1] for v in by_cat.values()),
            'categories': {k: tuple(v) for k, v in by_cat.items()}}


def check_day(day: str, rows: list[dict], expected: dict | None) -> list[str]:
    """Problems with one day's transcription (empty list = OK)."""
    problems = []
    for r in rows:
        try:
            sku_for(r['name'])
        except ValueError as exc:
            problems.append(str(exc))
        if r['quantity'] <= 0 or r['amount_vnd'] < 0:
            problems.append(f"{r['name']}: số lượng/tiền không hợp lệ")
    if expected and expected.get('complete'):
        t = totals(rows)
        if t['items'] != expected['items']:
            problems.append(f"{day}: tổng số lượng {t['items']} ≠ phiếu POS {expected['items']}")
        if t['revenue_vnd'] != expected['revenue_vnd']:
            problems.append(f"{day}: tổng doanh thu {t['revenue_vnd']:,} ≠ phiếu POS {expected['revenue_vnd']:,}")
    return problems


def by_sku(rows: list[dict]) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        sku = sku_for(r['name'])
        out[sku][0] += r['quantity']
        out[sku][1] += r['amount_vnd']
    return {k: (v[0], v[1]) for k, v in out.items()}


def ensure_menu(db) -> list[str]:
    """Create the SKUs the POS sells that the menu does not have yet. Returns the ids created."""
    from src.models import MenuItem
    have = {s for (s,) in db.query(MenuItem.sku_id).all()}
    created = []
    for sku, name, variant, price in NEW_SKUS.values():
        if sku not in have:
            db.add(MenuItem(sku_id=sku, sku_name=name, variant=variant, selling_price_vnd=Decimal(price),
                            effective_from=date(2026, 11, 1), is_active=True))
            created.append(sku)
            have.add(sku)
    return created


def import_day(db, day: str, rows: list[dict], expected: dict | None, store_id: str) -> dict:
    from src.models import SalesDaily
    problems = check_day(day, rows, expected)
    if problems:
        raise ValueError('; '.join(problems))
    d = date.fromisoformat(day)
    complete = bool(expected and expected.get('complete'))
    db.query(SalesDaily).filter(SalesDaily.store_id == store_id, SalesDaily.business_date == d).delete()
    agg = by_sku(rows)
    for sku, (qty, amount) in sorted(agg.items()):
        db.add(SalesDaily(business_date=d, store_id=store_id, sku_id=sku, quantity_sold=qty,
                          revenue_vnd=Decimal(amount), source_id=f"POS_{d:%Y%m%d}",
                          verification_status='verified' if complete else 'pending'))
    t = totals(rows)
    return {'date': day, 'skus': len(agg), 'items': t['items'], 'revenue_vnd': t['revenue_vnd'], 'complete': complete}


def _digest(csv_path: Path, expected: dict | None) -> str:
    h = hashlib.sha256(csv_path.read_bytes())
    h.update(json.dumps(expected or {}, sort_keys=True).encode())
    h.update(json.dumps([POS_TO_SKU, NEW_SKUS], sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()[:16]


def sync(force: bool = False, path: Path | None = None) -> dict:
    """Import every changed day file. Safe to call at each start. Returns what was imported / skipped / failed."""
    from src.database import Base, SessionLocal, engine
    from src.models import AppSetting
    from src.runtime_settings import resolve_store_id

    base = path or folder()
    report = {'imported': [], 'unchanged': [], 'failed': {}, 'created_skus': []}
    files = sorted(base.glob('20??-??-??.csv')) if base.exists() else []
    if not files:
        return report
    Base.metadata.create_all(bind=engine)
    expected_all = manifest(base)
    db = SessionLocal()
    try:
        store_id = resolve_store_id(db)
        report['created_skus'] = ensure_menu(db)
        db.commit()
        for f in files:
            day = f.stem
            expected = expected_all.get(day)
            key = f'pos_import:{day}'
            digest = _digest(f, expected)
            seen = db.get(AppSetting, key)
            if seen and seen.value == digest and not force:
                report['unchanged'].append(day)
                continue
            try:
                report['imported'].append(import_day(db, day, read_day(f), expected, store_id))
                if seen:
                    seen.value = digest
                else:
                    db.add(AppSetting(key=key, value=digest, updated_by='pos_import'))
                db.commit()
            except Exception as exc:  # noqa: BLE001 - one bad day must not block the others
                db.rollback()
                report['failed'][day] = str(exc)
                logger.warning('POS import %s failed: %s', day, exc)
    finally:
        db.close()
    return report


_DONE = False


def sync_once() -> dict | None:
    """Called once per server process at start-up (POS_IMPORT_AUTO=0 turns it off)."""
    global _DONE
    if _DONE or str(os.environ.get('POS_IMPORT_AUTO', '1')).strip().lower() in {'0', 'false', 'off', 'no'}:
        return None
    _DONE = True
    try:
        report = sync()
        if report['imported'] or report['failed']:
            logger.info('POS import: %s', report)
        return report
    except Exception as exc:  # noqa: BLE001 - never stop the app from starting
        logger.warning('POS import skipped: %s', exc)
        return None


def main(argv: list[str]) -> int:
    base = folder()
    expected_all = manifest(base)
    bad = 0
    for f in sorted(base.glob('20??-??-??.csv')):
        rows = read_day(f)
        problems = check_day(f.stem, rows, expected_all.get(f.stem))
        t = totals(rows)
        state = 'đủ' if (expected_all.get(f.stem) or {}).get('complete') else 'THIẾU ẢNH'
        print(f"{f.stem}: {len(rows)} dòng, {t['items']} món, {t['revenue_vnd']:,}đ [{state}]"
              + (' — ' + '; '.join(problems) if problems else ' ✓'))
        bad += bool(problems)
    if '--check' not in argv and not bad:
        print(sync(force='--force' in argv))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
