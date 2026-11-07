import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pandas as pd
from sqlalchemy import func, or_
from src.runtime_settings import resolve_store_id

from src.database import SessionLocal
from src.models import (
    Ingredient,
    MenuItem,
    Purchase,
    RecipeBOM,
    SalesDaily,
    StockCount,
    ToppingDaily,
)


class BOMEngine:
    def __init__(self, db_session=None, *, store_id=None):
        self.db = db_session or SessionLocal()
        self.store_id = store_id

    def close(self):
        if self.db:
            self.db.close()

    def get_sales_summary(self, start_date=None, end_date=None):
        """Aggregate sales revenue, quantity, and top SKUs."""
        query = self.db.query(
            SalesDaily.business_date,
            SalesDaily.sku_id,
            MenuItem.sku_name,
            MenuItem.variant,
            SalesDaily.quantity_sold,
            SalesDaily.revenue_vnd
        ).join(MenuItem, SalesDaily.sku_id == MenuItem.sku_id)
        query = query.filter(SalesDaily.store_id == resolve_store_id(self.db, self.store_id))

        if start_date:
            query = query.filter(SalesDaily.business_date >= start_date)
        if end_date:
            query = query.filter(SalesDaily.business_date <= end_date)

        rows = query.all()
        df = pd.DataFrame(rows, columns=[
            "business_date", "sku_id", "sku_name", "variant", "quantity_sold", "revenue_vnd"
        ])
        if df.empty:
            return df
        df["revenue_vnd"] = df["revenue_vnd"].astype(float)
        df["quantity_sold"] = df["quantity_sold"].astype(int)
        return df

    def calculate_theoretical_consumption(self, start_date=None, end_date=None):
        """BOM Explosion: Explode daily sales into theoretical ingredient usage."""
        query = self.db.query(
            SalesDaily.business_date,
            SalesDaily.sku_id,
            MenuItem.sku_name,
            SalesDaily.quantity_sold,
            RecipeBOM.ingredient_id,
            Ingredient.ingredient_name,
            Ingredient.ingredient_group,
            RecipeBOM.quantity_per_item,
            RecipeBOM.unit
        ).join(MenuItem, SalesDaily.sku_id == MenuItem.sku_id)\
         .join(RecipeBOM, SalesDaily.sku_id == RecipeBOM.sku_id)\
         .join(Ingredient, RecipeBOM.ingredient_id == Ingredient.ingredient_id)
        query = query.filter(
            SalesDaily.store_id == resolve_store_id(self.db, self.store_id),
            RecipeBOM.effective_from <= SalesDaily.business_date,
            or_(RecipeBOM.effective_to.is_(None), RecipeBOM.effective_to >= SalesDaily.business_date),
            RecipeBOM.is_optional.is_(False))

        if start_date:
            query = query.filter(SalesDaily.business_date >= start_date)
        if end_date:
            query = query.filter(SalesDaily.business_date <= end_date)

        rows = query.all()
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            "business_date", "sku_id", "sku_name", "quantity_sold",
            "ingredient_id", "ingredient_name", "ingredient_group",
            "quantity_per_item", "unit"
        ])
        if df.duplicated(['business_date', 'sku_id', 'ingredient_id']).any():
            raise ValueError('Có công thức chồng lấn hiệu lực; cần xác minh BOM trước khi tính nhu cầu.')
        df["quantity_sold"] = df["quantity_sold"].astype(float)
        df["quantity_per_item"] = df["quantity_per_item"].astype(float)
        df["theoretical_usage"] = df["quantity_sold"] * df["quantity_per_item"]

        # Aggregate by ingredient
        agg = df.groupby(["ingredient_id", "ingredient_name", "ingredient_group", "unit"], as_index=False).agg({
            "theoretical_usage": "sum"
        })
        agg["theoretical_usage"] = agg["theoretical_usage"].round(2)
        agg = agg.sort_values(by="theoretical_usage", ascending=False)
        return agg

    def get_topping_waste_summary(self, start_date=None, end_date=None):
        """Analyze prepared vs wasted quantities for toppings."""
        query = self.db.query(
            ToppingDaily.prepared_ingredient_id,
            Ingredient.ingredient_name,
            func.sum(ToppingDaily.prepared_qty).label("total_prepared"),
            func.sum(ToppingDaily.wasted_qty).label("total_wasted"),
            ToppingDaily.unit
        ).join(Ingredient, ToppingDaily.prepared_ingredient_id == Ingredient.ingredient_id)
        query = query.filter(ToppingDaily.store_id == resolve_store_id(self.db, self.store_id))

        if start_date:
            query = query.filter(ToppingDaily.business_date >= start_date)
        if end_date:
            query = query.filter(ToppingDaily.business_date <= end_date)

        query = query.group_by(ToppingDaily.prepared_ingredient_id, Ingredient.ingredient_name, ToppingDaily.unit)
        rows = query.all()
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            "prepared_ingredient_id", "ingredient_name", "total_prepared", "total_wasted", "unit"
        ])
        df["total_prepared"] = df["total_prepared"].astype(float)
        df["total_wasted"] = df["total_wasted"].astype(float)
        df["total_used"] = df["total_prepared"] - df["total_wasted"]
        df["waste_rate_pct"] = ((df["total_wasted"] / df["total_prepared"]) * 100).round(2)
        df = df.sort_values(by="waste_rate_pct", ascending=False)
        return df

    def calculate_inventory_reconciliation(self):
        """Variance analysis comparing theoretical usage, purchases, waste, and stock counts."""
        # 1. Total purchases received per ingredient
        purch_query = self.db.query(
            Purchase.ingredient_id,
            func.sum(Purchase.quantity_received).label("total_purchased"),
            Purchase.unit
        ).group_by(Purchase.ingredient_id, Purchase.unit)
        purch_df = pd.DataFrame(purch_query.all(), columns=["ingredient_id", "total_purchased", "unit"])
        if not purch_df.empty:
            purch_df["total_purchased"] = purch_df["total_purchased"].astype(float)

        # 2. Latest stock count per ingredient
        latest_count_date = self.db.query(func.max(StockCount.business_date)).scalar()
        stk_query = self.db.query(
            StockCount.ingredient_id,
            StockCount.quantity_counted.label("actual_stock_count"),
            StockCount.unit
        ).filter(StockCount.business_date == latest_count_date)
        stk_df = pd.DataFrame(stk_query.all(), columns=["ingredient_id", "actual_stock_count", "unit"])
        if not stk_df.empty:
            stk_df["actual_stock_count"] = stk_df["actual_stock_count"].astype(float)

        # 3. Initial (earliest) stock count per ingredient as opening balance
        earliest_count_date = self.db.query(func.min(StockCount.business_date)).scalar()
        if earliest_count_date and earliest_count_date < latest_count_date:
            init_stk_query = self.db.query(
                StockCount.ingredient_id,
                StockCount.quantity_counted.label("initial_stock"),
                StockCount.unit
            ).filter(StockCount.business_date == earliest_count_date)
            init_stk_df = pd.DataFrame(init_stk_query.all(), columns=["ingredient_id", "initial_stock", "unit"])
            if not init_stk_df.empty:
                init_stk_df["initial_stock"] = init_stk_df["initial_stock"].astype(float)
        else:
            init_stk_df = pd.DataFrame(columns=["ingredient_id", "initial_stock", "unit"])

        # 4. Theoretical consumption
        cons_df = self.calculate_theoretical_consumption()

        # Merge for reconciliation
        merged = pd.merge(stk_df, purch_df, on=["ingredient_id", "unit"], how="left")
        if not init_stk_df.empty:
            merged = pd.merge(merged, init_stk_df, on=["ingredient_id", "unit"], how="left")
        else:
            merged["initial_stock"] = 0.0
        merged = pd.merge(merged, cons_df[["ingredient_id", "ingredient_name", "theoretical_usage"]], on="ingredient_id", how="left")
        merged = merged.fillna(0)

        # Formula: Expected = Initial Stock + Total Purchases - Theoretical Usage
        merged["expected_stock"] = (merged["initial_stock"] + merged["total_purchased"] - merged["theoretical_usage"]).round(2)
        merged["variance"] = (merged["actual_stock_count"] - merged["expected_stock"]).round(2)
        
        # Calculate sensible denominator: initial_stock + total_purchased
        base_denom = merged["initial_stock"] + merged["total_purchased"]
        base_denom = base_denom.replace(0, float("nan"))
        base_denom = base_denom.fillna(merged["theoretical_usage"].replace(0, float("nan")))
        base_denom = base_denom.fillna(merged["actual_stock_count"].replace(0, 1.0))
        merged["variance_pct"] = ((merged["variance"] / base_denom) * 100).round(2).fillna(0.0)

        return merged

if __name__ == "__main__":
    engine = BOMEngine()
    print("=== THEORETICAL CONSUMPTION (TOP 10) ===")
    cons = engine.calculate_theoretical_consumption()
    print(cons.head(10).to_string(index=False))

    print("\n=== TOPPING WASTE SUMMARY ===")
    waste = engine.get_topping_waste_summary()
    print(waste.to_string(index=False))

    print("\n=== INVENTORY RECONCILIATION ===")
    recon = engine.calculate_inventory_reconciliation()
    print(recon.head(10).to_string(index=False))
    engine.close()
