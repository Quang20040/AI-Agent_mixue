import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from src.agent.mixue_agent import MixueOperationsAgent


@pytest.fixture(scope="module")
def agent():
    ag = MixueOperationsAgent()
    yield ag
    ag.close()


def test_agent_sales_tool(agent):
    res = agent.tool_get_daily_sales()
    assert res["status"] == "SUCCESS"
    assert res["total_revenue_vnd"] > 0
    assert len(res["top_5_best_sellers"]) == 5
    assert len(res["source_refs"]) > 0


def test_agent_forecast_tool(agent):
    res = agent.tool_forecast_demand("2026-10-13")
    assert res["status"] == "SUCCESS"
    assert res["total_skus"] == 39
    assert res["total_forecasted_cups"] > 0
    assert "source_refs" in res


def test_agent_prep_tool(agent):
    res = agent.tool_optimize_topping_prep("2026-10-13")
    assert res["status"] == "SUCCESS"
    assert res["verification"]["is_valid"] is True
    assert res["draft_plan_id"].startswith("PLAN_PREP_")
    assert res["requires_manager_approval"] is True


def test_agent_replenishment_tool(agent):
    res = agent.tool_optimize_replenishment("2026-10-13")
    assert res["status"] == "SUCCESS"
    assert res["draft_plan_id"].startswith("PLAN_PO_")
    assert res["requires_manager_approval"] is True


def test_sticker_decoder_numeric_code(agent):
    # Test code 24101: 24 = Trà đào bigsize, 1 = 30% đường, 0 = Nóng, 1 = Thêm trân châu
    res = agent.tool_decode_recipe_or_sticker("24101")
    assert res["status"] == "SUCCESS"
    assert res["type"] == "CUP_STICKER_DECODE"
    assert "30%" in res["sugar"]
    assert "Nóng" in res["ice"]
    assert "Trân châu" in res["additional_topping"]


def test_rbac_approval_enforcement(agent):
    # 1. Generate a valid draft
    prep_res = agent.tool_optimize_topping_prep("2026-10-13")
    draft_id = prep_res["draft_plan_id"]

    # 2. Staff attempts approval -> Must be rejected (403/UNAUTHORIZED)
    staff_res = agent.tool_approve_plan(draft_id, user_role="STAFF", user_name="Barista")
    assert staff_res["status"] == "UNAUTHORIZED"
    assert staff_res["is_approved"] is False

    # 3. Manager attempts approval -> Must succeed
    mgr_res = agent.tool_approve_plan(draft_id, user_role="MANAGER", user_name="Store Manager")
    assert mgr_res["status"] == "SUCCESS"
    assert mgr_res["is_approved"] is True
    assert "Store Manager" in mgr_res["approved_by"]


def test_agent_staff_can_query_recipes_and_prep(agent):
    # 1. Staff query for recipe
    res_recipe = agent.process_query("Công thức TS1", user_role="STAFF", user_name="Nhân viên Bar")
    assert res_recipe["tool_called"] == "decode_recipe_or_sticker"
    assert "TS1" in res_recipe["text"]

    # 2. Staff query for topping prep
    res_prep = agent.process_query("Ngày mai nên sơ chế bao nhiêu mẻ topping?", user_role="STAFF", user_name="Nhân viên Bar")
    assert res_prep["tool_called"] == "optimize_topping_prep"
    assert "Kế hoạch sơ chế Topping" in res_prep["text"]

    # 3. Staff query for sticker decode
    res_sticker = agent.process_query("Giải mã mã tem 24101", user_role="STAFF", user_name="Nhân viên Bar")
    assert res_sticker["tool_called"] == "decode_recipe_or_sticker"
    assert "Giải mã tem dán ly Mixue" in res_sticker["text"]


