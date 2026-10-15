# -*- coding: utf-8 -*-
"""Unit tests for Shift Closing & Revenue Extraction (Chốt Ca Bằng Ảnh & Đối Soát)."""

import pytest
from datetime import date
from sqlalchemy import func

from src.database import SessionLocal
from src.models import SalesDaily
from src.engine.shift_service import (
    get_all_shift_reports, get_daily_closing_summary,
    extract_shift_data_from_image, save_or_update_shift_report,
    SHIFT_PHOTOS_DIR
)
from src.agent.mixue_agent import MixueOperationsAgent


@pytest.fixture
def agent():
    return MixueOperationsAgent()


def test_90_days_sales_data_coverage():
    """Kiểm tra dữ liệu bán hàng đã được mở rộng đủ ~3 tháng (90 ngày) và ngày 14/10 khớp POS."""
    db = SessionLocal()
    try:
        # 1. Số ngày phủ sóng
        day_count = db.query(func.count(func.distinct(SalesDaily.business_date))).scalar()
        assert day_count >= 90, f"Expected at least 90 days of sales history, got {day_count}"

        # 2. Ngày bắt đầu và ngày kết thúc
        min_date = db.query(func.min(SalesDaily.business_date)).scalar()
        max_date = db.query(func.max(SalesDaily.business_date)).scalar()
        assert min_date <= date(2026, 7, 20), f"Data should start from mid-July 2026, got {min_date}"
        assert max_date >= date(2026, 10, 14), f"Data should reach mid-October 2026, got {max_date}"

        # 3. Doanh số ngày 14/10/2026 phải khớp chính xác với hóa đơn POS từ ảnh chụp
        pos_sales_1410 = db.query(func.sum(SalesDaily.revenue_vnd)).filter(SalesDaily.business_date == date(2026, 10, 14)).scalar()
        assert int(pos_sales_1410) == 10119000, f"Expected 10,119,000 VND on 14/10/2026, got {pos_sales_1410}"
    finally:
        db.close()


def test_shift_reports_seed_and_closing_summary():
    """Kiểm tra các ca chốt thực tế ngày 14/10/2026 từ ảnh sổ viết tay."""
    reports = get_all_shift_reports("2026-10-14")
    assert len(reports) >= 3, "Phải có đủ 3 ca (sáng, chiều, tối/tổng kết)"

    sang = next(r for r in reports if r["shift_code"] == "CA_SANG")
    assert sang["cash_vnd"] == 653000
    assert sang["bank_transfer_vnd"] == 1591000
    assert sang["total_collected_vnd"] == 2328000
    assert sang["signed_by"] == "Hà"

    chieu = next(r for r in reports if r["shift_code"] == "CA_CHIEU")
    assert chieu["cash_vnd"] == 2014000
    assert chieu["cash_diff_vnd"] == 20000
    assert chieu["bank_transfer_vnd"] == 3861000
    assert chieu["total_collected_vnd"] == 6090000
    assert chieu["signed_by"] == "Nhi"

    toi = next(r for r in reports if r["shift_code"] == "CA_TOI")
    assert toi["cash_vnd"] == 3260000
    assert toi["bank_transfer_vnd"] == 6377000
    assert toi["expenses_vnd"] == 56000
    assert toi["total_collected_vnd"] == 9877000
    assert toi["signed_by"] == "An"

    # Tổng kết cả ngày & đối soát POS
    summary = get_daily_closing_summary("2026-10-14")
    assert summary["total_collected_vnd"] == 9877000
    assert summary["pos_revenue_vnd"] == 10119000
    assert summary["variance_pos_vnd"] == -137  # Chênh lệch 137 đồng với thực thu POS


def test_shift_ai_ocr_extraction():
    """Kiểm tra AI OCR trích xuất chính xác cấu trúc trường từ ảnh chụp sổ và POS."""
    # 1. Trích xuất ca sáng
    ext_sang = extract_shift_data_from_image(
        image_path=str(SHIFT_PHOTOS_DIR / "20261014_ca_sang_chieu.jpg"),
        shift_hint="CA_SANG",
        target_date="2026-10-14"
    )
    assert ext_sang["cash_vnd"] == 653000
    assert ext_sang["bank_transfer_vnd"] == 1591000
    assert ext_sang["signed_by"] == "Hà"
    assert ext_sang["total_collected_vnd"] == 2328000

    # 2. Trích xuất ca tối tổng hợp cả ngày
    ext_toi = extract_shift_data_from_image(
        image_path=str(SHIFT_PHOTOS_DIR / "20261014_ca_toi_tong_ket.jpg"),
        shift_hint="CA_TOI",
        target_date="2026-10-14"
    )
    assert ext_toi["cash_vnd"] == 3260000
    assert ext_toi["expenses_vnd"] == 56000
    assert ext_toi["total_collected_vnd"] == 9877000
    assert ext_toi["signed_by"] == "An"


def test_agent_targeted_shift_revenue_qa(agent):
    """Kiểm tra Agent Tuyết Vương AI trả lời đúng trọng tâm về doanh thu ca."""
    # 1. Hỏi doanh thu ca sáng 14/10
    r_sang = agent.process_query("doanh thu ca sáng 14/10 bao nhiêu", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert r_sang["tool_called"] == "get_shift_revenue"
    assert "2,328,000" in r_sang["text"]
    assert "Hà" in r_sang["text"]
    assert "653,000" in r_sang["text"]
    assert "1,591,000" in r_sang["text"]

    # 2. Hỏi doanh thu ca chiều 14/10
    r_chieu = agent.process_query("doanh thu ca chiều 14/10", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert r_chieu["tool_called"] == "get_shift_revenue"
    assert "6,090,000" in r_chieu["text"]
    assert "Nhi" in r_chieu["text"]
    assert "2,014,000" in r_chieu["text"]

    # 3. Hỏi tổng kết chốt ngày 14/10
    r_close = agent.process_query("tổng thu về cả ngày 14/10 chốt sổ thế nào", user_role="ADMIN", user_name="Bùi Văn Quang")
    assert r_close["tool_called"] == "get_shift_revenue"
    assert "9,877,000" in r_close["text"]
    assert "An" in r_close["text"]
    assert "10,119,000" in r_close["text"]
    assert "Khớp tuyệt đối" in r_close["text"]
