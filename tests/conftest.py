"""Tests never call a paid or remote model implicitly through a developer .env."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def disable_live_models(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f"sqlite:///{(ROOT / 'data' / 'beverageops.db').as_posix()}")
    monkeypatch.setenv('POSTGRES_MCP_ENABLED', 'false')
    monkeypatch.setenv('STORE_ID', '')
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('APP_DEMO_MODE', 'true')
    monkeypatch.setenv('LLM_ENABLED', 'false')
    monkeypatch.setenv('WEATHER_ENABLED', 'false')