def test_agent_staff_cannot_query_sales_or_inventory_or_po(agent):
    # 1. Staff blocked from sales/revenue
    res_sales = agent.process_query("Doanh thu bán hàng 30 ngày qua", user_role="STAFF", user_name="Nhân viên Bar")
    assert res_sales["tool_called"] == "rbac_restriction"
    assert "Quyền hạn bị giới hạn" in res_sales["text"]

    # 2. Staff blocked from demand forecasting
    res_fc = agent.process_query("Dự báo doanh số ngày mai", user_role="STAFF", user_name="Nhân viên Bar")
    assert res_fc["tool_called"] == "rbac_restriction"

    # 3. Staff blocked from inventory reconciliation
    res_inv = agent.process_query("Đối soát tồn kho và kiểm kê", user_role="STAFF", user_name="Nhân viên Bar")
    assert res_inv["tool_called"] == "rbac_restriction"

    # 4. Staff blocked from replenishment PO
    res_po = agent.process_query("Có cần nhập hàng đặt PO gì không?", user_role="STAFF", user_name="Nhân viên Bar")
    assert res_po["tool_called"] == "rbac_restriction"


def test_agent_admin_can_query_all_topics(agent):
    # Admin can query sales
    res_sales = agent.process_query("Doanh số bán hàng", user_role="ADMIN", user_name="Nguyễn Hạnh Chi")
    assert res_sales["tool_called"] == "get_daily_sales" or "doanh thu" in res_sales["text"].lower()

    # Admin can query forecasting
    res_fc = agent.process_query("Dự báo số ly ngày mai", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert res_fc["tool_called"] == "forecast_demand"

    # Admin can query replenishment PO
    res_po = agent.process_query("Đơn đặt hàng nhập hàng", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert res_po["tool_called"] == "optimize_replenishment"


def test_agent_salary_guardrail(agent):
    # Both staff and admin are subject to HR privacy guardrail on salary/bonus
    queries = [
        "Lương tháng này của em được bao nhiêu?",
        "Bảng lương nhân viên tháng 10",
        "Có thưởng thêm KPI gì không?",
        "Em muốn ứng lương"
    ]
    for q in queries:
        res = agent.process_query(q, user_role="STAFF", user_name="Nguyễn Văn A")
        assert res["tool_called"] == "guardrail_salary_privacy"
        assert "Bảo Mật" in res["text"] or "AI Guardrail" in res["text"] or "bảo mật" in res["text"].lower()
        assert "Bùi Văn Quang" in res["text"] or "Nguyễn Hạnh Chi" in res["text"]


def test_agent_admin_deep_queries(agent):
    # 1. Admin queries employees
    res_emp = agent.process_query("Danh sách nhân sự cửa hàng", user_role="ADMIN", user_name="Nguyễn Hạnh Chi")
    assert res_emp["tool_called"] == "get_employees_overview"
    assert "Nhân sự" in res_emp["text"]
    assert "Bùi Văn Quang" in res_emp["text"]

    # 2. Admin queries October stock ledger
    res_stock = agent.process_query("Tình hình xuất nhập tồn tháng 10", user_role="ADMIN", user_name="Nguyễn Hạnh Chi")
    assert res_stock["tool_called"] == "get_daily_stock_matrix_info"
    assert "Tháng 10/2026" in res_stock["text"]

    # 3. Admin queries sales analytics (highest, lowest, AOV)
    res_analytics = agent.process_query("Ngày nào doanh thu cao nhất và thấp nhất?", user_role="ADMIN", user_name="Nguyễn Hạnh Chi")
    assert res_analytics["tool_called"] == "get_sales_analytics"
    assert "doanh thu cao nhất" in res_analytics["text"].lower()
    assert "aov" in res_analytics["text"].lower()

    # 4. Admin queries store information
    res_store = agent.process_query("Thông tin cửa hàng và chủ quán là ai?", user_role="ADMIN", user_name="Nguyễn Hạnh Chi")
    assert res_store["tool_called"] == "get_store_and_project_info"
    assert "39 Tôn Quang Phiệt" in res_store["text"]
    assert "Nguyễn Hạnh Chi" in res_store["text"]


def test_agent_date_aware_sales_query(agent):
    # Specific date: 10/10
    res_1010 = agent.process_query("doanh thu 10/10 được bao nhiêu", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert res_1010["tool_called"] == "get_daily_sales"
    assert "37,946,000" in res_1010["text"]
    assert "1,609" in res_1010["text"]
    assert "10/10/2026" in res_1010["text"]

    # Date range: 01/10 to 05/10
    res_range = agent.process_query("doanh số từ 01/10 đến 05/10", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert res_range["tool_called"] == "get_daily_sales"
    assert "01/10/2026 đến 05/10/2026" in res_range["text"]
    assert "187,753,000" in res_range["text"]

    # Relative date: hôm qua
    res_yest = agent.process_query("doanh thu hôm qua", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert res_yest["tool_called"] == "get_daily_sales"
    assert "11/10/2026" in res_yest["text"]


def test_agent_conversation_memory_follow_up(agent):
    # Turn 1: 9/10 bán được bao nhiêu cốc
    res_t1 = agent.process_query("9/10 bán được bao nhiêu cốc", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert res_t1["tool_called"] == "get_daily_sales"
    assert "38,577,000" in res_t1["text"]
    assert "09/10/2026" in res_t1["text"]

    # Turn 2: User correction with ISO date
    res_t2 = agent.process_query("2026-10-9 cơ mà", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert res_t2["tool_called"] == "get_daily_sales"
    assert "09/10/2026" in res_t2["text"]
    assert "38,577,000" in res_t2["text"]
    assert "đính chính" in res_t2["text"]

    # Turn 3: Follow-up question
    res_t3 = agent.process_query("thế còn ngày 10/10?", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert res_t3["tool_called"] == "get_daily_sales"
    assert "10/10/2026" in res_t3["text"]
    assert "37,946,000" in res_t3["text"]


def test_agent_targeted_concise_qa(agent):
    """Kiểm tra bot trả lời đúng trọng tâm câu hỏi, không in thông tin dư thừa."""
    # 1. Hỏi món bán nhiều nhất ngày 10/10
    r_best = agent.process_query("món nào bán nhiều nhất hôm 10/10", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert "Trà cam vàng" in r_best["text"]
    assert "67 cốc" in r_best["text"]
    assert "Top 5" not in r_best["text"]  # Không xả danh sách Top 5 khi chỉ hỏi 1 món

    # 2. Hỏi tiếp nối: thế còn ngày 9/10?
    r_best_next = agent.process_query("thế còn ngày 9/10?", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert "Kem ốc quế" in r_best_next["text"]
    assert "69 cốc" in r_best_next["text"]

    # 3. Hỏi nhân viên chính thức
    r_staff_official = agent.process_query("có mấy nhân viên chính thức", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert "1 nhân viên chính thức" in r_staff_official["text"]
    assert "Lê Thị Thảo" in r_staff_official["text"]
    assert "Trần Văn Nam" not in r_staff_official["text"]  # Không xả nhân viên thử việc

    # 4. Hỏi nhân viên thử việc
    r_staff_prob = agent.process_query("có mấy nhân viên thử việc", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert "1 nhân viên thử việc" in r_staff_prob["text"]
    assert "Trần Văn Nam" in r_staff_prob["text"]
    assert "Lê Thị Thảo" not in r_staff_prob["text"]

    # 5. Hỏi tổng số nhân viên
    r_staff_count = agent.process_query("có bao nhiêu nhân viên", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert "4 nhân sự" in r_staff_count["text"]
    assert "Lê Thị Thảo" in r_staff_count["text"]
    assert "Trần Văn Nam" in r_staff_count["text"]

    # 6. Hỏi tồn kho cụ thể
    r_stock = agent.process_query("tồn kho bột kem", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert "Bột kem" in r_stock["text"]
    assert "Tồn sổ sách hiện tại" in r_stock["text"]





