# -*- coding: utf-8 -*-
"""MultiAgentOrchestrator: Tuyết Vương Trưởng Điều Phối Đa Tác Tử (Multi-Agent Supervisor).

Điều phối và tổng hợp trí tuệ từ 4 tác tử chuyên môn:
1. RepoDocsAgent: Khám phá toàn bộ file markdown, 16 bảng CSV quy chuẩn Mixue, báo cáo kiểm toán.
2. DatabaseAnalyticsAgent: Phân tích cơ sở dữ liệu bán hàng, sổ đóng ca POS, ma trận kho 31 ngày.
3. OperationsBOMAgent: Định lượng công thức pha chế BOM, giải mã tem ly, kế hoạch nấu mẻ & đơn đặt hàng PO.
4. NLPSynthesizer: Xử lý ngôn ngữ tự nhiên, tổng hợp câu trả lời sâu sắc, minh bạch và đầy đủ dẫn chứng.
"""

import re
from typing import Any
from pathlib import Path

from .repo_docs_agent import RepoDocsAgent
from .database_analytics_agent import DatabaseAnalyticsAgent
from .operations_bom_agent import OperationsBOMAgent
from .nlp_synthesizer import NLPSynthesizer
from src.agent.response_policy import casual_reply, conversational_reply, is_prep_guide_request


def _norm(text: str) -> str:
    import unicodedata
    if not text:
        return ""
    t = text.lower().replace("đ", "d")
    norm = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").strip()
    norm = re.sub(r"\bchan\s*trau\b", "tran chau", norm)
    norm = re.sub(r"\bchan\s*chau\b", "tran chau", norm)
    norm = re.sub(r"\btran\s*trau\b", "tran chau", norm)
    return norm


