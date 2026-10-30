"""Independent regression contracts for the audited money/stock/auth/RAG defects.

All writes use per-test SQLite/JSON fixtures. Never use production transaction rows.
"""

import json
import os
from datetime import date, datetime
import subprocess
import sys

import pandas as pd
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src import auth
from src.database import Base
from src.models import DailyStockMovement, Ingredient, MenuItem, RecipeBOM, SalesDaily, User
from src.engine import daily_stock_service as stock
from src.engine import shift_service as shift
from src.engine.bom_engine import BOMEngine
from src.engine.optimizer import OptimizerEngine


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DEMO_MODE", "false")
    monkeypatch.setenv("STORE_ID", "")
    engine = create_engine("sqlite:///" + (tmp_path / "ops.db").as_posix(), connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    monkeypatch.setattr(auth, "SessionLocal", session)
    monkeypatch.setattr(stock, "SessionLocal", session)
    monkeypatch.setattr(stock, "engine", engine)
    import src.database

    monkeypatch.setattr(src.database, "SessionLocal", session)
    monkeypatch.setattr(shift, "SHIFT_DATA_FILE", tmp_path / "shifts.json")
    shift.SHIFT_DATA_FILE.write_text("[]", encoding="utf-8")
    with session() as db:
        db.add_all(
            [
                User(
                    username="audit_admin",
                    password_hash=auth.hash_password("audit-admin-password"),
                    full_name="Synthetic Admin",
                    role="ADMIN",
                    is_active=True,
                ),
                User(
                    username="audit_staff",
                    password_hash=auth.hash_password("audit-staff-password"),
                    full_name="Synthetic Staff",
                    role="STAFF_OFFICIAL",
                    is_active=True,
                ),
                User(
                    username="audit_disabled",
                    password_hash=auth.hash_password("audit-admin-password"),
                    full_name="Synthetic Disabled",
                    role="ADMIN",
                    is_active=False,
                ),
                Ingredient(ingredient_id="1", ingredient_name="Synthetic Ingredient", base_unit="g", ingredient_group="dry"),
                MenuItem(sku_id="SKU", sku_name="Synthetic Drink", selling_price_vnd=10000, effective_from=date(2026, 1, 1)),
            ]
        )
        db.commit()
    yield session
    engine.dispose()


def save(payload, **kwargs):
    return shift.save_or_update_shift_report(payload, actor_username="audit_admin", **kwargs)


def report(**kwargs):
    return {
        "business_date": "2026-10-02",
        "shift_code": "CA_SANG",
        "cash_vnd": 100,
        "bank_transfer_vnd": 200,
        "status": "APPROVED",
        **kwargs,
    }


def test_shift_partial_update_uses_merged_values(store):
    ok, _, original = save(report(id="R1"))
    assert ok
    ok, _, updated = save({"id": "R1", "cash_vnd": 150})
    assert ok and updated["bank_transfer_vnd"] == 200 and updated["total_collected_vnd"] == 350
    assert original["total_collected_vnd"] == 300


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, 0.5, 500_000_001])
def test_shift_rejects_invalid_money(store, value):
    ok, _, _ = save(report(cash_vnd=value))
    assert not ok
    assert shift.get_all_shift_reports() == []


@pytest.mark.parametrize(
    "payload", [{}, {"business_date": "bad", "shift_code": "CA_SANG"}, {"business_date": "2026-10-02", "shift_code": "INVALID"}]
)
def test_shift_requires_valid_identity(store, payload):
    assert not shift.validate_shift_report_payload(payload)[0]


def test_shift_approval_requires_role_and_account(store):
    assert not shift.validate_shift_report_payload(report(), require_admin_for_approval=True)[0]
    assert not shift.save_or_update_shift_report(report(), actor_role="ADMIN")[0]
    assert not shift.save_or_update_shift_report(report(), actor_username="audit_staff", actor_role="ADMIN")[0]
    assert not shift.save_or_update_shift_report(report(), actor_username="audit_disabled")[0]


def test_shift_corruption_does_not_become_approved_seed(store):
    shift.SHIFT_DATA_FILE.write_text("{BROKEN", encoding="utf-8")
    with pytest.raises(shift.ShiftStorageError):
        shift.get_all_shift_reports()
    assert shift.SHIFT_DATA_FILE.read_text() == "{BROKEN"


def test_missing_shift_file_has_no_demo_rows(store):
    shift.SHIFT_DATA_FILE.unlink()
    assert shift.get_all_shift_reports() == []


