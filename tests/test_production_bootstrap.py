"""Production start-up: the owner account comes from the environment, never from demo passwords."""
import importlib.util
from pathlib import Path

from src.auth import check_password, hash_password, verify_user
from src.database import SessionLocal
from src.models import User

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'provision_admin.py'


def _provision(env):
    spec = importlib.util.spec_from_file_location('provision_admin', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.provision_from_env(env)


def test_owner_is_created_from_env_and_must_change_password():
    env = {'OWNER_USERNAME': 'chuquan_test', 'OWNER_INITIAL_PASSWORD': 'Mixue-2132-khoidau', 'OWNER_FULL_NAME': 'Chủ quán'}
    assert _provision(env) == 'PROVISIONED'
    with SessionLocal() as db:
        owner = db.get(User, 'chuquan_test')
        assert owner.role == 'ADMIN' and owner.must_change_password
        assert check_password('Mixue-2132-khoidau', owner.password_hash)
    # A second boot never resets a password the owner already chose.
    with SessionLocal() as db:
        db.get(User, 'chuquan_test').password_hash = hash_password('mat-khau-rieng-cua-chu')
        db.commit()
    assert _provision(env) == 'EXISTS'
    with SessionLocal() as db:
        assert check_password('mat-khau-rieng-cua-chu', db.get(User, 'chuquan_test').password_hash)


def test_demo_password_account_is_taken_over_but_weak_passwords_are_refused():
    assert _provision({'OWNER_USERNAME': 'quanly', 'OWNER_INITIAL_PASSWORD': '123'}) == 'WEAK_PASSWORD'
    assert _provision({'OWNER_USERNAME': 'Bad Name!', 'OWNER_INITIAL_PASSWORD': 'x' * 16}) == 'INVALID_USERNAME'
    assert _provision({}) == 'SKIPPED'
    # 'quanly' still has the published demo password, so the server owner may claim it.
    assert _provision({'OWNER_USERNAME': 'quanly', 'OWNER_INITIAL_PASSWORD': 'Quanly-2132-moi!'}) == 'PROVISIONED'
    with SessionLocal() as db:
        assert check_password('Quanly-2132-moi!', db.get(User, 'quanly').password_hash)


def test_demo_passwords_are_rejected_in_production(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('APP_DEMO_MODE', 'true')
    assert verify_user('nhanvien', '123') is None
