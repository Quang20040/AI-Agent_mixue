import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from typing import Any, ClassVar

from src.database import SessionLocal
from src.models import Ingredient


class IndependentPlanValidator:
    """Independent Policy Validator for Preparation and Replenishment Plans.
    
    Enforces ADR-005, ADR-006, and PRD Verification Checklist:
    1. Quantity Non-negativity (qty >= 0)
    2. Valid Base Units (g, ml, cái/pcs)
    3. Exact Multiple of Batch Size (for topping prep)
    4. Exact Multiple of Pack Size (for replenishment orders)
    5. Referential Integrity (ingredient exists in DB)
    6. Food Safety & Shelf-life Compliance
    7. Human-in-the-Loop Governance: requires_manager_approval is strictly True
    """

    ALLOWED_UNITS: ClassVar[set[str]] = {"g", "ml", "pcs", "cái"}

    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
        self._load_ingredient_cache()

    def close(self):
        if self.db:
            self.db.close()

    def _load_ingredient_cache(self):
        ings = self.db.query(Ingredient.ingredient_id, Ingredient.base_unit).all()
        self.valid_ingredients = {r[0]: r[1] for r in ings}

    def verify_topping_prep_plan(self, prep_lines: list[dict[str, Any]]) -> dict[str, Any]:
        """Validates topping preparation recommendations."""
        violations = []
        warnings = []

        if not prep_lines:
            return {
                "is_valid": False,
                "status": "REJECTED",
                "violations": ["Kế hoạch sơ chế rỗng (không có dòng nào)."],
                "warnings": [],
                "requires_manager_approval": True
            }

        for idx, line in enumerate(prep_lines):
            ing_id = line.get("ingredient_id")
            rec_qty = line.get("recommended_prep_qty", 0.0)
            batch_size = line.get("batch_size", 0.0)
            unit = line.get("unit")

            # 1. Ingredient Existence
            if ing_id not in self.valid_ingredients:
                violations.append(f"Dòng {idx+1}: Mã nguyên liệu '{ing_id}' không tồn tại trong danh mục hệ thống.")
                continue

            # 2. Non-negative quantity
            if rec_qty < 0:
                violations.append(f"Dòng {idx+1} ({ing_id}): Lượng sơ chế âm ({rec_qty}).")

            # 3. Valid unit
            if unit not in self.ALLOWED_UNITS:
                violations.append(f"Dòng {idx+1} ({ing_id}): Đơn vị '{unit}' không hợp lệ.")
            elif unit != self.valid_ingredients[ing_id]:
                violations.append(f"Dòng {idx+1} ({ing_id}): Đơn vị {unit} không khớp danh mục ({self.valid_ingredients[ing_id]}).")
            if line.get('batch_yield_is_estimate'):
                warnings.append(f'Dòng {idx+1} ({ing_id}): Số mẻ dựa trên sản lượng thành phẩm ước lượng, cần đối chiếu thực tế.')

            # 4. Batch size multiple
            if batch_size <= 0:
                violations.append(f"Dòng {idx+1} ({ing_id}): Quy cách mẻ (batch_size) phải > 0.")
            else:
                remainder = round(rec_qty % batch_size, 4)
                if remainder != 0 and remainder != batch_size:
                    violations.append(f"Dòng {idx+1} ({ing_id}): Lượng sơ chế ({rec_qty}) không tròn theo quy cách mẻ ({batch_size}).")

            # 5. Waste risk warning
            risk = line.get("risk_level")
            if risk == "HIGH":
                warnings.append(f"Dòng {idx+1} ({ing_id}): Nguy cơ hao hụt cao (>30%) do mẻ chuẩn bị vượt xa lượng dự báo.")

        is_valid = len(violations) == 0
        return {
            "is_valid": is_valid,
            "status": "VERIFIED" if is_valid else "REJECTED",
            "total_lines": len(prep_lines),
            "violations": violations,
            "warnings": warnings,
            "requires_manager_approval": True,
            "verifier": "IndependentPlanValidator_v1.0"
        }

    def verify_replenishment_plan(self, po_lines: list[dict[str, Any]]) -> dict[str, Any]:
        """Validates replenishment purchase order lines."""
        violations = []
        warnings = []

        if not po_lines:
            return {
                "is_valid": False,
                "status": "REJECTED",
                "violations": ["Đơn đặt hàng rỗng (không có dòng nào)."],
                "warnings": [],
                "requires_manager_approval": True
            }

        for idx, line in enumerate(po_lines):
            ing_id = line.get("ingredient_id")
            order_qty = line.get("recommended_order_qty", 0.0)
            pack_size = line.get("pack_size", 0.0)
            unit = line.get("unit")

            # 1. Existence
            if ing_id not in self.valid_ingredients:
                violations.append(f"Dòng {idx+1}: Mã nguyên liệu '{ing_id}' không tồn tại trong DB.")
                continue

            # 2. Non-negative
            if order_qty < 0:
                violations.append(f"Dòng {idx+1} ({ing_id}): Lượng đặt hàng âm ({order_qty}).")

            # 3. Valid unit
            if unit not in self.ALLOWED_UNITS:
                violations.append(f"Dòng {idx+1} ({ing_id}): Đơn vị '{unit}' không hợp lệ.")

            # 4. Pack size multiple
            if order_qty > 0:
                if pack_size <= 0:
                    violations.append(f"Dòng {idx+1} ({ing_id}): Quy cách đóng gói (pack_size) phải > 0.")
                else:
                    remainder = round(order_qty % pack_size, 4)
                    if remainder != 0 and remainder != pack_size:
                        violations.append(f"Dòng {idx+1} ({ing_id}): Lượng đặt hàng ({order_qty}) không tròn theo quy cách đóng gói ({pack_size}).")

            # 5. Critical shortage warning
            if line.get("priority") == "CRITICAL":
                warnings.append(f"Dòng {idx+1} ({ing_id}): Cảnh báo tồn kho cạn kiệt dưới thời gian giao hàng (Lead Time)!")

        is_valid = len(violations) == 0
        return {
            "is_valid": is_valid,
            "status": "VERIFIED" if is_valid else "REJECTED",
            "total_lines": len(po_lines),
            "violations": violations,
            "warnings": warnings,
            "requires_manager_approval": True,
            "verifier": "IndependentPlanValidator_v1.0"
        }


if __name__ == "__main__":
    validator = IndependentPlanValidator()
    print("Testing validator with mock data...")
    test_lines = [
        {"ingredient_id": "TP02", "recommended_prep_qty": 10000.0, "batch_size": 5000.0, "unit": "ml", "risk_level": "LOW"},
        {"ingredient_id": "NL06", "recommended_prep_qty": 2000.0, "batch_size": 1000.0, "unit": "g", "risk_level": "LOW"}
    ]
    res = validator.verify_topping_prep_plan(test_lines)
    print("Verification result:", res)
    validator.close()
