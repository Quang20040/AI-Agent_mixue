import zipfile

from src.engine.data_export import build_export, verify


def test_export_contains_the_database_and_shift_reports_and_verifies():
    path = build_export()
    try:
        names = zipfile.ZipFile(path).namelist()
        assert 'beverageops.db' in names and 'shift_reports.json' in names and 'manifest.json' in names
        assert verify(path) == []
    finally:
        path.unlink()
