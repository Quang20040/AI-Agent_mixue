"""Migration safety contracts on synthetic databases; no local .env or real data."""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select

spec = importlib.util.spec_from_file_location('migration', Path(__file__).resolve().parents[1] / 'scripts/migrate_sqlite_to_postgres.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


@pytest.fixture
def databases(tmp_path):
    metadata = MetaData()
    table = Table('items', metadata, Column('id', Integer, primary_key=True), Column('label', String(20), nullable=False))
    source, target = [create_engine('sqlite:///' + (tmp_path / name).as_posix()) for name in ('source.db', 'target.db')]
    for engine in (source, target):
        metadata.create_all(engine)
    yield metadata, table, source, target
    source.dispose()
    target.dispose()


def test_transfer_preserves_every_field(databases):
    metadata, table, source, target = databases
    with source.begin() as db:
        db.execute(table.insert(), [{'id': 7, 'label': 'Synthetic'}])
    assert migration.transfer(source, target, metadata)['items']['verified']
    with target.connect() as db:
        assert db.execute(select(table)).one() == (7, 'Synthetic')


def test_existing_target_data_is_never_overwritten(databases):
    metadata, table, source, target = databases
    with target.begin() as db:
        db.execute(table.insert(), [{'id': 99, 'label': 'Keep me'}])
    with pytest.raises(ValueError, match='TARGET_NOT_EMPTY'):
        migration.transfer(source, target, metadata)
    with target.connect() as db:
        assert db.execute(select(table)).one() == (99, 'Keep me')


def test_failed_insert_rolls_back_previous_rows(databases):
    metadata, table, source, target = databases
    with source.begin() as db:
        db.execute(table.insert(), [{'id': 1, 'label': 'First'}, {'id': 2, 'label': 'Second'}])
    with target.begin() as db:
        db.exec_driver_sql("CREATE TRIGGER reject_second BEFORE INSERT ON items WHEN NEW.id=2 BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
    with pytest.raises(Exception):
        migration.transfer(source, target, metadata)
    with target.connect() as db:
        assert db.execute(select(table)).all() == []
