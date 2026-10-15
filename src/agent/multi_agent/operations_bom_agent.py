# -*- coding: utf-8 -*-
"""OperationsBOMAgent: Chuyên gia Công thức Pha chế (BOM), Quy chuẩn SOP & Chuỗi Cung ứng.

Quản lý:
- Định lượng công thức pha chế chi tiết từng gam/ml trà, bột sữa, đường, siro, thạch, topping (`BOMEngine`, `RecipeBOM`).
- Giải mã tem in dán ly 5 chữ số kết hợp 16 quy tắc gia giảm đường & topping thực tế.
- Lập kế hoạch sơ chế topping theo mẻ (Topping Prep Batch Optimization).
- Lập đơn đặt hàng bổ sung kho định kỳ làm tròn theo kiện/thùng (Replenishment PO).
"""

from typing import Any
from datetime import date, timedelta
from src.database import SessionLocal
from src.models import MenuItem, RecipeBOM, Ingredient
from src.engine.bom_engine import BOMEngine
from src.engine.forecasting import ForecastingEngine
from src.engine.optimizer import OptimizerEngine
from src.engine.validator import IndependentPlanValidator
from src.engine.plan_service import save_plan

SUGAR_MAP = {
    "0": "0% (Không đường)",
    "1": "30% (Rất ít đường)",
    "2": "50% (Ít đường)",
    "3": "70% (Vừa đường)",
    "4": "100% (Đường chuẩn)"
}

ICE_MAP = {
    "0": "Nóng (Hot)",
    "1": "Không đá (No ice)",
    "2": "Ít đá (Less ice)",
    "3": "Đá vừa (Medium ice)",
    "4": "Đá chuẩn (Standard ice)"
}

TOPPING_MAP = {
    "0": "Không thêm topping",
    "1": "Trân châu nguyên vị (+1 vá)",
    "2": "Thạch dừa (+1 vá)",
    "3": "Thạch đường đen (+1 vá)",
    "4": "Thạch đào (+1 vá)",
    "5": "Nha đam (+1 vá)"
}

SKU_PREFIX_MAP = {
    "01": ("Kem ốc quế", "01440"),
    "02": ("Kem siêu sundae dâu tây", "02440"),
    "03": ("Kem siêu sundae xoài", "03440"),
    "04": ("Kem siêu sundae socola", "04440"),
    "05": ("Kem siêu sundae lô hội", "05440"),
    "06": ("Hồng trà kem tươi", "06440"),
    "07": ("Lục trà kem tươi", "07440"),
    "11": ("Trà chanh tươi ướp lạnh", "11440"),
    "12": ("Nước chanh tươi ướp lạnh", "12440"),
    "21": ("Trà sữa trân châu đường đen", "21441"),
    "22": ("Trà sữa 2J", "22440"),
    "23": ("Trà sữa nướng", "23440"),
    "24": ("Trà đào bigsize", "24440"),
    "25": ("Trà sữa ba anh em", "25440"),
    "31": ("Cà phê Americano", "31040"),
}


def _norm(text: str) -> str:
    import unicodedata
    if not text:
        return ""
    t = text.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").strip()


