# -*- coding: utf-8 -*-
"""Verification script: Demonstrating Multi-Agent Natural Language responses across all domains."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agent.mixue_agent import MixueOperationsAgent


def main():
    agent = MixueOperationsAgent()
    print("=" * 80)
    print("DEMO: HỆ THỐNG MULTI-AGENT XỬ LÝ NGÔN NGỮ TỰ NHIÊN (MIXUE 39 TÔN QUANG PHIỆT)")
    print("=" * 80)

    test_queries = [
        # Domain 1: Repo Docs & 16 CSVs (SOP Quy chuẩn đường, topping, bảo quản)
        ("STAFF", "Quy tắc đường và topping quy định thế nào khi khách gọi thêm topping thạch dừa?"),
        ("STAFF", "Thời gian sơ chế một mẻ trân châu là bao lâu và hạn dùng quy định thế nào?"),
        ("STAFF", "Quy định bảo quản nước cốt hồng trà TP06 như thế nào?"),

        # Domain 2: Database Analytics (Doanh số, chốt ca, sổ kho - Dành cho Quản lý)
        ("MANAGER", "Doanh thu bán hàng từ ngày 2026-10-01 đến 2026-10-08 và top 3 món bán chạy nhất?"),
        ("MANAGER", "Tình hình đóng ca và đối soát máy POS gần đây thế nào?"),
        ("MANAGER", "Tồn kho sổ sách của bột kem không sữa TP01 hiện tại là bao nhiêu?"),

        # Domain 3: Operations & BOM & Tem dán ly 5 số
        ("STAFF", "Công thức pha chế món Trà đào bigsize và giải mã tem dán 24101"),

        # Domain 4: RBAC Security Guardrail
        ("STAFF", "Doanh thu bán hàng hôm nay được bao nhiêu tiền?")
    ]

    for role, q in test_queries:
        print(f"\n[Người hỏi]: ({role}) \"{q}\"")
        res = agent.process_query(q, user_role=role, user_name="Người dùng Thử nghiệm")
        print(f"[Tool điều phối]: {res.get('tool_called')}")
        print(f"[Nguồn tham chiếu]: {res.get('evidence_refs')}")
        print("-" * 50)
        print(res["text"][:500] + ("..." if len(res["text"]) > 500 else ""))
        print("=" * 80)

    agent.close()


if __name__ == "__main__":
    main()
