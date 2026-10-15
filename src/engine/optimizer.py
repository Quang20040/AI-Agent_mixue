import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from sqlalchemy import func
from src.database import SessionLocal
from src.models import (
    MenuItem, Ingredient, RecipeBOM, SalesDaily, Purchase, StockCount, ToppingDaily
)

# Standard Batch Sizes for Prepared Toppings / Semi-finished Products
TOPPING_BATCH_CONFIG = {
    "TP02": {"name": "Hồng trà lạnh", "batch_size": 5000.0, "unit": "ml", "shelf_life": "4 giờ / Đổ bỏ cuối ngày"},
    "TP03": {"name": "Trà xanh lạnh", "batch_size": 5000.0, "unit": "ml", "shelf_life": "4 giờ / Đổ bỏ cuối ngày"},
    "TP04": {"name": "Trà sữa lạnh", "batch_size": 5000.0, "unit": "ml", "shelf_life": "Đổ bỏ cuối ngày"},
    "NL06": {"name": "Trân châu nguyên vị", "batch_size": 1000.0, "unit": "g", "shelf_life": "4 giờ"},
    "NL07": {"name": "Thạch dừa", "batch_size": 1000.0, "unit": "g", "shelf_life": "Đổ bỏ cuối ngày"},
    "NL08": {"name": "Thạch đường đen", "batch_size": 1000.0, "unit": "g", "shelf_life": "Đổ bỏ cuối ngày"},
}

# Standard Pack Sizes fallback
DEFAULT_PACK_SIZES = {
    "g": 1000.0,     # 1 kg
    "ml": 1000.0,    # 1 liter
    "cái": 500.0,    # 500 pcs
    "pcs": 500.0
}