class OperationsBOMAgent:
    """Agent chuyên sâu về công thức pha chế, quy chuẩn quầy bar và tối ưu hóa mẻ nấu."""

    def __init__(self, db_session=None):
        self._external_db = db_session
        self.bom_engine = BOMEngine(db_session=db_session)
        self.fc_engine = ForecastingEngine(db_session=db_session)
        self.opt_engine = OptimizerEngine(db_session=db_session)
        self.validator = IndependentPlanValidator(db_session=db_session)

    @property
    def db(self):
        return self._external_db or SessionLocal()

    def get_recipe_details(self, item_name_or_sku: str) -> dict[str, Any]:
        """Tra cứu công thức định lượng chi tiết (BOM) của một món trong thực đơn."""
        session = self.db
        try:
            q_norm = _norm(item_name_or_sku)
            menu_item = session.query(MenuItem).filter(
                (MenuItem.sku_id.ilike(f"%{item_name_or_sku}%")) |
                (MenuItem.sku_name.ilike(f"%{item_name_or_sku}%"))
            ).first()

            if not menu_item:
                # Tìm mờ trong danh sách
                all_items = session.query(MenuItem).all()
                for it in all_items:
                    if q_norm in _norm(it.sku_name) or q_norm in _norm(it.sku_id):
                        menu_item = it
                        break

            if not menu_item:
                return {
                    "status": "NOT_FOUND",
                    "message": f"Không tìm thấy món '{item_name_or_sku}' trong hệ thống thực đơn 39 món Mixue."
                }

            # Lấy các thành phần BOM
            boms = session.query(RecipeBOM, Ingredient).join(
                Ingredient, RecipeBOM.ingredient_id == Ingredient.ingredient_id
            ).filter(RecipeBOM.sku_id == menu_item.sku_id).all()

            components = []
            total_cost = 0.0
            for b, ing in boms:
                qty = float(getattr(b, "quantity_per_item", getattr(b, "quantity", 0.0)))
                cost = float(ing.unit_cost_vnd) if ing.unit_cost_vnd else 0.0
                line_cost = qty * cost
                total_cost += line_cost
                components.append({
                    "ingredient_id": ing.ingredient_id,
                    "ingredient_name": ing.ingredient_name,
                    "quantity": qty,
                    "unit": b.unit,
                    "unit_cost": cost,
                    "line_cost": round(line_cost, 0),
                    "storage_rule": ing.shelf_life_rule_id or "Theo quy chuẩn bao bì"
                })

            margin = 0.0
            price = float(getattr(menu_item, "selling_price_vnd", getattr(menu_item, "price", 0.0)))
            if price > 0 and total_cost > 0:
                margin = round(((price - total_cost) / price) * 100, 1)

            return {
                "status": "SUCCESS",
                "sku_id": menu_item.sku_id,
                "sku_name": menu_item.sku_name,
                "category": getattr(menu_item, "variant", "") or "Chuẩn",
                "price_vnd": price,
                "total_cost_vnd": round(total_cost, 0),
                "gross_margin_pct": margin,
                "components": components,
                "evidence_ref": f"bom_recipes:{menu_item.sku_id}",
                "total_ingredients": len(components)
            }
        finally:
            if not self._external_db:
                session.close()

    def decode_cup_sticker(self, code_str: str) -> dict[str, Any]:
        """Giải mã tem dán in ly 5 chữ số quầy bar Mixue."""
        clean_code = str(code_str).strip()
        if len(clean_code) < 5 or not clean_code.isdigit():
            return {
                "status": "ERROR",
                "message": f"Mã tem '{code_str}' không hợp lệ. Quy chuẩn tem ly gồm đúng 5 chữ số (Ví dụ: 24101, 01440)."
            }

        p_code = clean_code[:2]
        s_code = clean_code[2]
        i_code = clean_code[3]
        t_code = clean_code[4]

        drink_name = SKU_PREFIX_MAP.get(p_code, (f"Món đồ uống mã #{p_code}", ""))[0]
        sugar_desc = SUGAR_MAP.get(s_code, "Đường chuẩn (100%)")
        ice_desc = ICE_MAP.get(i_code, "Đá chuẩn (Standard)")
        topping_desc = TOPPING_MAP.get(t_code, "Không thêm topping")

        # Áp dụng 16 quy tắc điều chỉnh đường và topping theo SOP quầy bar
        bar_rules = []
        if t_code != "0":
            if s_code == "4":
                bar_rules.append("⚠️ Quy tắc SOP: Khách chọn đường 100% kèm Topping thêm -> Giảm mức đường thực tế pha chế xuống 70% để tránh quá ngọt.")
            elif s_code in ["2", "3"]:
                bar_rules.append("💡 Quy tắc SOP: Khách chọn đường 50-70% kèm Topping thêm -> Giữ mức đường ổn định ở 50%.")
            elif s_code == "1":
                bar_rules.append("💡 Quy tắc SOP: Khách chọn đường 30% kèm Topping thêm -> Giữ nguyên mức 30%.")

        if p_code == "31":
            bar_rules.append("☕ Americano: Mặc định không đường; nếu khách yêu cầu thêm thì cho tiêu chuẩn 20g.")

        bar_rules.append("🧊 Uống ngon nhất trong vòng 2 giờ. Trân châu bảo quản nhiệt độ phòng tối đa 4 giờ.")

        return {
            "status": "SUCCESS",
            "type": "CUP_STICKER_DECODE",
            "code": clean_code,
            "product": drink_name,
            "product_code": p_code,
            "sugar": sugar_desc,
            "ice": ice_desc,
            "additional_topping": topping_desc,
            "standard_bar_rule": " | ".join(bar_rules),
            "rules_list": bar_rules,
            "evidence_ref": f"sticker_rules:{clean_code}"
        }

    def compute_topping_prep_plan(self, target_date: str | None = None, buffer_pct: float = 0.10) -> dict[str, Any]:
        """Tính toán kế hoạch nấu mẻ trân châu & topping cho ngày tới."""
        t_date = target_date or (date.today() + timedelta(days=1)).isoformat()
        prep_draft = self.opt_engine.generate_topping_prep_plan(target_date=t_date, buffer_pct=buffer_pct)
        validation_res = self.validator.validate_prep_plan(prep_draft)

        saved = save_plan({
            "plan_type": "PREP_TOPPING",
            "target_date": t_date,
            "status": "DRAFT",
            "requires_manager_approval": True,
            "created_by": "Tuyết Vương AI",
            "data": prep_draft,
            "validation": validation_res
        })

        return {
            "status": "SUCCESS",
            "target_date": t_date,
            "draft_plan_id": saved["plan_id"],
            "requires_manager_approval": True,
            "verification": validation_res,
            "prep_items": prep_draft.get("prep_items", []),
            "evidence_ref": f"plan_prep:{t_date}"
        }

    def compute_replenishment_po_plan(self, target_date: str | None = None, lead_time_days: int = 2) -> dict[str, Any]:
        """Tính toán đơn đặt hàng bổ sung nguyên liệu (PO) làm tròn theo kiện/thùng."""
        t_date = target_date or (date.today() + timedelta(days=1)).isoformat()
        po_draft = self.opt_engine.generate_replenishment_orders(target_date=t_date, lead_time_days=lead_time_days)
        validation_res = self.validator.validate_replenishment_orders(po_draft)

        saved = save_plan({
            "plan_type": "PURCHASE_ORDER",
            "target_date": t_date,
            "status": "DRAFT",
            "requires_manager_approval": True,
            "created_by": "Tuyết Vương AI",
            "data": po_draft,
            "validation": validation_res
        })

        return {
            "status": "SUCCESS",
            "target_date": t_date,
            "draft_plan_id": saved["plan_id"],
            "requires_manager_approval": True,
            "verification": validation_res,
            "po_items": po_draft.get("orders", []),
            "total_estimated_cost": po_draft.get("total_estimated_cost", 0),
            "evidence_ref": f"plan_po:{t_date}"
        }

    # Alias
    lookup_recipe_bom = get_recipe_details
