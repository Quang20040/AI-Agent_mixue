"""POS daily slips (data/pos_daily) → sales_daily: every POS name maps to a SKU, complete days reconcile with the
slip footer, re-import is idempotent, an incomplete day is stored as 'pending', a wrong transcription is refused."""
import json
import shutil
from datetime import date

import pytest

from src.database import Base, SessionLocal, engine
from src.engine import pos_import
from src.models import AppSetting, MenuItem, SalesDaily

DAYS = ['2026-11-01', '2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06']


def _clean(days):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for d in days:
            db.query(SalesDaily).filter(SalesDaily.business_date == date.fromisoformat(d)).delete()
            db.query(AppSetting).filter(AppSetting.key == f'pos_import:{d}').delete()
        new_ids = [v[0] for v in pos_import.NEW_SKUS.values()]
        db.query(MenuItem).filter(MenuItem.sku_id.in_(new_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def pos_dir(tmp_path):
    for f in pos_import.folder().iterdir():
        shutil.copy(f, tmp_path / f.name)
    _clean(DAYS + ['2026-11-07'])
    yield tmp_path
    _clean(DAYS + ['2026-11-07'])


def test_shipped_transcriptions_reconcile_with_the_pos_footer():
    expected = pos_import.manifest()
    for f in sorted(pos_import.folder().glob('20??-??-??.csv')):
        rows = pos_import.read_day(f)
        assert pos_import.check_day(f.stem, rows, expected.get(f.stem)) == [], f.stem
    assert all(expected[d]['complete'] for d in DAYS)


def test_sync_imports_days_creates_new_skus_and_is_idempotent(pos_dir):
    report = pos_import.sync(path=pos_dir)
    assert not report['failed']
    assert {r['date'] for r in report['imported']} == set(DAYS) | {'2026-11-07'}
    db = SessionLocal()
    try:
        assert db.get(MenuItem, 'DK11').sku_name == 'Kem ốc quế Matcha'
        assert db.get(MenuItem, 'TP1') is not None
        d1 = date(2026, 11, 1)
        rows = db.query(SalesDaily).filter(SalesDaily.business_date == d1).all()
        assert sum(int(r.revenue_vnd) for r in rows) == 10_943_000
        assert sum(r.quantity_sold for r in rows if not r.sku_id.startswith('TP')) == 516
        # (ZLP) Kem Ốc Quế Nguyên Vị is the same cone as DK1, so the two lines are summed
        dk1 = next(r for r in rows if r.sku_id == 'DK1')
        assert (dk1.quantity_sold, int(dk1.revenue_vnd)) == (45, 450_000)
        assert {r.verification_status for r in rows} == {'verified'}
        partial = db.query(SalesDaily).filter(SalesDaily.business_date == date(2026, 11, 7)).all()
        assert partial and {r.verification_status for r in partial} == {'pending'}
        count = db.query(SalesDaily).filter(SalesDaily.business_date >= d1).count()
    finally:
        db.close()

    again = pos_import.sync(path=pos_dir)
    assert again['imported'] == [] and len(again['unchanged']) == 7
    forced = pos_import.sync(force=True, path=pos_dir)
    assert len(forced['imported']) == 7
    db = SessionLocal()
    try:
        assert db.query(SalesDaily).filter(SalesDaily.business_date >= d1).count() == count
    finally:
        db.close()


def test_a_wrong_transcription_is_refused_and_nothing_is_written(pos_dir):
    f = pos_dir / '2026-11-02.csv'
    f.write_text(f.read_text(encoding='utf-8').replace('Trà Chanh Lô Hội,TRÀ HOA QUẢ,25,524000',
                                                         'Trà Chanh Lô Hội,TRÀ HOA QUẢ,26,524000'), encoding='utf-8')
    report = pos_import.sync(path=pos_dir)
    assert '2026-11-02' in report['failed'] and '369' in report['failed']['2026-11-02']
    db = SessionLocal()
    try:
        assert db.query(SalesDaily).filter(SalesDaily.business_date == date(2026, 11, 2)).count() == 0
    finally:
        db.close()


def test_unknown_pos_name_is_reported():
    problems = pos_import.check_day('2026-11-09', [{'name': 'Món mới toanh', 'category': 'KEM',
                                                    'quantity': 1, 'amount_vnd': 10000}], None)
    assert problems and 'Món mới toanh' in problems[0]


def test_completing_day_7_reimports_it_as_verified(pos_dir):
    pos_import.sync(path=pos_dir)
    rows = pos_import.read_day(pos_dir / '2026-11-07.csv')
    t = pos_import.totals(rows)
    m = json.loads((pos_dir / 'manifest.json').read_text(encoding='utf-8'))
    m['2026-11-07'] = {'items': t['items'], 'revenue_vnd': t['revenue_vnd'], 'complete': True}
    (pos_dir / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
    report = pos_import.sync(path=pos_dir)
    assert [r['date'] for r in report['imported']] == ['2026-11-07']
    db = SessionLocal()
    try:
        rows = db.query(SalesDaily).filter(SalesDaily.business_date == date(2026, 11, 7)).all()
        assert {r.verification_status for r in rows} == {'verified'}
    finally:
        db.close()
