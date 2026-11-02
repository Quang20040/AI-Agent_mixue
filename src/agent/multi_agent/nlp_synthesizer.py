# -*- coding: utf-8 -*-
"""NLPSynthesizer: Bộ Tổng hợp Xử lý Ngôn ngữ Tự nhiên & Trả lời Chuyên sâu.

Chuyển đổi dữ liệu và tri thức đa nguồn từ các Agent chuyên biệt thành câu trả lời
tự nhiên, đầy đủ ý, có cấu trúc chặt chẽ và dẫn chứng số liệu minh bạch theo phong
cách Tuyết Vương Mixue (Snow King).
"""

from typing import Any
import os
from src.agent.response_policy import prep_guide_reply


class NLPSynthesizer:
    """Bộ tổng hợp câu trả lời ngôn ngữ tự nhiên cấp độ chuyên gia."""

    def __init__(self):
        # Kiểm tra xem có cấu hình LLM bên ngoài không (OpenAI / LiteLLM / Gemini)
        self.llm_enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
        self.llm_api_key = os.getenv("LLM_API_KEY", "")

    def synthesize(
        self,
        query: str,
        user_name: str = "Bạn",
        user_role: str = "STAFF",
        docs_results: list[dict[str, Any]] | None = None,
        db_results: dict[str, Any] | None = None,
        bom_results: dict[str, Any] | None = None,
        tool_called: str = "multi_agent_search"
    ) -> dict[str, Any]:
        """Tổng hợp kết quả từ các Agent thành phản hồi sâu sắc và rõ ràng."""
        docs_results = docs_results or []
        evidence_refs: list[str] = []

        sections: list[str] = []

        if db_results and db_results.get('status') not in (None, 'SUCCESS'):
            return {'text': db_results.get('message', 'Chưa có dữ liệu phù hợp với yêu cầu này.'),
                    'tool_called': tool_called, 'status': db_results['status'], 'evidence_refs': []}

        if bom_results and bom_results.get('type') == 'SOP_PREP_GUIDE' and not db_results:
            return prep_guide_reply(query, bom_results)

        # 1. Xử lý dữ liệu từ Database & Doanh thu / Ca trực / Kho
        if db_results and db_results.get("status") == "SUCCESS":
            if "total_revenue" in db_results:
                rev = db_results["total_revenue"]
                cups = db_results["total_cups"]
                days = db_results["total_days"]
                avg_day = db_results["avg_revenue_per_day"]
                s_date = db_results["start_date"]
                e_date = db_results["end_date"]
                evidence_refs.append(db_results.get("evidence_ref", "database:sales_daily"))

                sec = (
                    f"### 📊 Báo Cáo Doanh Thu Bán Hàng ({s_date} đến {e_date})\n\n"
                    f"- **Tổng doanh thu:** **{rev:,.0f} đ**\n"
                    f"- **Tổng số lượng ly bán ra:** **{cups:,} ly** ({days} ngày, Trung bình: **{avg_day:,.0f} đ / ngày**)\n"
                    f"- **Giá bán trung bình mỗi ly (AOV):** **{db_results['avg_price_per_cup']:,.0f} đ / ly**\n"
                )

                if "best_day" in db_results and db_results["best_day"]:
                    b_day = db_results["best_day"]
                    sec += f"- 🌟 **Ngày đạt đỉnh doanh số:** Ngày `{b_day['date']}` đạt **{b_day['rev']:,.0f} đ** ({b_day['cups']:,} ly)\n"

                if "top_best_sellers" in db_results and db_results["top_best_sellers"]:
                    sec += "\n**Top món bán chạy nhất:**\n"
                    for idx, top in enumerate(db_results["top_best_sellers"][:5], 1):
                        sec += f"{idx}. **{top['sku_name']}**: {top['total_cups']:,} ly ({top['total_rev']:,.0f} đ)\n"

                sections.append(sec)

            elif "reports" in db_results:
                evidence_refs.append(db_results.get("evidence_ref", "shift_reports"))
                reports = db_results["reports"]
                sec = f"### 📋 Đối Soát Thu Tiền & Đóng Ca ({len(reports)} báo cáo ca)\n\n"
                sec += f"- **Tổng tiền mặt thu về:** {db_results['total_cash']:,.0f} đ\n"
                sec += f"- **Tổng chuyển khoản ngân hàng:** {db_results['total_banking']:,.0f} đ\n"
                sec += f"- **Tổng doanh thu máy POS ghi nhận:** {db_results['total_pos']:,.0f} đ\n"
                sec += f"- **Tổng thực thu:** **{db_results['total_collected']:,.0f} đ**\n\n"

                sec += "| Ngày | Ca | Trưởng ca | Thực thu (VNĐ) | Doanh thu POS | Trạng thái đối soát |\n"
                sec += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                for r in reports[:5]:
                    d = r.get("business_date") or r.get("date") or "N/A"
                    c = r.get("shift_code") or r.get("shift_type") or "N/A"
                    lead = r.get("leader") or r.get("cashier") or r.get("signed_by") or "Quản lý"
                    col = float(r.get("total_collected_vnd", 0) or 0)
                    pos = float(r.get("pos_collected_vnd", 0) or 0)
                    stt = r.get("reconciliation_status", "Đã chốt ca")
                    sec += f"| {d} | {c} | {lead} | {col:,.0f} | {pos:,.0f} | {stt} |\n"
                sections.append(sec)

            elif "items" in db_results:
                evidence_refs.append(db_results.get("evidence_ref", "daily_stock_matrix"))
                items = db_results["items"]
                sec = f"### 📦 File kho tháng này ({db_results['total_items']} mặt hàng chính)\n\n"
                sec += f"- **Lệnh kho chờ Quản lý duyệt:** **{db_results['pending_requests_count']} lệnh**\n\n"
                sec += "| Mã NL | Tên mặt hàng | Tồn đầu | Tổng nhập | Tổng xuất | Tồn sổ sách | Tồn thực tế |\n"
                sec += "| :---: | :--- | :---: | :---: | :---: | :---: | :---: |\n"
                for it in items[:10]:
                    sec += f"| {it['ing_id']} | {it['name']} | {it['initial_stock']} | {it['total_in']} | {it['total_out']} | **{it['book_stock']}** | {it['actual_count']} |\n"
                sections.append(sec)

            elif "matched_rows" in db_results:
                evidence_refs.append(db_results.get("evidence_ref", "daily_stock_matrix"))
                rows = db_results["matched_rows"]
                sec = "### 📦 Chi Tiết Tồn Kho Mặt Hàng Yêu Cầu\n\n"
                for r in rows:
                    sec += f"**Mặt hàng:** {r.get('Tên mặt hàng (Quy cách)')} (Mã: `{r.get('Mã NL')}`)\n"
                    sec += f"- Tồn đầu kỳ: `{r.get('initial_stock', next((v for k, v in r.items() if str(k).startswith('Tồn cuối T')), '—'))}` | Tổng nhập: `{r.get('Tổng nhập')}` | Tổng xuất: `{r.get('Tổng xuất')}`\n"
                    sec += f"- **Tồn sổ sách hiện tại:** **{r.get('Tồn sổ sách')}** đơn vị\n"
                    sec += f"- Tồn thực tế kiểm kê: `{r.get('Tồn thực tế')}` (Chênh lệch: `{r.get('Chênh lệch')}`)\n\n"
                sections.append(sec)

            elif "employees" in db_results:
                evidence_refs.append(db_results.get("evidence_ref", "table:employees"))
                emps = db_results["employees"]
                sec = f"### 👥 Danh Bạ Nhân Sự Cửa Hàng ({len(emps)} nhân sự)\n\n"
                sec += "| Họ và tên | Tài khoản | Vai trò | Chức danh | Huy hiệu | Đổi pass lần đầu |\n"
                sec += "| :--- | :--- | :---: | :--- | :--- | :---: |\n"
                for e in emps:
                    ch_p = "Cần đổi" if e["must_change_password"] else "Đã an toàn"
                    sec += f"| **{e['name']}** | `{e['username']}` | {e['role']} | {e['title']} | {e['badge']} | {ch_p} |\n"
                sections.append(sec)

        # 2. Xử lý dữ liệu từ Operations BOM & Công thức
        if bom_results and bom_results.get("status") == "SUCCESS":
            if "components" in bom_results:
                evidence_refs.append(bom_results.get("evidence_ref", "bom_recipes"))
                sec = (
                    f"### 🍵 Bảng Công Thức Định Lượng Chuẩn (BOM): {bom_results['sku_name']}\n\n"
                    f"- **Mã món:** `{bom_results['sku_id']}` | **Nhóm:** {bom_results['category']}\n"
                    f"- **Giá bán niêm yết:** **{bom_results['price_vnd']:,.0f} đ**\n"
                    f"- **Giá vốn nguyên liệu (Cost):** **{bom_results['total_cost_vnd']:,.0f} đ**\n"
                    f"- **Biên lợi nhuận gộp:** **{bom_results['gross_margin_pct']}%**\n\n"
                    f"**Chi tiết thành phần pha chế quầy bar:**\n\n"
                    f"| Mã NL | Tên nguyên liệu | Định lượng | Đơn vị | Quy chuẩn bảo quản |\n"
                    f"| :---: | :--- | :---: | :---: | :--- |\n"
                )
                for comp in bom_results["components"]:
                    sec += f"| {comp['ingredient_id']} | {comp['ingredient_name']} | **{comp['quantity']}** | {comp['unit']} | {comp['storage_rule']} |\n"
                sections.append(sec)

            elif "product" in bom_results:
                evidence_refs.append(bom_results.get("evidence_ref", "cup_sticker"))
                sec = (
                    f"### 🏷️ Giải Mã Mã Tem Dán Ly: #{bom_results['code']}\n\n"
                    f"- 🧋 **Món đồ uống:** **{bom_results['product']}** (Mã phân hệ: `{bom_results['product_code']}`)\n"
                    f"- 🍬 **Mức đường:** **{bom_results['sugar']}**\n"
                    f"- 🧊 **Mức đá:** **{bom_results['ice']}**\n"
                    f"- 🍨 **Topping thêm:** **{bom_results['additional_topping']}**\n\n"
                    f"**Quy chuẩn pha chế SOP áp dụng:**\n"
                )
                for r in bom_results.get("rules_list", []):
                    sec += f"- {r}\n"
                sections.append(sec)

            elif bom_results.get("type") == "SOP_PREP_GUIDE":
                reply = prep_guide_reply(query, bom_results)
                sections.append(reply['text'])
                evidence_refs.extend(reply['evidence_refs'])

        # 3. Xử lý tri thức trích xuất từ Repo Docs, Báo cáo & Quy chuẩn CSV
        if docs_results and not sections:
            sec = ""
            for doc in docs_results[:1]:
                evidence_refs.append(f"file:{doc['file_path']}")
                content = doc["content"]
                if content.strip().startswith("|"):
                    # Định dạng bảng Markdown hoàn chỉnh
                    if len(content) > 3000:
                        content = content[:3000] + "\n\n*(Đã rút gọn bớt các dòng tiếp theo...)*"
                    sec += f"{content}\n\n"
                else:
                    clean_snippet = content
                    if len(clean_snippet) > 800:
                        clean_snippet = clean_snippet[:800] + "..."
                    sec += f"> {clean_snippet}\n\n"
            sections.append(sec)

        if not sections:
            return {'text': 'Mình chưa tìm thấy thông tin phù hợp. Bạn nói rõ món hoặc nội dung cần hỏi nhé.',
                    'tool_called': tool_called, 'evidence_refs': [], 'status': 'NO_DATA'}
        final_text = "\n\n".join(sections).strip()

        # Loại bỏ trùng lặp evidence_refs
        unique_refs = list(dict.fromkeys(evidence_refs))

        return {
            "text": final_text,
            "tool_called": tool_called,
            "evidence_refs": unique_refs,
            "status": "SUCCESS"
        }
