"""Test isolation.

* Tests never call a paid or remote model implicitly through a developer .env.
* Tests never modify the tracked store data: the SQLite database, shift_reports.json and
  the agent's private stores are copied to a per-session temporary directory, and the
  application is pointed at the copies before any ``src`` module is imported.
"""
import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_SANDBOX = Path(tempfile.mkdtemp(prefix='beverageops-tests-'))
atexit.register(shutil.rmtree, _SANDBOX, ignore_errors=True)
for name in ('beverageops.db', 'shift_reports.json'):
    if (ROOT / 'data' / name).is_file():
        shutil.copy2(ROOT / 'data' / name, _SANDBOX / name)
(_SANDBOX / 'agent_private').mkdir()

TEST_DATABASE_URL = f"sqlite:///{(_SANDBOX / 'beverageops.db').as_posix()}"
_PATHS = {
    'DATABASE_URL': TEST_DATABASE_URL,
    'SHIFT_DATA_FILE': str(_SANDBOX / 'shift_reports.json'),
    'OCR_EDITS_LOG_FILE': str(_SANDBOX / 'agent_private' / 'ocr_user_edits.jsonl'),
    'AGENT_CHECKPOINT_PATH': str(_SANDBOX / 'agent_private' / 'checkpoints.sqlite'),
    'AGENT_AUDIT_PATH': str(_SANDBOX / 'agent_private' / 'audit.jsonl'),
    'CHAT_ATTACHMENTS_DIR': str(_SANDBOX / 'chat_attachments'),
}
# Module-level so the paths are in place before test modules import src.database & co.
os.environ.update(_PATHS)


@pytest.fixture(autouse=True)
def disable_live_models(monkeypatch):
    for name, value in _PATHS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv('POSTGRES_MCP_ENABLED', 'false')
    monkeypatch.setenv('STORE_ID', '')
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('APP_DEMO_MODE', 'true')
    monkeypatch.setenv('LLM_ENABLED', 'false')
    monkeypatch.setenv('WEATHER_ENABLED', 'false')


@pytest.fixture(autouse=True)
def independent_stock_requests():
    """The double-click guard rejects identical stock requests made within a few seconds.
    Age rows left by earlier tests (temporary DB only) so tests do not depend on runner speed."""
    from datetime import datetime, timedelta

    from src.database import SessionLocal
    from src.models import DailyStockMovement

    with SessionLocal() as db:
        db.query(DailyStockMovement).filter(
            DailyStockMovement.created_at >= datetime.now() - timedelta(hours=1)
        ).update({DailyStockMovement.created_at: datetime.now() - timedelta(hours=1)}, synchronize_session=False)
        db.commit()
    yield