# Quy cách đóng gói Thùng / Kiện nguyên số chuẩn chuỗi Mixue (Master Packaging SOP)
# Quy tắc nghiệp vụ nghiêm ngặt: Nhập hàng 100% theo số nguyên thùng / kiện (1, 2, 3... thùng), không nhập lẻ túi.
MIXUE_CARTON_SPECS = {
    "1": {"name": "Ốc quế", "carton_spec": "Thùng 400 cái (25 cái/dây, 16 dây/thùng)", "carton_size": 400.0, "carton_unit": "thùng", "base_unit": "pcs"},
    "2": {"name": "Bột kem", "carton_spec": "Thùng 24kg (3kg*8 túi)", "carton_size": 24000.0, "carton_unit": "thùng", "base_unit": "g"},
    "3": {"name": "Bột trà sữa", "carton_spec": "Thùng 20kg (2kg x 10 túi)", "carton_size": 20000.0, "carton_unit": "thùng", "base_unit": "g"},
    "4": {"name": "Bột pudding", "carton_spec": "Thùng 20kg (1kg*20 túi, thùng 20kg)", "carton_size": 20000.0, "carton_unit": "thùng", "base_unit": "g"},
    "6": {"name": "Cốc 700", "carton_spec": "Kiện 1.000 cái (1 dây 50c, 20 dây/kiện)", "carton_size": 1000.0, "carton_unit": "kiện", "base_unit": "pcs"},
    "7": {"name": "Cốc 500", "carton_spec": "Kiện 1.000 cái (1 dây 50c, 20 dây/kiện)", "carton_size": 1000.0, "carton_unit": "kiện", "base_unit": "pcs"},
    "8": {"name": "Cốc chữ U", "carton_spec": "Kiện 1.000 cái (1 dây 50c, 20 dây/kiện)", "carton_size": 1000.0, "carton_unit": "kiện", "base_unit": "pcs"},
    "9": {"name": "Đường quả (Syrup hoa quả)", "carton_spec": "Kiện 26kg (6.5kg/bình, 4 bình/kiện)", "carton_size": 26000.0, "carton_unit": "kiện", "base_unit": "g"},
    "10": {"name": "Đường mật (đường mía)", "carton_spec": "Kiện 26kg (6.5kg/bình, 4 bình/kiện)", "carton_size": 26000.0, "carton_unit": "kiện", "base_unit": "g"},
    "11": {"name": "Đường đen", "carton_spec": "Thùng 14.4kg (1,2kg*12 chai)", "carton_size": 14400.0, "carton_unit": "thùng", "base_unit": "g"},
    "12": {"name": "Trân châu đen", "carton_spec": "Thùng 16kg (1kg*16 túi, thùng 16kg)", "carton_size": 16000.0, "carton_unit": "thùng", "base_unit": "g"},
    "13": {"name": "Hồng trà", "carton_spec": "Thùng 8kg (50g*160 túi)", "carton_size": 8000.0, "carton_unit": "thùng", "base_unit": "g"},
    "14": {"name": "Trà xanh / trà hoa nhài", "carton_spec": "Thùng 8kg (50g*160 túi)", "carton_size": 8000.0, "carton_unit": "thùng", "base_unit": "g"},
    "15": {"name": "Syrup cam bưởi", "carton_spec": "Thùng 18kg (900g*20 hộp)", "carton_size": 18000.0, "carton_unit": "thùng", "base_unit": "g"},
    "16": {"name": "Mứt đào vàng", "carton_spec": "Thùng 18kg (900g*20 hộp)", "carton_size": 18000.0, "carton_unit": "thùng", "base_unit": "g"},
    "17": {"name": "Mứt trái đào", "carton_spec": "Thùng 18kg (900g*20 hộp)", "carton_size": 18000.0, "carton_unit": "thùng", "base_unit": "g"},
    "18": {"name": "Thạch lô hội", "carton_spec": "Thùng 18kg (1kg*18 túi)", "carton_size": 18000.0, "carton_unit": "thùng", "base_unit": "g"},
    "19": {"name": "Thạch dừa", "carton_spec": "Kiện 20kg (2kg/túi, 10 túi/kiện)", "carton_size": 20000.0, "carton_unit": "kiện", "base_unit": "g"},
    "20": {"name": "Thạch nguyên vị", "carton_spec": "Thùng 20kg (1kg/túi * 20 túi)", "carton_size": 20000.0, "carton_unit": "thùng", "base_unit": "g"},
    "21": {"name": "Syrup hạt dẻ", "carton_spec": "Thùng 14.4kg (1,2kg*12 chai)", "carton_size": 14400.0, "carton_unit": "thùng", "base_unit": "g"},
    "22": {"name": "Bột matcha", "carton_spec": "Thùng 3.6kg (300g*12 gói)", "carton_size": 3600.0, "carton_unit": "thùng", "base_unit": "g"},
    "23": {"name": "Syrup Xoài", "carton_spec": "Thùng 17kg (850gr*20lon, 17kg/thùng)", "carton_size": 17000.0, "carton_unit": "thùng", "base_unit": "g"},
    "24": {"name": "Syrup Dâu Tây", "carton_spec": "Thùng 18kg (900g*20 hộp)", "carton_size": 18000.0, "carton_unit": "thùng", "base_unit": "g"},
    "25": {"name": "Syrup Socola", "carton_spec": "Thùng 14.4kg (1,2kg*12 chai)", "carton_size": 14400.0, "carton_unit": "thùng", "base_unit": "g"},
    "26": {"name": "Syrup Việt Quất", "carton_spec": "Thùng 18kg (900gr*20 lon, 18kg/thùng)", "carton_size": 18000.0, "carton_unit": "thùng", "base_unit": "g"},
    "27": {"name": "Syrup chanh dây", "carton_spec": "Thùng 18kg (900gr*20 lon)", "carton_size": 18000.0, "carton_unit": "thùng", "base_unit": "g"},
    "28": {"name": "Bột Cafe rang", "carton_spec": "Thùng 7.6kg (380gr*20gói)", "carton_size": 7600.0, "carton_unit": "thùng", "base_unit": "g"},
    "29": {"name": "Vụn Oreo", "carton_spec": "Thùng 10kg (1kg*10 gói)", "carton_size": 10000.0, "carton_unit": "thùng", "base_unit": "g"},
    "30": {"name": "Chanh vàng", "carton_spec": "Kiện 15kg (15kg/kiện)", "carton_size": 15000.0, "carton_unit": "kiện", "base_unit": "g"},
    "31": {"name": "Cam vàng", "carton_spec": "Kiện 15kg", "carton_size": 15000.0, "carton_unit": "kiện", "base_unit": "g"},
    "32": {"name": "Ống hút bé", "carton_spec": "Kiện 5.000 cái (50 túi/kiện, 100c/túi)", "carton_size": 5000.0, "carton_unit": "kiện", "base_unit": "pcs"},
    "33": {"name": "Ống hút to", "carton_spec": "Kiện 5.000 cái (50 túi/kiện, 100c/túi)", "carton_size": 5000.0, "carton_unit": "kiện", "base_unit": "pcs"},
    "34": {"name": "Thìa sundea", "carton_spec": "Thùng 3.000 chiếc (60 túi*50 chiếc)", "carton_size": 3000.0, "carton_unit": "thùng", "base_unit": "pcs"},
    "35": {"name": "Giấy lót ốc quế", "carton_spec": "Thùng 10.000 cái/thùng", "carton_size": 10000.0, "carton_unit": "thùng", "base_unit": "pcs"},
    "36": {"name": "Giấy in hóa đơn", "carton_spec": "Thùng 50 cuộn/thùng", "carton_size": 50.0, "carton_unit": "thùng", "base_unit": "pcs"},
    "37": {"name": "Giấy in tem", "carton_spec": "Thùng 20 cuộn (800 tờ/cuộn)", "carton_size": 16000.0, "carton_unit": "thùng", "base_unit": "pcs"},
    "38": {"name": "Màng dập cốc", "carton_spec": "Cuộn chuẩn (3.000 ly/cuộn)", "carton_size": 3000.0, "carton_unit": "cuộn", "base_unit": "pcs"},
    "39": {"name": "Túi đơn T-shirt", "carton_spec": "Kiện 2.000 cái", "carton_size": 2000.0, "carton_unit": "kiện", "base_unit": "pcs"},
    "40": {"name": "Túi đựng cốc 2 ly", "carton_spec": "Thùng 8.000 cái/thùng", "carton_size": 8000.0, "carton_unit": "thùng", "base_unit": "pcs"},
    "41": {"name": "Túi đựng cốc 4 ly", "carton_spec": "Thùng 4.000 cái", "carton_size": 4000.0, "carton_unit": "thùng", "base_unit": "pcs"}
}

