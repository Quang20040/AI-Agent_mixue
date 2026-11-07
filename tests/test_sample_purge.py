import shutil
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, func, select, text


def _copy(tmp_path):
    import os
    src = Path(os.environ['DATABASE_URL'].removeprefix('sqlite:///'))
    dst = tmp_path / 'b.db'
    shutil.copy2(src, dst)
    return create_engine(f'sqlite:///{dst}')


def test_simulated_history_goes_real_records_stay(tmp_path):
    from src.engine import sample_purge
    from src.models import DailyStockMovement, MenuItem, RecipeBOM, SalesDaily
    engine = _copy(tmp_path)
    with engine.connect() as db:
        before_moves = db.scalar(select(func.count()).select_from(DailyStockMovement))
        kept_day = db.scalar(select(func.count()).select_from(SalesDaily).where(SalesDaily.business_date == date(2026, 10, 14)))
    counts = sample_purge.preview(engine)
    assert counts['sales_daily'] > 3000 and counts['purchases'] > 0
    result = sample_purge.apply('quanly', engine=engine, backup=False)
    assert result['deleted'] == counts
    assert sum(sample_purge.preview(engine).values()) == 0
    with engine.connect() as db:
        assert db.scalar(select(func.count()).select_from(SalesDaily)) == kept_day > 0      # 14/10 (real POS) kept
        assert db.scalar(select(func.count()).select_from(DailyStockMovement)) == before_moves
        assert db.scalar(select(func.count()).select_from(MenuItem)) == 39
        assert db.scalar(select(func.count()).select_from(RecipeBOM)) == 120
        assert db.execute(text('select count(*) from users')).scalar() >= 4


def test_purge_endpoint_previews_unless_confirmed():
    import pytest
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from src import login_sessions
    from src.api.main import app
    client = TestClient(app)
    staff = {'Authorization': f'Bearer {login_sessions.create("nhanvien")}'}
    manager = {"Authorization": f"Bearer {login_sessions.create('chucuahang')}"}  # quanly may be mid password reset in other tests
    assert client.post('/api/v1/stores/2132/sample-data/purge', json={'confirm': True}, headers=staff).status_code == 403
    res = client.post('/api/v1/stores/2132/sample-data/purge', json={'confirm': False}, headers=manager)
    assert res.status_code == 200, (res.status_code, res.text[:300])
    assert 'sales_daily' in res.json()['preview']      # a preview deletes nothing