@pytest.mark.parametrize("scope,expected", [("daily_cumulative", 200), ("per_shift", 400)])
def test_cashless_evening_has_explicit_scope(store, scope, expected):
    for code, cash, bank in [("CA_SANG", 100, 0), ("CA_CHIEU", 100, 0), ("CA_TOI", 0, 200)]:
        assert save(
            report(shift_code=code, cash_vnd=cash, bank_transfer_vnd=bank, report_scope=scope if code == "CA_TOI" else "per_shift")
        )[0]
    assert shift.get_daily_closing_summary("2026-10-02")["total_collected_vnd"] == expected


def test_stock_actor_and_entity_validation(store):
    def create(user, role, ingredient="1"):
        return stock.create_stock_request(date(2026, 10, 2), ingredient, "IN", 1, user, role)

    assert create("audit_staff", "ADMIN")["status"] == "FORBIDDEN"
    assert create("audit_disabled", "ADMIN")["status"] == "FORBIDDEN"
    assert create("missing", "ADMIN")["status"] == "FORBIDDEN"
    assert create("audit_admin", "ADMIN", "UNKNOWN")["status"] == "ERROR"
    assert create("audit_staff", "STAFF_OFFICIAL")["is_approved"] is False


@pytest.mark.parametrize(
    "kind,qty,expected",
    [
        ("ACTUAL_COUNT", 0, "SUCCESS"),
        ("IN", 0, "ERROR"),
        ("OUT", 0, "ERROR"),
        ("OUT", -1, "ERROR"),
        ("IN", float("nan"), "ERROR"),
        ("ACTUAL_COUNT", float("inf"), "ERROR"),
    ],
)
def test_stock_quantity_boundaries(store, kind, qty, expected):
    assert stock.create_stock_request(date(2026, 10, 2), "1", kind, qty, "audit_admin", "ADMIN")["status"] == expected


def test_stock_pending_transitions_and_authorization(store):
    result = stock.create_stock_request(date(2026, 10, 2), "1", "OUT", 2, "audit_staff", "STAFF_OFFICIAL")
    ident = result["request_id"]
    assert not stock.approve_stock_request(ident, "audit_staff")[0]
    assert stock.approve_stock_request(ident, "audit_admin")[0]
    assert not stock.reject_stock_request(ident, "audit_admin")[0]
    assert not stock.approve_stock_request(ident, "audit_admin")[0]
    assert not stock.delete_stock_movement(ident, "audit_staff")[0]
    assert not stock.update_stock_movement(ident, 3, "audit_staff")[0]
    assert not stock.update_stock_cell_manually("1", "T5 1/10", 3, "audit_staff")[0]


def test_stock_duplicate_does_not_write_twice(store):
    args = (date(2026, 10, 2), "1", "IN", 2, "audit_admin", "ADMIN")
    assert stock.create_stock_request(*args)["status"] == "SUCCESS"
    assert stock.create_stock_request(*args)["status"] == "DUPLICATE"
    with store() as db:
        assert db.query(DailyStockMovement).count() == 1


def test_monthly_ledger_opening_period_zero_count_and_batch_queries(store):
    with store() as db:
        for d, kind, qty in [
            (date(2026, 9, 30), "INITIAL", 100),
            (date(2026, 10, 2), "IN", 7),
            (date(2026, 10, 3), "OUT", 2),
            (date(2026, 11, 2), "IN", 11),
            (date(2026, 11, 4), "ACTUAL_COUNT", 0),
        ]:
            db.add(
                DailyStockMovement(
                    business_date=d, ingredient_id="1", movement_type=kind, quantity=qty, status="APPROVED", recorded_by="audit_admin"
                )
            )
        db.commit()
    queries = []

    def count(*args):
        queries.append(1)

    event.listen(stock.engine, "before_cursor_execute", count)
    try:
        frame = stock.get_stock_matrix_df(2026, 11)
    finally:
        event.remove(stock.engine, "before_cursor_execute", count)
    row = frame.iloc[0]
    assert row["Tổng nhập"] == 11 and row["Tổng xuất"] == 0
    assert row["Tồn cuối 10/2026"] == 105 and row["Tồn sổ sách"] == 116
    assert row["Tồn thực tế"] == 0 and row["Chênh lệch"] == -116
    assert "T5 1/10" not in frame.columns and len(queries) <= 4
    feb = stock.get_stock_matrix_df(2027, 2)
    assert "Tồn cuối 1/2027" in feb and not any("/2" in c and "29/" in c for c in feb)