class MultiAgentOrchestrator:
    """Tuyết Vương Trưởng: Điều phối đa tác tử xử lý ngôn ngữ tự nhiên và truy xuất đa nguồn."""

    def __init__(self, db_session=None, repo_dir: Path | str | None = None):
        self.docs_agent = RepoDocsAgent(repo_dir=repo_dir)
        self.db_agent = DatabaseAnalyticsAgent(db_session=db_session)
        self.bom_agent = OperationsBOMAgent(db_session=db_session)
        self.synthesizer = NLPSynthesizer()

    def dispatch(
        self,
        query: str,
        user_role: str = "MANAGER",
        user_name: str = "Quản lý",
        chat_history: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Phân tích ý định câu hỏi tự nhiên và điều phối các Sub-Agents tìm kiếm đồng thời."""
        q = query.strip()
        q_norm = _norm(q)
        clean_role = (user_role or "STAFF").strip().upper()
        is_admin = clean_role in ["ADMIN", "MANAGER", "OWNER"]
        small_talk = conversational_reply(query, is_admin=is_admin)
        if small_talk:
            return small_talk
        light_chat = casual_reply(query)
        if light_chat:
            return light_chat

        # 0. RBAC Guardrail: Chặn Nhân viên truy cập dữ liệu doanh số, kho, đơn PO, nhân sự
        if not is_admin:
            admin_restricted_patterns = [
                r"\bdoanh\s+thu\b", r"\bdoanh\s+so\b", r"\bban\s+hang\b", r"\bso\s+ly\b", r"\bso\s+coc\b",
                r"\btien\b", r"\bloi\s+nhuan\b", r"\bthu\s+duoc\s+bao\s+nhieu\b", r"\bban\s+duoc\s+bao\s+nhieu\b",
                r"\bban\s+chay\s+nhat\b", r"\baov\b", r"\bgia\s+trung\s+binh\b",
                r"\bdu\s+bao\b", r"\bforecast\b", r"\bdu\s+doan\b", r"\bhao\s+hut\b", r"\bwaste\b",
                r"\bdoi\s+soat\b", r"\bkiem\s+ke\b", r"\blech\s+kho\b", r"\bton\s+kho\b", r"\bso\s+kho\b", r"\bthe\s+kho\b", r"\blenh\s+kho\b",
                r"\bnhap\s+hang\b", r"\bdat\s+hang\b", r"\bpo\b", r"\bnhan\s+vien\b", r"\bnhan\s+su\b", r"\btai\s+khoan\b"
            ]
            is_sop_allowed_kw = any(w in q_norm for w in [
                "cong thuc", "pha che", "dinh luong", "lam mon", "tem", "ma tem",
                "bao quan", "han dung", "thoi gian", "so che", "nau", "cach lam", "sop", "huong dan"
            ])
            has_admin_restriction = any(re.search(pat, q_norm) for pat in admin_restricted_patterns)
            if has_admin_restriction and not is_sop_allowed_kw:
                return {
                    "text": (
                        "🔒 **Quyền hạn bị giới hạn (Tài khoản Nhân viên):**\n\n"
                        "Bạn đang đăng nhập với vai trò **Nhân viên quầy / Pha chế**. Theo quy định bảo mật vận hành tại chi nhánh Mixue 39 Tôn Quang Phiệt, **nhân viên không được phép xem doanh thu, sản lượng bán hàng, tồn kho, đơn nhập hàng và danh sách nhân sự**.\n\n"
                        "Bạn chỉ được quyền tra cứu:\n"
                        "- 🍵 **Công thức sản phẩm & định lượng chuẩn (BOM)** (Ví dụ: `Công thức TS1`)\n"
                        "- 🥣 **Quy chuẩn sơ chế & hạn dùng SOP** (Ví dụ: `Sơ chế trân châu`, `Hạn bảo quản trà đào`)\n"
                        "- 🏷️ **Giải mã tem dán ly 5 chữ số** (Ví dụ: `24101`)\n\n"
                        "*Các dữ liệu về doanh thu, sản lượng, kiểm kê kho và đơn nhập hàng (PO) chỉ dành riêng cho Quản lý và Chủ cửa hàng (Admin).*"
                    ),
                    "tool_called": "rbac_restriction",
                    "status": "FORBIDDEN",
                    "evidence_refs": ["policy:RBAC_Store_2132_Staff_Restriction"]
                }

        docs_results: list[dict[str, Any]] = []
        db_results: dict[str, Any] | None = None
        bom_results: dict[str, Any] | None = None
        primary_tool = "multi_agent_search"

        if is_prep_guide_request(q):
            guide = self.bom_agent.get_sop_prep_guide(q)
            if guide:
                return self.synthesizer.synthesize(query=q, user_name=user_name, user_role=clean_role,
                                                  bom_results=guide, tool_called='get_sop_prep_guide')

        # 1. Phát hiện câu hỏi liên quan đến Hướng dẫn nấu mẻ / Sơ chế Topping / Định nghĩa (SOP Prep Guide)
        is_prep_sop_query = any(w in q_norm for w in [
            "cach nau", "huong dan nau", "quy trinh nau", "cach lam", "nau the nao", "so che the nao",
            "cach pha", "cach u", "huong dan so che", "quy trinh so che", "dinh nghia", "la gi", "luoc", "nau", "so che"
        ])
        if is_prep_sop_query or any(k in q_norm for k in ["tran chau", "chan trau", "thach dao", "thach duong den", "pudding", "kem tuoi", "u tra"]):
            sop_res = self.bom_agent.get_sop_prep_guide(q)
            if sop_res:
                bom_results = sop_res
                primary_tool = "get_sop_prep_guide"

        # 2. Phát hiện câu hỏi liên quan đến Công thức Pha chế (BOM) & Tem dán ly (nếu chưa có kết quả sơ chế)
        if not bom_results:
            is_recipe_query = any(w in q_norm for w in ["cong thuc", "dinh luong", "pha che", "nguyen lieu cua mon", "cach pha", "mon"])
            is_sticker_query = any(w in q_norm for w in ["ma tem", "tem dan", "tem in", "giai ma tem", "ma ly"])
            
            # Kiểm tra mã tem 5 số
            code_match = re.search(r"\b(\d{5})\b", q)
            if code_match and (is_sticker_query or "tem" in q_norm or "ly" in q_norm or len(q.split()) <= 4):
                bom_results = self.bom_agent.decode_cup_sticker(code_match.group(1))
                primary_tool = "decode_recipe_or_sticker"

            elif is_recipe_query:
                # Trích xuất tên món
                matched_items = self.db_agent.query_menu_catalogue()
                for it in matched_items:
                    if _norm(it["sku_name"]) in q_norm or _norm(it["sku_id"]) in q_norm:
                        bom_results = self.bom_agent.get_recipe_details(it["sku_id"])
                        primary_tool = "decode_recipe_or_sticker"
                        break

        # 2. Phát hiện câu hỏi liên quan đến Doanh số / Bán hàng (Chỉ Admin)
        is_sales_query = any(w in q_norm for w in [
            "doanh thu", "doanh so", "ban duoc bao nhieu", "so ly", "so coc",
            "ban chay nhat", "ban it nhat", "best seller", "aov", "gia trung binh"
        ])
        if is_sales_query and is_admin:
            primary_tool = "get_daily_sales"
            # Trích xuất ngày nếu có
            from src.agent.mixue_agent import _parse_query_date_range
            s_d, e_d = _parse_query_date_range(q)
            db_results = self.db_agent.query_sales_deep(start_date=s_d, end_date=e_d)

        # 3. Phát hiện câu hỏi liên quan đến Đóng ca & Đối soát POS (Chỉ Admin)
        is_shift_query = any(w in q_norm for w in ["ca truc", "dong ca", "chot ca", "ca sang", "ca chieu", "ca toi", "pos", "lech tien", "thuc thu"])
        if is_shift_query and is_admin:
            primary_tool = "get_shift_revenue"
            from src.agent.mixue_agent import _parse_query_date_range
            s_d, _ = _parse_query_date_range(q)
            shift_code = None
            if "ca chieu" in q_norm:
                shift_code = "CA_CHIEU"
            elif "ca sang" in q_norm:
                shift_code = "CA_SANG"
            elif "ca toi" in q_norm:
                shift_code = "CA_TOI"
            db_results = self.db_agent.query_shift_closing(target_date=s_d, shift_code=shift_code)

        # 4. Phát hiện câu hỏi liên quan đến Sổ kho 31 ngày (Chỉ Admin)
        is_stock_query = any(w in q_norm for w in ["ton kho", "so kho", "nhap kho", "xuat kho", "kiem ke", "the kho", "lenh kho"])
        if is_stock_query and is_admin:
            primary_tool = "get_daily_stock_matrix_info"
            db_results = self.db_agent.query_daily_stock_matrix(ingredient_query=q)

        # 5. Phát hiện câu hỏi liên quan đến Nhân sự cửa hàng (Chỉ Admin)
        is_hr_query = any(w in q_norm for w in ["nhan vien", "nhan su", "tai khoan", "chuc danh", "chu quan", "quan ly"])
        if is_hr_query and is_admin:
            primary_tool = "get_employees_overview"
            db_results = self.db_agent.query_employees_directory()

        # 6. Luôn luôn kích hoạt RepoDocsAgent để lục tìm tài liệu, SOP, quy chuẩn, báo cáo kiểm toán
        technical = any(word in q_norm for word in ['kien truc', 'ma nguon', 'repo', 'lap trinh', 'kiem thu', 'database', 'langgraph'])
        docs_hits = self.docs_agent.search(q, top_k=3, category_filter=None if technical else 'SOP_QUY_CHUAN') if not (db_results or bom_results) else []
        if docs_hits:
            docs_results = docs_hits

        # 7. Nếu câu hỏi về quy định bảo quản cụ thể
        if any(w in q_norm for w in ["bao quan", "han dung", "nhiet do"]):
            rules = self.docs_agent.get_storage_rules()
            if rules:
                clean_rules_text = "\n".join([f"- **{r['code']}**: {r['condition']} (Hạn dùng: **{r['shelf_life']}**)" for r in rules[:8]])
                docs_results.append({
                    "file_path": "DU_LIEU_CAN_NHAP/10_Quy_dinh_bao_quan_theo_anh.csv",
                    "category": "SOP_BAO_QUAN",
                    "title": "Bảng Quy định Điều kiện Bảo quản & Hạn dùng",
                    "content": clean_rules_text
                })

        # 8. Nếu câu hỏi về thời gian sơ chế mẻ
        if any(w in q_norm for w in ["thoi gian so che", "nau mat bao lau", "so che mat bao lau", "u tra bao lau"]):
            times = self.docs_agent.get_prep_times()
            if times:
                clean_times_text = "\n".join([f"- **{t['semi_product']}**: {t['prep_time']} ({t['notes']})" for t in times[:8]])
                docs_results.append({
                    "file_path": "DU_LIEU_CAN_NHAP/13_Thoi_gian_so_che_theo_anh.csv",
                    "category": "SOP_THOI_GIAN",
                    "title": "Bảng Thời gian Sơ chế Theo Mẻ",
                    "content": clean_times_text
                })

        # 9. Nếu câu hỏi về 16 quy tắc đường & topping
        if any(w in q_norm for w in ["quy tac duong", "them topping", "giam duong", "duong va topping"]):
            sugars = self.docs_agent.get_sugar_and_topping_rules()
            if sugars:
                clean_sugars = "\n".join([f"- **{s['scope']}**: {s['rule']}" for s in sugars])
                docs_results.append({
                    "file_path": "DU_LIEU_CAN_NHAP/16_Quy_tac_duong_va_topping.csv",
                    "category": "SOP_DUONG_TOPPING",
                    "title": "16 Quy tắc Đường & Topping Quầy Bar",
                    "content": clean_sugars
                })

        # 10. Chuyển toàn bộ dữ liệu thu thập qua Bộ tổng hợp ngôn ngữ tự nhiên NLPSynthesizer
        return self.synthesizer.synthesize(
            query=q,
            user_name=user_name,
            user_role=clean_role,
            docs_results=docs_results,
            db_results=db_results,
            bom_results=bom_results,
            tool_called=primary_tool
        )
