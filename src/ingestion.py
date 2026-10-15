# -*- coding: utf-8 -*-
"""Data ingestion pipeline: imports validated CSV files from DU_LIEU_CAN_NHAP into database."""
import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from sqlalchemy.orm import Session
from src.database import engine, Base, SessionLocal
from src.models import (
    MenuItem, Ingredient, RecipeBOM, SalesDaily, Purchase, StockCount, ToppingDaily
)
from scripts.tieng_viet import TEP, COT, chuan_hoa

ROOT = Path(__file__).resolve().parents[1]

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully.")

def import_all(folder_path=None):
    if folder_path is None:
        folder_path = ROOT / "DU_LIEU_CAN_NHAP"
    else:
        folder_path = Path(folder_path)

    init_db()
    db: Session = SessionLocal()

    try:
        # 1. Menu Items
        f_menu = folder_path / f"{TEP['menu_items']}.csv"
        if f_menu.exists():
            with f_menu.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                translated = {v: k for k, v in COT.items()}
                count = 0
                for row in reader:
                    r = {translated.get(k, k): chuan_hoa(translated.get(k, k), v.strip()) for k, v in row.items()}
                    sku_id = r["sku_id"]
                    obj = db.query(MenuItem).filter_by(sku_id=sku_id).first()
                    if not obj:
                        obj = MenuItem(sku_id=sku_id)
                        db.add(obj)
                    obj.sku_name = r["sku_name"]
                    obj.variant = r.get("variant") or None
                    obj.selling_price_vnd = Decimal(r["selling_price_vnd"]) if r.get("selling_price_vnd") else Decimal(0)
                    obj.effective_from = date.fromisoformat(r["effective_from"])
                    obj.effective_to = date.fromisoformat(r["effective_to"]) if r.get("effective_to") else None
                    obj.is_active = (r.get("is_active") == "true")
                    count += 1
                db.commit()
                print(f"Imported {count} menu items.")

        # 2. Ingredients
        f_ing = folder_path / f"{TEP['ingredients']}.csv"
        if f_ing.exists():
            with f_ing.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                translated = {v: k for k, v in COT.items()}
                count = 0
                for row in reader:
                    r = {translated.get(k, k): chuan_hoa(translated.get(k, k), v.strip()) for k, v in row.items()}
                    ing_id = r["ingredient_id"]
                    obj = db.query(Ingredient).filter_by(ingredient_id=ing_id).first()
                    if not obj:
                        obj = Ingredient(ingredient_id=ing_id)
                        db.add(obj)
                    obj.ingredient_name = r["ingredient_name"]
                    obj.base_unit = r["base_unit"]
                    obj.unit_cost_vnd = Decimal(r["unit_cost_vnd"]) if r.get("unit_cost_vnd") else None
                    obj.ingredient_group = r["ingredient_group"]
                    obj.shelf_life_rule_id = r.get("shelf_life_rule_id") or None
                    count += 1
                db.commit()
                print(f"Imported {count} ingredients.")

        # 3. Recipe BOM
        f_bom = folder_path / f"{TEP['recipe_bom']}.csv"
        if f_bom.exists():
            db.query(RecipeBOM).delete() # Refresh BOM lines cleanly
            with f_bom.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                translated = {v: k for k, v in COT.items()}
                count = 0
                for row in reader:
                    r = {translated.get(k, k): chuan_hoa(translated.get(k, k), v.strip()) for k, v in row.items()}
                    bom = RecipeBOM(
                        recipe_id=r["recipe_id"],
                        sku_id=r["sku_id"],
                        ingredient_id=r["ingredient_id"],
                        quantity_per_item=Decimal(r["quantity_per_item"]),
                        unit=r["unit"],
                        effective_from=date.fromisoformat(r["effective_from"]),
                        effective_to=date.fromisoformat(r["effective_to"]) if r.get("effective_to") else None,
                        is_optional=(r.get("is_optional") == "true")
                    )
                    db.add(bom)
                    count += 1
                db.commit()
                print(f"Imported {count} recipe BOM lines.")

        # 4. Sales Daily
        f_sales = folder_path / f"{TEP['sales_daily']}.csv"
        if f_sales.exists():
            db.query(SalesDaily).delete() # Clean reload
            with f_sales.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                translated = {v: k for k, v in COT.items()}
                count = 0
                for row in reader:
                    r = {translated.get(k, k): chuan_hoa(translated.get(k, k), v.strip()) for k, v in row.items()}
                    sales = SalesDaily(
                        business_date=date.fromisoformat(r["business_date"]),
                        store_id=r["store_id"],
                        sku_id=r["sku_id"],
                        quantity_sold=int(r["quantity_sold"]),
                        revenue_vnd=Decimal(r["revenue_vnd"]),
                        source_id=r.get("source_id"),
                        verification_status=r.get("verification_status", "verified")
                    )
                    db.add(sales)
                    count += 1
                db.commit()
                print(f"Imported {count} daily sales records.")

        # 5. Purchases
        f_purch = folder_path / f"{TEP['purchases']}.csv"
        if f_purch.exists():
            db.query(Purchase).delete()
            with f_purch.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                translated = {v: k for k, v in COT.items()}
                count = 0
                for row in reader:
                    r = {translated.get(k, k): chuan_hoa(translated.get(k, k), v.strip()) for k, v in row.items()}
                    purch = Purchase(
                        purchase_id=r["purchase_id"],
                        order_date=date.fromisoformat(r["order_date"]) if r.get("order_date") else None,
                        received_date=date.fromisoformat(r["received_date"]),
                        ingredient_id=r["ingredient_id"],
                        quantity_received=Decimal(r["quantity_received"]),
                        unit=r["unit"],
                        unit_cost_vnd=Decimal(r["unit_cost_vnd"]) if r.get("unit_cost_vnd") else None,
                        source_id=r.get("source_id")
                    )
                    db.add(purch)
                    count += 1
                db.commit()
                print(f"Imported {count} purchase lines.")

        # 6. Stock Counts
        f_stock = folder_path / f"{TEP['stock_counts']}.csv"
        if f_stock.exists():
            db.query(StockCount).delete()
            with f_stock.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                translated = {v: k for k, v in COT.items()}
                count = 0
                for row in reader:
                    r = {translated.get(k, k): chuan_hoa(translated.get(k, k), v.strip()) for k, v in row.items()}
                    stk = StockCount(
                        count_id=r["count_id"],
                        counted_at=datetime.fromisoformat(r["counted_at"]),
                        business_date=date.fromisoformat(r["business_date"]),
                        ingredient_id=r["ingredient_id"],
                        quantity_counted=Decimal(r["quantity_counted"]),
                        unit=r["unit"],
                        verified_by_role=r["verified_by_role"]
                    )
                    db.add(stk)
                    count += 1
                db.commit()
                print(f"Imported {count} stock count records.")

        # 7. Topping Daily
        f_top = folder_path / f"{TEP['topping_daily']}.csv"
        if f_top.exists():
            db.query(ToppingDaily).delete()
            with f_top.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                translated = {v: k for k, v in COT.items()}
                count = 0
                for row in reader:
                    r = {translated.get(k, k): chuan_hoa(translated.get(k, k), v.strip()) for k, v in row.items()}
                    top = ToppingDaily(
                        business_date=date.fromisoformat(r["business_date"]),
                        store_id=r["store_id"],
                        prepared_ingredient_id=r["prepared_ingredient_id"],
                        prepared_qty=Decimal(r["prepared_qty"]),
                        wasted_qty=Decimal(r["wasted_qty"]),
                        unit=r["unit"],
                        carry_in_qty=Decimal(r["carry_in_qty"]) if r.get("carry_in_qty") else Decimal(0),
                        carry_out_qty=Decimal(r["carry_out_qty"]) if r.get("carry_out_qty") else Decimal(0),
                        reason=r.get("reason"),
                        source_id=r.get("source_id")
                    )
                    db.add(top)
                    count += 1
                db.commit()
                print(f"Imported {count} topping preparation/waste records.")

        print("\nAll operational data ingested into Database successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    import_all()