# Đồng bộ ánh xạ các mã nguyên liệu quầy bar (NL...) về đúng quy cách thùng/kiện chuẩn Mixue
MIXUE_CARTON_SPECS.update({
    "NL01": MIXUE_CARTON_SPECS["10"],  # Đường mật: Kiện 26kg (6.5kg*4 bình)
    "NL02": MIXUE_CARTON_SPECS["9"],   # Đường quả: Kiện 26kg (6.5kg*4 bình)
    "NL03": MIXUE_CARTON_SPECS["11"],  # Đường đen: Thùng 14.4kg (1.2kg*12 chai)
    "NL04": MIXUE_CARTON_SPECS["21"],  # Syrup hạt dẻ: Thùng 14.4kg (1.2kg*12 chai)
    "NL05": MIXUE_CARTON_SPECS["25"],  # Syrup socola: Thùng 14.4kg (1.2kg*12 chai)
    "NL06": MIXUE_CARTON_SPECS["12"],  # Trân châu đen: Thùng 16kg (1kg*16 túi)
    "NL07": MIXUE_CARTON_SPECS["19"],  # Thạch dừa: Kiện 20kg (2kg*10 túi)
    "NL08": MIXUE_CARTON_SPECS["18"],  # Thạch lô hội: Thùng 18kg (1kg*18 túi)
    "NL10": MIXUE_CARTON_SPECS["29"],  # Vụn Oreo: Thùng 10kg (1kg*10 gói)
    "NL11": MIXUE_CARTON_SPECS["23"],  # Mứt xoài: Thùng 17kg (850g*20 lon)
    "NL12": MIXUE_CARTON_SPECS["17"],  # Mứt trái đào: Thùng 18kg (900g*20 hộp)
    "NL13": MIXUE_CARTON_SPECS["16"],  # Mứt đào vàng: Thùng 18kg (900g*20 hộp)
    "NL14": MIXUE_CARTON_SPECS["24"],  # Mứt dâu tây: Thùng 18kg (900g*20 hộp)
    "NL15": MIXUE_CARTON_SPECS["27"],  # Mứt chanh leo: Thùng 18kg (900g*20 lon)
    "NL16": MIXUE_CARTON_SPECS["15"],  # Mứt cam bưởi: Thùng 18kg (900g*20 hộp)
    "NL22": MIXUE_CARTON_SPECS["28"]   # Bột cafe: Thùng 7.6kg (380g*20 gói)
})