def test_new_catalog_item_and_missing_opening_are_not_fabricated(store):
    frame = stock.get_stock_matrix_df(2026, 11)
    assert list(frame["Mã NL"]) == ["1"]
    assert frame.iloc[0]["Tồn sổ sách"] == "—"


def versions(store):
    with store() as db:
        db.add_all(
            [
                RecipeBOM(
                    recipe_id="old",
                    sku_id="SKU",
                    ingredient_id="1",
                    quantity_per_item=10,
                    unit="g",
                    effective_from=date(2026, 1, 1),
                    effective_to=date(2026, 6, 30),
                ),
                RecipeBOM(
                    recipe_id="new", sku_id="SKU", ingredient_id="1", quantity_per_item=20, unit="g", effective_from=date(2026, 7, 1)
                ),
                SalesDaily(business_date=date(2026, 10, 2), store_id="2132", sku_id="SKU", quantity_sold=10, revenue_vnd=100000),
            ]
        )
        db.commit()


def test_consumption_and_optimizer_use_effective_recipe(store):
    versions(store)
    with store() as db:
        assert BOMEngine(db).calculate_theoretical_consumption().theoretical_usage.sum() == 200
        demand = OptimizerEngine(db).calculate_ingredient_demand(
            pd.DataFrame([{"sku_id": "SKU", "predicted_qty": 10, "target_date": date(2026, 10, 2)}])
        )
        assert demand.theoretical_qty.sum() == 200
        multi = OptimizerEngine(db).calculate_ingredient_demand(
            pd.DataFrame(
                [
                    {"sku_id": "SKU", "predicted_qty": 10, "target_date": date(2026, 6, 30)},
                    {"sku_id": "SKU", "predicted_qty": 10, "target_date": date(2026, 7, 1)},
                ]
            )
        )
        assert multi.theoretical_qty.sum() == 300


def test_store_isolation_and_configuration(store, monkeypatch):
    versions(store)
    with store() as db:
        db.add(SalesDaily(business_date=date(2026, 10, 2), store_id="OTHER", sku_id="SKU", quantity_sold=90, revenue_vnd=900000))
        db.commit()
        assert BOMEngine(db, store_id="2132").get_sales_summary().quantity_sold.sum() == 10
        with pytest.raises(ValueError, match="STORE_ID"):
            BOMEngine(db).get_sales_summary()
        monkeypatch.setenv("STORE_ID", "WRONG")
        with pytest.raises(ValueError, match="STORE_ID"):
            BOMEngine(db).get_sales_summary()


def test_forecast_infers_single_store_when_unconfigured(store):
    versions(store)
    from src.engine.forecasting import ForecastingEngine

    with store() as db:
        forecast = ForecastingEngine(db)
        assert forecast.store_id == "2132" and len(forecast.df) == 1


def test_auth_role_throttle_and_password_policy(store):
    assert auth.get_allowed_pages("UNKNOWN") == []
    assert auth.verify_user("audit_disabled", "audit-admin-password") is None
    for _ in range(8):
        assert auth.verify_user("audit_admin", "bad") is None
    assert auth.verify_user("audit_admin", "audit-admin-password") is None
    from src.models import LoginThrottle
    from datetime import timedelta, timezone

    with store() as db:
        throttle = db.get(LoginThrottle, "audit_admin")
        throttle.blocked_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
    assert auth.verify_user("audit_admin", "audit-admin-password")["role"] == "ADMIN"
    assert not auth.change_user_password("audit_admin", "audit-admin-password", "654321")[0]
    assert auth.change_user_password("audit_admin", "audit-admin-password", "a-new-long-password")[0]


