"""Regressions for employee editing, durable approval and chatbot intent routing."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import auth
from src.agent.mixue_agent import MixueOperationsAgent
from src.database import Base
from src.engine import plan_service
from src.models import User


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'regressions.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(auth, "SessionLocal", factory)
    monkeypatch.setattr(plan_service, "SessionLocal", factory)
    with factory() as db:
        db.add_all([User(username="manager", password_hash="unused", full_name="Manager", role="ADMIN", is_active=True),
                    User(username="barista", password_hash="unused", full_name="Barista", role="STAFF", is_active=True)])
        db.commit()
    yield factory
    engine.dispose()


def test_employee_edit_delete_and_authorization(isolated_db):
    assert auth.normalize_role("STAFF") == "STAFF_OFFICIAL"
    assert not auth.create_employee("barista", "new_employee", "Employee", "", "STAFF_OFFICIAL")[0]
    assert auth.create_employee("manager", "new_employee", "Employee", "", "STAFF_OFFICIAL")[0]
    assert auth.update_employee("manager", "new_employee", "Updated Employee", "0900000000", "STAFF_PROBATION", False)[0]
    employee = next(e for e in auth.get_all_employees() if e["username"] == "new_employee")
    assert employee["full_name"] == "Updated Employee" and not employee["is_active"]
    assert not auth.delete_employee("barista", "new_employee")[0]
    assert not auth.delete_employee("manager", "manager")[0]
    assert auth.delete_employee("manager", "new_employee")[0]
    assert not auth.update_employee("manager", "manager", "Manager", "", "STAFF", False)[0]


def test_approval_survives_new_agent_and_is_idempotent(isolated_db):
    plan = {"plan_id": "PLAN_PO_ABCD1234", "plan_type": "REPLENISHMENT_PO", "status": "PENDING_APPROVAL",
            "target_date": "2026-10-15", "created_at": "2026-10-15T09:00:00", "lines": [{"ingredient_id": "1", "recommended_order_qty": 200}],
            "verification": {"is_valid": True, "violations": []}}
    plan_service.save_plan(plan)
    with isolated_db() as db:
        agent = MixueOperationsAgent(db)
        assert not agent.tool_approve_plan(plan["plan_id"], "STAFF").get("is_approved")
        result = agent.process_query("Ký duyệt đơn nhập hàng PLAN_PO_ABCD1234", "ADMIN", "Manager")
        assert result["tool_called"] == "approve_plan"
        assert result["raw_result"]["is_approved"]
    with isolated_db() as db:
        fresh_agent = MixueOperationsAgent(db)
        repeat = fresh_agent.tool_approve_plan(plan["plan_id"], "ADMIN", "Other Manager")
        assert repeat["approved_by"] == "Manager (ADMIN)"
    saved = plan_service.list_plans("REPLENISHMENT_PO")[0]
    assert saved["lines"] == plan["lines"] and saved["status"] == "APPROVED"


@pytest.mark.parametrize("query", ["Số lượng nhân viên chính thức", "Định lượng TS1", "Sản lượng hôm nay", "Số lượng topping"])
def test_operational_quantity_is_not_salary(isolated_db, query):
    with isolated_db() as db:
        agent = MixueOperationsAgent(db)
        assert agent.tool_check_guardrail(query) is None


def test_stock_not_misclassified_as_recipe(isolated_db):
    with isolated_db() as db:
        agent = MixueOperationsAgent(db)
        result = agent.process_query("stock tồn kho", "ADMIN")
        assert result["tool_called"] != "decode_recipe_or_sticker"
        result = agent.process_query("Số lượng nhân viên chính thức", "ADMIN")
        assert result["tool_called"] == "get_employees_overview"
        assert result["raw_result"]["count"] == 1


def test_store_name_does_not_override_revenue_question(isolated_db):
    with isolated_db() as db:
        agent = MixueOperationsAgent(db)
        result = agent.process_query("Doanh thu cửa hàng hôm nay", "ADMIN")
        assert result["tool_called"] == "get_daily_sales"
