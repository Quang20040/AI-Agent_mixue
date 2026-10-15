# -*- coding: utf-8 -*-
"""DatabaseAnalyticsAgent: Chuyên gia Phân tích Dữ liệu Cơ sở Dữ liệu & Sổ sách Tài chính.

Thực hiện truy vấn SQL sâu và phân tích số liệu thời gian thực:
- Doanh thu bán hàng theo ngày, khoảng ngày, nhóm món, best-seller, least-seller, AOV (`SalesDaily`).
- Báo cáo đóng ca, đối soát máy POS, tiền mặt, chuyển khoản, chênh lệch thu tiền (`shift_reports.json`).
- Ma trận xuất - nhập - tồn kho 31 ngày và lệnh kho chờ duyệt (`DailyStockMovement`, `Ingredient`).
- Danh mục nhân sự, phân quyền tài khoản cửa hàng (`Employee`).
"""

from datetime import date, datetime
from typing import Any
import pandas as pd
from sqlalchemy import func, desc, asc

from src.database import SessionLocal
from src.models import SalesDaily, MenuItem, Ingredient, DailyStockMovement, User, Purchase, StockCount
from src.engine.shift_service import get_all_shift_reports, get_daily_closing_summary
from src.engine.daily_stock_service import get_stock_matrix_df, get_pending_requests
from src.auth import get_all_employees


def _norm(text: str) -> str:
    import unicodedata
    if not text:
        return ""
    t = text.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").strip()


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, (date, datetime)):
        return val.date() if isinstance(val, datetime) else val
    try:
        return date.fromisoformat(str(val).strip())
    except Exception:
        return None


