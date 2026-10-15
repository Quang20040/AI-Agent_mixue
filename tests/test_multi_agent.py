# -*- coding: utf-8 -*-
import pytest
from src.agent.multi_agent.repo_docs_agent import RepoDocsAgent
from src.agent.multi_agent.database_analytics_agent import DatabaseAnalyticsAgent
from src.agent.multi_agent.operations_bom_agent import OperationsBOMAgent
from src.agent.multi_agent.nlp_synthesizer import NLPSynthesizer
from src.agent.multi_agent.multi_agent_orchestrator import MultiAgentOrchestrator
from src.agent.mixue_agent import MixueOperationsAgent


def test_repo_docs_agent_search():
    docs_agent = RepoDocsAgent()
    assert len(docs_agent.chunks) > 50

    # Test search for sugar and topping rules
    res = docs_agent.search("quy tắc đường và topping khi thêm thạch dừa")
    assert len(res) > 0
    assert any("16_Quy_tac_duong_va_topping" in r["file_path"] for r in res)

    # Test search for storage regulations
    res_storage = docs_agent.get_storage_rules("hồng trà")
    assert isinstance(res_storage, list)

    # Test search for prep times
    res_prep = docs_agent.get_prep_times("trân châu")
    assert isinstance(res_prep, list)


def test_database_analytics_agent():
    db_agent = DatabaseAnalyticsAgent()
    sales = db_agent.get_daily_sales_analytics(start_date="2026-10-01", end_date="2026-10-10")
    assert sales["status"] == "SUCCESS"
    assert sales["total_revenue"] > 0
    assert len(sales["top_best_sellers"]) > 0

    shifts = db_agent.get_shift_closing_reconciliation()
    assert shifts["status"] == "SUCCESS"
    assert len(shifts["reports"]) > 0

    stock = db_agent.get_inventory_status_overview()
    assert stock["status"] == "SUCCESS"
    assert stock["total_items"] > 0

    emps = db_agent.get_employee_directory()
    assert emps["status"] == "SUCCESS"
    assert len(emps["employees"]) > 0


def test_operations_bom_agent():
    bom_agent = OperationsBOMAgent()
    recipe = bom_agent.lookup_recipe_bom("TS1")
    assert recipe["status"] == "SUCCESS"
    assert recipe["sku_id"] == "TS1"
    assert len(recipe["components"]) > 0

    sticker = bom_agent.decode_cup_sticker("24101")
    assert sticker["status"] == "SUCCESS"
    assert sticker["code"] == "24101"
    assert "30%" in sticker["sugar"]


def test_nlp_synthesizer():
    synthesizer = NLPSynthesizer()
    dummy_db = {
        "status": "SUCCESS",
        "total_revenue": 15000000.0,
        "total_cups": 750,
        "total_days": 5,
        "avg_revenue_per_day": 3000000.0,
        "avg_price_per_cup": 20000.0,
        "start_date": "2026-10-01",
        "end_date": "2026-10-05",
        "top_best_sellers": [{"sku_name": "Trà sữa Trân châu", "total_cups": 300, "total_rev": 7500000.0}]
    }
    result = synthesizer.synthesize(
        query="Báo cáo doanh thu đầu tháng 10",
        user_name="Quản lý",
        user_role="MANAGER",
        db_results=dummy_db
    )
    assert result["status"] == "SUCCESS"
    assert "15,000,000" in result["text"]
    assert "Trà sữa Trân châu" in result["text"]
    assert len(result["evidence_refs"]) > 0


def test_multi_agent_orchestrator_integration():
    orchestrator = MultiAgentOrchestrator()

    # Query 1: Knowledge / SOP
    ans_sop = orchestrator.dispatch("Quy tắc giảm đường khi khách gọi thêm topping thạch dừa", user_role="STAFF")
    assert ans_sop["status"] == "SUCCESS"
    assert "16_Quy_tac_duong_va_topping" in str(ans_sop["evidence_refs"])

    # Query 2: Manager sales inquiry
    ans_sales = orchestrator.dispatch("Doanh thu bán hàng từ ngày 2026-10-01 đến 2026-10-10", user_role="MANAGER")
    assert ans_sales["status"] == "SUCCESS"
    assert any("sales_daily" in ref for ref in ans_sales["evidence_refs"])

    # Query 3: Staff sales inquiry -> Blocked
    ans_blocked = orchestrator.dispatch("Doanh thu bán hàng tháng 10", user_role="STAFF")
    assert ans_blocked["tool_called"] == "rbac_restriction"

    # Query 4: Sổ kho
    ans_stock = orchestrator.dispatch("Xem tồn kho TP01", user_role="MANAGER")
    assert ans_stock["status"] == "SUCCESS"
    assert "TP01" in ans_stock["text"]


def test_mixue_operations_agent_natural_language_fallback():
    agent = MixueOperationsAgent()
    try:
        # A question that previous canned mock would have completely failed or given rigid intro:
        res = agent.process_query("Quy định thời gian bảo quản của nước cốt hồng trà là mấy tiếng?", user_role="STAFF")
        assert res["status"] == "SUCCESS"
        assert len(res["text"]) > 100
        # Check that it did NOT output canned mock greeting fallback
        assert "Xin chào! Tôi là Trợ lý Vận hành Siêu thông minh Mixue (Snow King)" not in res["text"]
    finally:
        agent.close()


def test_sop_cooking_guide_typo_chan_trau():
    agent = MixueOperationsAgent()
    try:
        # User query with phonetic typo "cách nấu chân trâu"
        res = agent.process_query("cách nấu chân trâu", user_role="STAFF", user_name="Barista")
        assert res["status"] == "SUCCESS"
        text = res["text"]

        # 1. Must define what trân châu is
        assert "Định nghĩa" in text or "Trân châu" in text

        # 2. Must give cooking process and exact minutes (35p nấu, 30p ủ, 10p ủ đường)
        assert "35 phút" in text
        assert "30 phút" in text
        assert "10 phút" in text

        # 3. Must give exact ingredients / batches
        assert "Trân châu đen" in text
        assert "Đường mật" in text

        # 4. Must give shelf-life / storage (4 giờ)
        assert "4 giờ" in text

        # 5. Must cite files in evidence_refs
        assert any("09_Cong_thuc_so_che_theo_me" in ref for ref in res["evidence_refs"])
    finally:
        agent.close()