def test_default_admin_and_quick_demo_mode_are_disabled(tmp_path, monkeypatch):
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + (tmp_path / "empty.db").as_posix(),
        "APP_ENV": "production",
        "APP_DEMO_MODE": "true",
    }
    result = subprocess.run(
        [sys.executable, "-c", "from src.auth import verify_user; print(verify_user('quanly','123') is None)"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0 and result.stdout.strip() == "True"


def test_postgres_url_never_silently_becomes_sqlite(tmp_path):
    env = {**os.environ, "DATABASE_URL": "postgresql://synthetic:synthetic@localhost:5432/test"}
    env.pop("POSTGRES_ACTIVE", None)
    # Assert engine selection independently from driver/server availability. The
    # container integration test remains separate and must use a real driver.
    code = "from unittest.mock import patch; p=patch('sqlalchemy.create_engine'); create=p.start(); import src.database; print(create.call_args.args[0].get_backend_name()); p.stop()"
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0 and result.stdout.strip() == "postgresql"


def test_rag_unknown_entity_and_explicit_entity_gate(tmp_path):
    from src.agent.multi_agent.repo_docs_agent import RepoDocsAgent

    documents = tmp_path / "DU_LIEU_CAN_NHAP"
    documents.mkdir()
    (documents / "10_Quy_dinh_bao_quan_theo_anh.csv").write_text(
        "Mã nguyên liệu,Điều kiện theo ảnh,Hạn dùng nguyên văn\nTP02,Đậy kín,4 giờ\nTP03,Giữ lạnh,8 giờ\n", encoding="utf-8"
    )
    agent = RepoDocsAgent(tmp_path)
    assert agent.search("TP99 bảo quản được bao lâu", category_filter="SOP_QUY_CHUAN") == []
    hits = agent.search("TP02 bảo quản", category_filter="SOP_QUY_CHUAN")
    assert hits and all(hit["metadata"].get("code") == "TP02" for hit in hits)


def test_manual_cell_replaces_approved_aggregate_without_approving_pending(store):
    from src.engine.stock_matrix import day_label

    day = date(2026, 11, 2)
    with store() as db:
        for quantity, status in [(2, "APPROVED"), (3, "APPROVED"), (99, "PENDING")]:
            db.add(
                DailyStockMovement(
                    business_date=day, ingredient_id="1", movement_type="OUT", quantity=quantity, status=status, recorded_by="audit_staff"
                )
            )
        db.commit()
    column = day_label(day)
    assert stock.update_stock_cell_manually("1", column, 7, "audit_admin", year=2026, month=11)[0]
    assert stock.get_cell_value("1", column, year=2026, month=11) == 7
    with store() as db:
        pending = db.query(DailyStockMovement).filter_by(status="PENDING").one()
        assert pending.quantity == 99
    assert stock.update_stock_cell_manually("1", column, None, "audit_admin", year=2026, month=11)[0]
    with store() as db:
        assert db.query(DailyStockMovement).one().status == "PENDING"


def test_backup_restore_covers_sqlite_json_checkpoint_and_media(tmp_path):
    import sqlite3
    from src.engine.backup_bundle import BackupBundle

    root = tmp_path / "bundle-app"
    data = root / "data"
    (data / "agent_private/chat_uploads").mkdir(parents=True)
    for relative in ["beverageops.db", "agent_private/conversations.sqlite", "agent_private/checkpoints.sqlite"]:
        with sqlite3.connect(data / relative) as db:
            db.execute("CREATE TABLE probe (value INTEGER)")
            db.execute("INSERT INTO probe VALUES (1)")
    (data / "shift_reports.json").write_text('[{"cash_vnd":100}]')
    (data / "agent_private/chat_uploads/image.bin").write_bytes(b"SYNTHETIC_IMAGE")
    bundle = BackupBundle(root)
    assert not bundle.create()[0]
    ok, stamp = bundle.create(maintenance=True)
    assert ok and stamp in bundle.list()
    with sqlite3.connect(data / "beverageops.db") as db:
        db.execute("UPDATE probe SET value=2")
    (data / "shift_reports.json").write_text("{BROKEN")
    (data / "agent_private/chat_uploads/image.bin").write_bytes(b"CHANGED")
    assert bundle.restore(stamp, maintenance=True)[0]
    for relative in ["beverageops.db", "agent_private/conversations.sqlite", "agent_private/checkpoints.sqlite"]:
        with sqlite3.connect(data / relative) as db:
            assert db.execute("SELECT value FROM probe").fetchone()[0] == 1
    assert json.loads((data / "shift_reports.json").read_text())[0]["cash_vnd"] == 100
    assert (data / "agent_private/chat_uploads/image.bin").read_bytes() == b"SYNTHETIC_IMAGE"
    assert list((root / "backups").glob("safety_*"))


def test_backup_rejects_tampering_before_overwrite(tmp_path):
    from src.engine.backup_bundle import BackupBundle

    data = tmp_path / "data"
    data.mkdir()
    (data / "shift_reports.json").write_text("[]")
    bundle = BackupBundle(tmp_path)
    ok, stamp = bundle.create(maintenance=True)
    assert ok
    (data / "shift_reports.json").write_text('[{"marker":"LIVE"}]')
    (tmp_path / "backups" / stamp / "data/shift_reports.json").write_text("TAMPERED")
    assert not bundle.restore(stamp, maintenance=True)[0]
    assert "LIVE" in (data / "shift_reports.json").read_text()


def test_shift_multi_process_updates_do_not_overwrite_each_other(store):
    db_url = str(store.kw["bind"].url)
    code = """
import sys
from pathlib import Path
from src.engine import shift_service as s
s.SHIFT_DATA_FILE=Path(sys.argv[1])
ok, _, _ = s.save_or_update_shift_report({'business_date':sys.argv[2], 'shift_code':'CA_SANG', 'cash_vnd':100}, actor_username='audit_admin')
raise SystemExit(0 if ok else 1)
"""
    env = {**os.environ, "DATABASE_URL": db_url, "APP_ENV": "production", "APP_DEMO_MODE": "false"}
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(shift.SHIFT_DATA_FILE), f"2026-10-{day}"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for day in range(10, 14)
    ]
    for process in processes:
        stdout, stderr = process.communicate(timeout=40)
        assert process.returncode == 0, stdout + stderr
    assert len(shift.get_all_shift_reports()) == 4


def test_ocr_confirmation_contract_persists_once_without_real_photos(store, tmp_path, monkeypatch):
    from src.agent.mixue_agent import MixueOperationsAgent
    from src.agent.config import AgentSettings
    from src.agent.conversation_store import ConversationStore
    from src.agent.graph_tools import OcrDraftConfirmArguments
    from src.engine.vision_ocr import MONEY_FIELDS

    monkeypatch.setattr(shift, "OCR_EDITS_LOG_FILE", tmp_path / "ocr-audit.jsonl")
    memory = ConversationStore(tmp_path / "chat.sqlite")
    with store() as db:
        agent = MixueOperationsAgent(
            db_session=db,
            conversation_store=memory,
            settings=AgentSettings(checkpoint_path=str(tmp_path / "checkpoints.sqlite"), audit_path=str(tmp_path / "audit.jsonl")),
        )
        actor = agent._actor("ADMIN", "Synthetic Admin", "audit_admin")
        owner = agent._conversation_owner(actor)
        fields = {key: 0 for key in MONEY_FIELDS}
        fields.update(cash_vnd=100, bank_transfer_vnd=200, total_collected_vnd=300, report_date="2026-10-02", shift_code="CA_SANG")
        draft = memory.save_ocr_draft(
            owner,
            agent.current_conversation_id,
            user_id=actor.user_id,
            store_id=actor.store_id,
            draft_data={"fields": fields, "document_type": "handwritten_ledger"},
        )
        assert OcrDraftConfirmArguments(draft_id=draft["draft_id"])
        result = agent.confirm_ocr_draft(True, "ADMIN", "Synthetic Admin", user_id="audit_admin", draft_id=draft["draft_id"])
        assert result["status"] == "SUCCESS" and result["draft"]["status"] == "CONFIRMED"
        assert len(shift.get_all_shift_reports()) == 1
        second = agent.confirm_ocr_draft(True, "ADMIN", "Synthetic Admin", user_id="audit_admin", draft_id=draft["draft_id"])
        assert second["status"] == "NO_ACTIVE_DRAFT"
        agent.close()


def test_ocr_missing_fields_are_not_silently_filled_with_zero(store, tmp_path):
    from src.agent.mixue_agent import MixueOperationsAgent
    from src.agent.config import AgentSettings
    from src.agent.conversation_store import ConversationStore

    memory = ConversationStore(tmp_path / "chat.sqlite")
    with store() as db:
        agent = MixueOperationsAgent(
            db_session=db,
            conversation_store=memory,
            settings=AgentSettings(checkpoint_path=str(tmp_path / "checkpoints.sqlite"), audit_path=str(tmp_path / "audit.jsonl")),
        )
        actor = agent._actor("ADMIN", "Synthetic Admin", "audit_admin")
        memory.save_ocr_draft(
            agent._conversation_owner(actor),
            agent.current_conversation_id,
            user_id=actor.user_id,
            store_id=actor.store_id,
            draft_data={"fields": {"cash_vnd": 0, "total_collected_vnd": 0, "report_date": "2026-10-02", "shift_code": "CA_SANG"}},
        )
        result = agent.confirm_ocr_draft(True, "ADMIN", "Synthetic Admin", user_id="audit_admin")
        assert result["status"] == "VALIDATION_FAILED"
        assert shift.get_all_shift_reports() == []
        agent.close()
