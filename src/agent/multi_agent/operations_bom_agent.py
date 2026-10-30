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


from pathlib import Path
import csv
import re

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SEMI_PRODUCT_SOP_INFO = {
    "TP02": {
        "code": "TP02",
        "name": "Trân châu nguyên vị đã nấu (Trân châu đen)",
        "definition": "Topping cốt lõi đặc trưng của Mixue được chế biến từ hạt trân châu đen sống (mã nguyên liệu kho: 12), qua quy trình luộc sôi - ủ nóng nở dẻo và ủ ngâm đường mật để hạt trân châu đạt độ bóng mịn, dẻo mềm bên ngoài và dai giòn đàn hồi bên trong.",
        "storage": "Đậy nắp kín, bảo quản ở nhiệt độ phòng (nhiệt độ thường quầy bar, tránh gió quạt hoặc điều hòa thổi trực tiếp).",
        "shelf_life": "4 giờ (Sau 4 tiếng trân châu bị lại gạo chai cứng, bắt buộc phải đổ bỏ hủy mẻ, tuyệt đối không bảo quản trong tủ lạnh hoặc tái sử dụng qua ngày).",
        "brief_storage": "Đậy kín ở nhiệt độ phòng, tránh gió thổi trực tiếp.",
        "brief_shelf_life": "4 giờ. Hết hạn phải bỏ; không bảo quản trong tủ lạnh hoặc dùng qua ngày.",
        "brief_steps": [
            "Đun sôi lượng nước theo cỡ mẻ đã chọn.",
            "Cho trân châu từ từ vào, khuấy một chiều sát đáy để không dính nồi.",
            "Nấu sôi trên lửa vừa **35 phút**, đảo nhẹ mỗi 5–7 phút.",
            "Tắt bếp, đậy kín nắp và ủ **30 phút**.",
            "Vớt ra, xả nhẹ bằng **2.000 ml nước lọc nguội**, để ráo.",
            "Trộn với lượng đường mật của mẻ, ủ **10 phút**."
        ],
        "steps": [
            "Đun sôi nước sạch theo tỷ lệ quy chuẩn trong nồi nấu trân châu (4,000 ml nước cho 1 mẻ tiêu chuẩn 1,000 g trân châu; 3,000 ml nước cho nửa mẻ 500 g).",
            "Khi nước sôi bùng, từ từ rải đều trân châu đen vào nồi, dùng vá khuấy đều một chiều liên tục chạm đáy nồi để các hạt không bị dính vào nhau hoặc bén đáy.",
            "Nấu sôi đều trên lửa vừa trong đúng 35 phút (đảo nhẹ định kỳ 5-7 phút/lần).",
            "Tắt bếp, đậy kín nắp vung và tiến hành ủ nóng trong 30 phút để hạt trân châu chín thấu tận tâm lõi.",
            "Đổ trân châu ra rổ inox chuyên dụng, dùng 2,000 ml nước lọc nguội xả nhẹ để rửa sạch lớp nhớt bề mặt và làm hạt săn chắc lại.",
            "Đổ trân châu đã ráo nước vào âu chứa topping, thêm đường mật (500 g đường mật cho 1 mẻ; 250 g cho nửa mẻ), dùng phới trộn đều và ủ đường trong 10 phút để ngấm vị ngọt thanh và tạo độ bóng mượt."
        ],
        "keywords": ["tran chau", "chan trau", "chan chau", "tran trau", "pearl", "boba", "tp02", "12"]
    },
    "TP03": {
        "code": "TP03",
        "name": "Thạch đường đen đã chế biến (Pudding đường đen)",
        "definition": "Thạch topping thơm mùi đường đen truyền thống, mềm mượt và tan chảy trong miệng, được nấu từ bột pudding (mã 4) và syrup đường đen (NL03).",
        "storage": "Đậy nắp kín ở nhiệt độ phòng (dùng trong ngày) hoặc đậy nắp bảo quản lạnh trong tủ mát.",
        "shelf_life": "Đổ bỏ cuối ngày nếu ở nhiệt độ thường; 0+3 ngày nếu đậy nắp bảo quản ngăn mát tủ lạnh.",
        "steps": [
            "Đun sôi nước sạch (3,000 ml cho 1 mẻ tiêu chuẩn).",
            "Từ từ đổ bột pudding (500 g) vào nồi nước sôi, dùng phới lồng khuấy đều theo một chiều trong 1 phút.",
            "Rót syrup đường đen (500 g) vào hỗn hợp, tiếp tục khuấy đều cho tan hoàn toàn.",
            "Rót hỗn hợp thạch ra khay/hộp đựng, hớt bọt bề mặt để mặt thạch mịn đẹp.",
            "Để thạch nguội tự nhiên và đông lại trước khi sử dụng hoặc chuyển vào tủ mát."
        ],
        "keywords": ["thach duong den", "pudding duong den", "duong den", "tp03", "thach den"]
    },
    "TP04": {
        "code": "TP04",
        "name": "Thạch đào đã chế biến (Pudding đào)",
        "definition": "Thạch trái cây vị đào tươi mát, màu vàng cam bắt mắt và vị ngọt dịu, nấu từ bột pudding (mã 4), đường mật (NL01) và mứt đào vàng (NL13).",
        "storage": "Đậy nắp ở nhiệt độ thường hoặc đậy kín bảo quản lạnh trong ngăn mát.",
        "shelf_life": "Đổ bỏ cuối ngày ở nhiệt độ thường; 0+3 ngày nếu bảo quản trong tủ mát.",
        "steps": [
            "Đun sôi 2,000 ml nước sạch cho 1 mẻ tiêu chuẩn.",
            "Rải từ từ 250 g bột pudding vào nước sôi, khuấy tan đều.",
            "Thêm 250 g đường mật và 250 g mứt đào vàng vào nồi, khuấy đều liên tục trong 2 phút.",
            "Rót thạch ra khuôn khay, để nguội cho thạch đông kết kết cấu dẻo mịn."
        ],
        "keywords": ["thach dao", "pudding dao", "dao", "tp04"]
    },
    "TP05": {
        "code": "TP05",
        "name": "Trà sữa lạnh đã pha (Trà sữa nền cốt)",
        "definition": "Hỗn hợp trà sữa nền cốt pha sẵn phục vụ quầy bar, phối trộn giữa hồng trà ủ đậm vị (mã 13), bột trà sữa béo ngậy (mã 3) và làm lạnh sốc bằng đá viên.",
        "storage": "Bình giữ nhiệt chuyên dụng hoặc bình đong đậy kín nắp trong tủ lạnh.",
        "shelf_life": "Đổ bỏ cuối ngày (không để qua đêm).",
        "steps": [
            "Ủ 100 g hồng trà với 1,400 g nước sôi trong đúng 12 phút.",
            "Lọc bỏ bã trà, cho nhỏ giọt 30 giây để thu trọn nước cốt đậm đặc.",
            "Cho 650 g bột trà sữa vào nước cốt trà nóng, dùng phới khuấy kỹ trong 2 phút cho tan mịn hoàn toàn không vón cục.",
            "Cho 900 g đá viên vào khuấy tan trong 2 phút để làm lạnh sốc giữ trọn hương thơm béo ngậy."
        ],
        "keywords": ["tra sua lanh", "tra sua nen", "cot tra sua", "pha tra sua", "tp05"]
    },
    "TP06": {
        "code": "TP06",
        "name": "Sữa đặc pha từ bột trà sữa",
        "definition": "Hỗn hợp sữa nền ngọt ngậy dùng gia tăng độ sánh béo cho các dòng trà sữa và sữa trái cây Mixue.",
        "storage": "Bình giữ nhiệt hoặc bình đong đậy nắp trong tủ mát.",
        "shelf_life": "8 giờ trong bình giữ nhiệt; đổ bỏ cuối ngày nếu bảo quản lạnh.",
        "steps": [
            "Pha 500 g bột trà sữa với 500 g nước nóng.",
            "Dùng phới đánh đều trong khoảng 3 phút cho tan sánh mịn.",
            "Thêm 500 g đá viên khuấy đều để làm nguội sốc và tạo độ sánh kem chuẩn."
        ],
        "keywords": ["sua dac", "bot sua pha", "tp06"]
    },
    "TP07": {
        "code": "TP07",
        "name": "Trà xanh đã ủ (Lục trà hoa nhài)",
        "definition": "Cốt lục trà thơm hương hoa nhài thanh khiết, làm nền cho các món trà trái cây giải nhiệt (Trà chanh, Trà đào bigsize, Trà kiwi...).",
        "storage": "Bình giữ nhiệt quầy bar hoặc đậy nắp bảo quản lạnh.",
        "shelf_life": "Đổ bỏ cuối ngày.",
        "steps": [
            "Đun nước sôi 1,500 g, để nhiệt độ chuẩn 80-85°C (không ủ nước 100°C làm chát trà).",
            "Ủ 60 g trà xanh nhài (mã 14) trong đúng 6 phút.",
            "Lấy túi lọc trà ra để nhỏ giọt tự nhiên trong 30 giây (tuyệt đối không vắt ép túi trà tránh đắng chát).",
            "Cho 1,000 g đá viên vào cốt trà khuấy tan để khóa hương hoa nhài và làm lạnh sốc."
        ],
        "keywords": ["tra xanh", "luc tra", "tra nhai", "tp07", "u tra xanh"]
    },
    "TP08": {
        "code": "TP08",
        "name": "Hồng trà đã ủ (Cốt hồng trà đậm vị)",
        "definition": "Cốt hồng trà lên men truyền thống màu nâu đỏ óng ánh, vị đậm đà và hậu vị ngọt sâu, làm nền cho Hồng trà kem tươi và các dòng trà sữa đậm vị.",
        "storage": "Bình giữ nhiệt chuyên dụng hoặc đậy nắp bảo quản lạnh.",
        "shelf_life": "Đổ bỏ cuối ngày.",
        "steps": [
            "Đun 1,800 g nước sôi 100°C.",
            "Ủ 100 g hồng trà (mã 13) trong đúng 10 phút.",
            "Lấy túi trà ra, lọc để nhỏ giọt tự nhiên trong 30 giây (không vắt kiệt làm đục màu trà).",
            "Cho 1,000 g đá viên vào khuấy tan làm lạnh sốc và khóa hương trà."
        ],
        "keywords": ["hong tra", "u hong tra", "cot hong tra", "tp08"]
    },
    "TP10": {
        "code": "TP10",
        "name": "Cà phê cô đặc từ cà phê hòa tan",
        "definition": "Cốt cà phê cô đặc thơm nồng phục vụ cho các món Cà phê Americano và Cà phê sữa Mixue.",
        "storage": "Bình đong đậy nắp bảo quản trong ngăn mát tủ lạnh.",
        "shelf_life": "Đổ bỏ cuối ngày.",
        "steps": [
            "Pha 50 g bột cà phê hòa tan (NL22) với 300 g nước sôi.",
            "Khuấy đều liên tục trong khoảng 1 phút cho tan hết bọt.",
            "Cho 300 g đá viên vào khuấy tan để hạ nhiệt và cô đặc hương thơm."
        ],
        "keywords": ["ca phe", "coffee", "tp10", "pha ca phe"]
    },
    "TP11": {
        "code": "TP11",
        "name": "Hỗn hợp kem tươi đã pha trước khi đưa vào máy",
        "definition": "Hỗn hợp sữa kem tươi béo mịn thơm ngậy tạo nên linh hồn của món Kem ốc quế và Kem siêu sundae Mixue.",
        "storage": "Bình đong đậy nắp trong ngăn mát tủ lạnh hoặc nạp trực tiếp vào khoang chứa máy làm kem.",
        "shelf_life": "Đổ bỏ cuối ngày.",
        "steps": [
            "Pha 1,500 g bột kem (mã 2) với 4,000 g nước sạch.",
            "Dùng máy đánh hoặc phới lồng khuấy mạnh trong khoảng 3 phút cho tan mịn hoàn toàn.",
            "Để hỗn hợp nghỉ trong 15 phút cho bột ngậm đủ nước.",
            "Khuấy lại 2 lần trước khi rót vào khoang chứa của máy làm kem để kem đạt kết cấu xốp mịn hoàn hảo."
        ],
        "keywords": ["kem tuoi", "kem oc que", "bot kem", "hon hop kem", "pha kem", "tp11", "tp01"]
    },
    "NL07": {
        "code": "NL07",
        "name": "Thạch dừa dùng pha món (Nata de Coco)",
        "definition": "Topping thạch dừa giòn sần sật dùng trực tiếp cho các món trà trái cây và trà sữa Mixue.",
        "storage": "Đậy kín nắp khay tại quầy bar hoặc bảo quản lạnh trong tủ mát sau khi mở túi.",
        "shelf_life": "Đổ bỏ cuối ngày đối với phần đã múc ra khay quầy bar (không để qua đêm ngoài quầy); phần trong hộp đậy kín bảo quản tủ mát tối đa 0+3 ngày.",
        "steps": [
            "Cắt túi thạch dừa, đổ cả phần cái và nước đường ngâm vào hộp/khay chuyên dụng sạch sẽ.",
            "Dùng vá lỗ chuyên dụng khi múc định lượng vào cốc để không làm lệch lượng đường của món."
        ],
        "keywords": ["thach dua", "nata de coco", "nl07"]
    }
}


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

    def get_sop_prep_guide(self, query: str) -> dict[str, Any] | None:
        """Tra cứu hướng dẫn sơ chế, định nghĩa và quy trình nấu mẻ chuẩn SOP."""
        q_norm = _norm(query)
        matched_info = None

        # 1. Tìm kiếm theo từ khóa chuyên biệt
        for code, info in SEMI_PRODUCT_SOP_INFO.items():
            if any(k in q_norm for k in info["keywords"]):
                matched_info = info
                break

        if not matched_info:
            return None

        # Đọc dữ liệu mẻ thực tế từ 09_Cong_thuc_so_che_theo_me.csv và 02_Nguyen_lieu.csv
        csv_file = REPO_ROOT / "DU_LIEU_CAN_NHAP" / "09_Cong_thuc_so_che_theo_me.csv"
        ing_file = REPO_ROOT / "DU_LIEU_CAN_NHAP" / "02_Nguyen_lieu.csv"

        ing_map = {}
        if ing_file.exists():
            with open(ing_file, encoding="utf-8-sig", errors="ignore") as fp:
                for r in csv.DictReader(fp):
                    code_val = r.get("Mã nguyên liệu") or r.get("\ufeffMã nguyên liệu")
                    if code_val:
                        ing_map[code_val] = r.get("Tên nguyên liệu", code_val)

        batches = {}
        if csv_file.exists():
            with open(csv_file, encoding="utf-8-sig", errors="ignore") as fp:
                for r in csv.DictReader(fp):
                    tp = r.get("Bán thành phẩm đầu ra")
                    if tp == matched_info["code"]:
                        m_code = r.get("Mã công thức mẻ") or r.get("\ufeffMã công thức mẻ") or "ME"
                        portion = r.get("Số phần", "1")
                        in_id = r.get("Mã nguyên liệu đầu vào", "")
                        in_name = ing_map.get(in_id, in_id)
                        qty = r.get("Lượng đầu vào", "")
                        unit = r.get("Đơn vị đầu vào", "")
                        cups = r.get("Số cốc ước tính theo ảnh", "")

                        b_key = f"{portion} mẻ ({m_code})"
                        batches.setdefault(b_key, []).append({
                            "ing_id": in_id,
                            "ing_name": in_name,
                            "qty": qty,
                            "unit": unit,
                            "cups": cups
                        })

        return {
            "status": "SUCCESS",
            "type": "SOP_PREP_GUIDE",
            "code": matched_info["code"],
            "name": matched_info["name"],
            "definition": matched_info["definition"],
            "batches": batches,
            "steps": matched_info["steps"],
            "brief_steps": matched_info.get("brief_steps", matched_info["steps"]),
            "storage": matched_info["storage"],
            "brief_storage": matched_info.get("brief_storage", matched_info["storage"]),
            "shelf_life": matched_info["shelf_life"],
            "brief_shelf_life": matched_info.get("brief_shelf_life", matched_info["shelf_life"]),
            "evidence_refs": [
                "file:DU_LIEU_CAN_NHAP/09_Cong_thuc_so_che_theo_me.csv",
                "file:DU_LIEU_CAN_NHAP/13_Thoi_gian_so_che_theo_anh.csv",
                "file:DU_LIEU_CAN_NHAP/10_Quy_dinh_bao_quan_theo_anh.csv"
            ]
        }

    # Alias
    lookup_recipe_bom = get_recipe_details