class DatabaseAnalyticsAgent:
    """Agent chuyên sâu về phân tích dữ liệu cơ sở dữ liệu và sổ sách F&B."""

    def __init__(self, db_session=None):
        self._external_db = db_session

    @property
    def db(self):
        return self._external_db or SessionLocal()

    def query_sales_deep(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        sku_filter: str | None = None,
        limit_top: int = 5
    ) -> dict[str, Any]:
        """Truy vấn sâu dữ liệu bán hàng với các chỉ số tổng hợp."""
        session = self.db
        try:
            q = session.query(SalesDaily).join(MenuItem, SalesDaily.sku_id == MenuItem.sku_id)
            if start_date:
                s_dt = _parse_date(start_date)
                if s_dt:
                    q = q.filter(SalesDaily.business_date >= s_dt)
            if end_date:
                e_dt = _parse_date(end_date)
                if e_dt:
                    q = q.filter(SalesDaily.business_date <= e_dt)
            if sku_filter:
                q = q.filter((MenuItem.sku_name.ilike(f"%{sku_filter}%")) | (SalesDaily.sku_id == sku_filter))

            rows = q.all()
            if not rows:
                return {
                    "status": "NO_DATA",
                    "message": f"Không tìm thấy số liệu bán hàng trong khoảng thời gian {start_date or 'đầu kỳ'} đến {end_date or 'cuối kỳ'}."
                }

            df = pd.DataFrame([{
                "date": str(r.business_date),
                "sku_id": r.sku_id,
                "sku_name": r.menu_item.sku_name if r.menu_item else r.sku_id,
                "quantity": int(r.quantity_sold),
                "unit_price": float(r.revenue_vnd) / int(r.quantity_sold) if r.quantity_sold else 0.0,
                "total_revenue": float(r.revenue_vnd) if r.revenue_vnd else 0.0
            } for r in rows])

            total_rev = float(df["total_revenue"].sum())
            total_qty = int(df["quantity"].sum())
            unique_days = df["date"].nunique()
            avg_rev_per_day = round(total_rev / unique_days, 0) if unique_days else 0.0
            avg_price_per_cup = round(total_rev / total_qty, 0) if total_qty else 0.0

            # Gom theo SKU
            sku_grp = df.groupby(["sku_id", "sku_name"]).agg(
                total_cups=("quantity", "sum"),
                total_rev=("total_revenue", "sum")
            ).reset_index()

            top_by_cups = sku_grp.sort_values(by="total_cups", ascending=False).head(limit_top).to_dict("records")
            bottom_by_cups = sku_grp.sort_values(by="total_cups", ascending=True).head(limit_top).to_dict("records")

            # Gom theo ngày
            day_grp = df.groupby("date").agg(
                rev=("total_revenue", "sum"),
                cups=("quantity", "sum")
            ).reset_index()
            best_day = day_grp.sort_values(by="rev", ascending=False).iloc[0].to_dict()
            lowest_day = day_grp.sort_values(by="rev", ascending=True).iloc[0].to_dict()

            return {
                "status": "SUCCESS",
                "start_date": start_date or df["date"].min(),
                "end_date": end_date or df["date"].max(),
                "total_revenue": total_rev,
                "total_cups": total_qty,
                "total_days": unique_days,
                "avg_revenue_per_day": avg_rev_per_day,
                "avg_price_per_cup": avg_price_per_cup,
                "best_day": best_day,
                "lowest_day": lowest_day,
                "top_best_sellers": top_by_cups,
                "top_least_sellers": bottom_by_cups,
                "evidence_ref": f"sales_daily:{start_date or 'min'}_{end_date or 'max'}"
            }
        finally:
            if not self._external_db:
                session.close()

    def query_shift_closing(self, target_date: str | None = None, shift_code: str | None = None) -> dict[str, Any]:
        """Truy vấn báo cáo ca trực và đối soát thu tiền POS."""
        all_reports = get_all_shift_reports()
        if not all_reports:
            return {"status": "NO_DATA", "message": "Chưa có báo cáo ca trực nào được ghi nhận."}

        filtered = all_reports
        if target_date:
            filtered = [r for r in filtered if r.get("business_date") == target_date or r.get("date") == target_date]
        if shift_code:
            s_clean = shift_code.strip().upper()
            filtered = [r for r in filtered if r.get("shift_code") == s_clean or r.get("shift_type") == s_clean]

        if not filtered:
            return {
                "status": "NO_DATA",
                "message": f"Không tìm thấy báo cáo ca ngày {target_date or 'gần nhất'}{(' ca ' + shift_code) if shift_code else ''}."
            }

        total_cash = sum(float(r.get("cash_collected_vnd", 0) or 0) for r in filtered)
        total_bank = sum(float(r.get("banking_transfer_vnd", 0) or 0) for r in filtered)
        total_pos = sum(float(r.get("pos_collected_vnd", 0) or 0) for r in filtered)
        total_collected = sum(float(r.get("total_collected_vnd", 0) or 0) for r in filtered)

        return {
            "status": "SUCCESS",
            "count": len(filtered),
            "reports": filtered,
            "total_cash": total_cash,
            "total_banking": total_bank,
            "total_pos": total_pos,
            "total_collected": total_collected,
            "evidence_ref": f"shift_reports:{target_date or 'all'}"
        }

    def query_daily_stock_matrix(self, ingredient_query: str | None = None) -> dict[str, Any]:
        """Truy vấn ma trận xuất nhập tồn kho tháng 10/2026."""
        matrix_df = get_stock_matrix_df()
        if matrix_df.empty:
            return {"status": "NO_DATA", "message": "Ma trận kho chưa có số liệu."}

        if ingredient_query:
            q_norm = _norm(ingredient_query)
            matched = matrix_df[matrix_df["Tên mặt hàng (Quy cách)"].apply(lambda x: q_norm in _norm(str(x)))]
            if not matched.empty:
                return {
                    "status": "SUCCESS",
                    "matched_rows": matched.to_dict("records"),
                    "total_items": len(matched),
                    "evidence_ref": "daily_stock_movements:matrix"
                }

        summary_rows = []
        for _, row in matrix_df.iterrows():
            summary_rows.append({
                "stt": row.get("STT"),
                "ing_id": row.get("Mã NL"),
                "name": row.get("Tên mặt hàng (Quy cách)"),
                "initial_stock": row.get("Tồn T9"),
                "total_in": row.get("Tổng nhập"),
                "total_out": row.get("Tổng xuất"),
                "book_stock": row.get("Tồn sổ sách"),
                "actual_count": row.get("Tồn thực tế"),
                "variance": row.get("Chênh lệch")
            })

        pending = get_pending_requests()

        return {
            "status": "SUCCESS",
            "items": summary_rows,
            "total_items": len(summary_rows),
            "pending_requests_count": len(pending),
            "evidence_ref": "daily_stock_movements:october_2026"
        }

    def query_employees_directory(self) -> dict[str, Any]:
        """Truy vấn danh bạ nhân sự cửa hàng."""
        roster = get_all_employees()
        return {
            "status": "SUCCESS",
            "total_employees": len(roster),
            "employees": [
                {
                    "username": e["username"],
                    "name": e["full_name"],
                    "role": e["role"],
                    "title": e["role_title"],
                    "badge": e["role_badge"],
                    "phone": e["phone"],
                    "must_change_password": e["must_change_password"],
                    "is_active": e["is_active"]
                }
                for e in roster
            ],
            "evidence_ref": "table:users"
        }

    def query_menu_catalogue(self, category_or_name: str | None = None) -> list[dict[str, Any]]:
        """Truy vấn danh mục thực đơn 39 món."""
        session = self.db
        try:
            q = session.query(MenuItem)
            if category_or_name:
                q = q.filter(
                    (MenuItem.sku_name.ilike(f"%{category_or_name}%")) |
                    (MenuItem.variant.ilike(f"%{category_or_name}%")) |
                    (MenuItem.sku_id.ilike(f"%{category_or_name}%"))
                )
            items = q.all()
            return [{
                "sku_id": m.sku_id,
                "sku_name": m.sku_name,
                "category": m.variant or "Khác",
                "price": float(m.selling_price_vnd) if m.selling_price_vnd else 0.0,
                "is_active": m.is_active
            } for m in items]
        finally:
            if not self._external_db:
                session.close()

    # Aliases
    get_daily_sales_analytics = query_sales_deep
    get_shift_closing_reconciliation = query_shift_closing
    get_inventory_status_overview = query_daily_stock_matrix
    get_employee_directory = query_employees_directory