class OptimizerEngine:
    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()

    def close(self):
        if self.db:
            self.db.close()

    def calculate_ingredient_demand(self, forecast_df: pd.DataFrame) -> pd.DataFrame:
        """Explodes forecasted SKU quantities into ingredient demand based on active BOMs."""
        if forecast_df.empty:
            return pd.DataFrame()

        # Query all active recipe BOMs
        boms = self.db.query(
            RecipeBOM.sku_id,
            RecipeBOM.ingredient_id,
            Ingredient.ingredient_name,
            Ingredient.ingredient_group,
            RecipeBOM.quantity_per_item,
            RecipeBOM.unit
        ).join(Ingredient, RecipeBOM.ingredient_id == Ingredient.ingredient_id).all()

        bom_df = pd.DataFrame(boms, columns=[
            "sku_id", "ingredient_id", "ingredient_name", "ingredient_group", "quantity_per_item", "unit"
        ])
        bom_df["quantity_per_item"] = bom_df["quantity_per_item"].astype(float)

        merged = pd.merge(forecast_df[["sku_id", "predicted_qty"]], bom_df, on="sku_id", how="inner")
        merged["theoretical_qty"] = merged["predicted_qty"] * merged["quantity_per_item"]

        # Aggregate by ingredient
        agg = merged.groupby(
            ["ingredient_id", "ingredient_name", "ingredient_group", "unit"],
            as_index=False
        ).agg({"theoretical_qty": "sum"})

        agg["theoretical_qty"] = agg["theoretical_qty"].round(2)
        return agg.sort_values(by="theoretical_qty", ascending=False)

    def optimize_topping_preparation(
        self,
        target_date: date,
        ingredient_demand_df: pd.DataFrame,
        buffer_pct: float = 0.10,
        usable_stock_map: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """Generates daily preparation batch recommendations for toppings.
        
        Formula:
            Target = Forecasted_Demand * (1 + Buffer) - Usable_Opening_Stock
            Batches = ceil( max(0, Target) / Batch_Size )
            Recommended_Qty = Batches * Batch_Size
        """
        usable_stock_map = usable_stock_map or {}
        prep_recommendations = []

        for ing_id, cfg in TOPPING_BATCH_CONFIG.items():
            # Find forecasted demand
            row = ingredient_demand_df[ingredient_demand_df["ingredient_id"] == ing_id]
            forecasted = float(row["theoretical_qty"].iloc[0]) if not row.empty else 0.0

            # SOP rule: perishable toppings cannot carry over overnight (shelf-life = 4h / end-of-day)
            usable_stock = usable_stock_map.get(ing_id, 0.0)

            # Target requirement with buffer
            buffered_demand = forecasted * (1.0 + buffer_pct)
            net_needed = max(0.0, buffered_demand - usable_stock)

            batch_size = cfg["batch_size"]
            num_batches = math.ceil(net_needed / batch_size) if net_needed > 0 else 0
            recommended_prep = num_batches * batch_size

            expected_waste = max(0.0, recommended_prep - forecasted)
            waste_ratio = (expected_waste / recommended_prep * 100) if recommended_prep > 0 else 0.0

            risk = "LOW"
            if waste_ratio > 30.0:
                risk = "HIGH"
            elif waste_ratio > 15.0:
                risk = "MEDIUM"

            prep_recommendations.append({
                "target_date": target_date.isoformat(),
                "ingredient_id": ing_id,
                "ingredient_name": cfg["name"],
                "unit": cfg["unit"],
                "batch_size": batch_size,
                "forecasted_demand": round(forecasted, 1),
                "buffer_pct": int(buffer_pct * 100),
                "usable_opening_stock": round(usable_stock, 1),
                "num_batches": num_batches,
                "recommended_prep_qty": recommended_prep,
                "expected_waste_qty": round(expected_waste, 1),
                "risk_level": risk,
                "shelf_life_rule": cfg["shelf_life"]
            })

        return prep_recommendations

    def optimize_replenishment(
        self,
        target_date: date,
        daily_demand_df: pd.DataFrame,
        lead_time_days: int = 2,
        review_period_days: int = 7,
        safety_factor: float = 1.3
    ) -> List[Dict[str, Any]]:
        """Generates replenishment purchase order drafts for raw ingredients and disposables.
        
        Formula:
            Cycle = LeadTime + ReviewPeriod
            CycleDemand = DailyDemand * Cycle
            SafetyStock = DailyDemand * LeadTime * (SafetyFactor - 1.0)
            TargetStock = CycleDemand + SafetyStock
            NetReq = max(0, TargetStock - OnHand)
            Packs = ceil(NetReq / PackSize)
            OrderQty = Packs * PackSize
        """
        # Exclude in-house preparations and store utilities (Nước, Đá, Bán thành phẩm, Trái cây đã sơ chế)
        in_house_groups = {'prepared_topping', 'Bán thành phẩm', 'Trái cây đã sơ chế', 'Nước', 'Đá'}
        prep_ids = set(TOPPING_BATCH_CONFIG.keys())
        raw_demand = daily_demand_df[
            (~daily_demand_df["ingredient_id"].isin(prep_ids)) &
            (~daily_demand_df["ingredient_group"].isin(in_house_groups))
        ]

        # Get latest stock counts as on-hand inventory
        latest_date = self.db.query(func.max(StockCount.business_date)).scalar()
        stk_rows = self.db.query(
            StockCount.ingredient_id,
            StockCount.quantity_counted,
            StockCount.unit
        ).filter(StockCount.business_date == latest_date).all()
        on_hand_map = {r[0]: float(r[1]) for r in stk_rows}

        cycle_days = lead_time_days + review_period_days
        po_lines = []

        for _, row in raw_demand.iterrows():
            ing_id = row["ingredient_id"]
            ing_name = row["ingredient_name"]
            group = row["ingredient_group"]
            unit = row["unit"]
            daily_req = float(row["theoretical_qty"])

            on_hand = on_hand_map.get(ing_id, 0.0)

            # Cycle projection
            cycle_demand = daily_req * cycle_days
            safety_stock = daily_req * lead_time_days * (safety_factor - 1.0)
            target_stock = cycle_demand + safety_stock

            net_req = max(0.0, target_stock - on_hand)

            # Tra cứu quy cách thùng / kiện chuẩn Mixue (nguyên số, không lẻ)
            spec = MIXUE_CARTON_SPECS.get(str(ing_id))
            if spec:
                pack_size = float(spec["carton_size"])
                carton_unit = spec["carton_unit"]
                carton_spec_str = spec["carton_spec"]
            else:
                pack_size = float(DEFAULT_PACK_SIZES.get(unit, 1000.0))
                carton_unit = "thùng"
                carton_spec_str = f"Quy cách chuẩn ({pack_size:,.0f} {unit}/thùng)"

            packs_to_order = math.ceil(net_req / pack_size) if net_req > 0 else 0
            order_qty = packs_to_order * pack_size
            display_order = f"{int(packs_to_order)} {carton_unit}" if packs_to_order > 0 else f"0 {carton_unit}"

            # Urgency / Priority assessment
            days_of_stock = (on_hand / daily_req) if daily_req > 0 else 999.0
            if days_of_stock < lead_time_days:
                priority = "CRITICAL"
                status = "CẦN ĐẶT GẤP (Nguy cơ hết hàng)"
            elif packs_to_order > 0:
                priority = "REORDER"
                status = "ĐỀ XUẤT NHẬP (Theo chu kỳ)"
            else:
                priority = "OK"
                status = "ĐỦ TỒN KHO"

            po_lines.append({
                "ingredient_id": ing_id,
                "ingredient_name": ing_name,
                "ingredient_group": group,
                "unit": unit,
                "daily_demand": round(daily_req, 1),
                "current_on_hand": round(on_hand, 1),
                "days_of_stock_remaining": round(days_of_stock, 1),
                "lead_time_days": lead_time_days,
                "pack_size": pack_size,
                "carton_unit": carton_unit,
                "carton_spec": carton_spec_str,
                "packs_to_order": int(packs_to_order),
                "display_order": display_order,
                "recommended_order_qty": order_qty,
                "priority": priority,
                "status": status
            })

        # Sort: CRITICAL first, then REORDER, then OK
        priority_order = {"CRITICAL": 0, "REORDER": 1, "OK": 2}
        po_lines.sort(key=lambda x: (priority_order.get(x["priority"], 3), -x["recommended_order_qty"]))
        return po_lines


if __name__ == "__main__":
    from src.engine.forecasting import ForecastingEngine
    fe = ForecastingEngine()
    fc = fe.forecast_demand(horizon_days=1, model="auto")
    fe.close()

    opt = OptimizerEngine()
    print("=== FORECASTED INGREDIENT DEMAND (TOP 10) ===")
    dem = opt.calculate_ingredient_demand(fc)
    print(dem.head(10).to_string(index=False))

    print("\n=== TOPPING PREPARATION RECOMMENDATIONS ===")
    preps = opt.optimize_topping_preparation(date(2026, 10, 13), dem)
    prep_df = pd.DataFrame(preps)
    print(prep_df[["ingredient_id", "ingredient_name", "forecasted_demand", "num_batches", "recommended_prep_qty", "risk_level"]].to_string(index=False))

    print("\n=== REPLENISHMENT ORDERS (CRITICAL & REORDER) ===")
    po = opt.optimize_replenishment(date(2026, 10, 13), dem)
    po_df = pd.DataFrame(po)
    print(po_df[po_df["priority"] != "OK"].head(10).to_string(index=False))
    opt.close()
