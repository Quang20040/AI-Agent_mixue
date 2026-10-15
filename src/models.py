"""SQLAlchemy ORM models for BeverageOps AI."""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from src.database import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    sku_id = Column(String(50), primary_key=True)
    sku_name = Column(String(200), nullable=False)
    variant = Column(String(50), nullable=True)
    selling_price_vnd = Column(Numeric(12, 0), nullable=False)
    effective_from = Column(Date, nullable=False, default=date(2023, 10, 1))
    effective_to = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    recipes = relationship("RecipeBOM", back_populates="menu_item")
    sales = relationship("SalesDaily", back_populates="menu_item")

class Ingredient(Base):
    __tablename__ = "ingredients"

    ingredient_id = Column(String(50), primary_key=True)
    ingredient_name = Column(String(200), nullable=False)
    base_unit = Column(String(20), nullable=False)  # 'g', 'ml', 'pcs'
    unit_cost_vnd = Column(Numeric(12, 2), nullable=True)
    ingredient_group = Column(String(50), nullable=False)  # dry, syrup, prepared_topping, packaging
    shelf_life_rule_id = Column(String(50), nullable=True)

    bom_lines = relationship("RecipeBOM", back_populates="ingredient")
    purchases = relationship("Purchase", back_populates="ingredient")
    stock_counts = relationship("StockCount", back_populates="ingredient")

class RecipeBOM(Base):
    __tablename__ = "recipe_bom"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(String(100), nullable=False)
    sku_id = Column(String(50), ForeignKey("menu_items.sku_id"), nullable=False)
    ingredient_id = Column(String(50), ForeignKey("ingredients.ingredient_id"), nullable=False)
    quantity_per_item = Column(Numeric(10, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    is_optional = Column(Boolean, nullable=False, default=False)

    menu_item = relationship("MenuItem", back_populates="recipes")
    ingredient = relationship("Ingredient", back_populates="bom_lines")

    __table_args__ = (
        Index("idx_recipe_sku_ing", "sku_id", "ingredient_id"),
    )

class SalesDaily(Base):
    __tablename__ = "sales_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_date = Column(Date, nullable=False)
    store_id = Column(String(50), nullable=False)
    sku_id = Column(String(50), ForeignKey("menu_items.sku_id"), nullable=False)
    quantity_sold = Column(Integer, nullable=False)
    revenue_vnd = Column(Numeric(14, 0), nullable=False)
    source_id = Column(String(100), nullable=True)
    verification_status = Column(String(20), nullable=False, default="verified")

    menu_item = relationship("MenuItem", back_populates="sales")

    __table_args__ = (
        Index("idx_sales_store_date_sku", "store_id", "business_date", "sku_id", unique=True),
    )

class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_id = Column(String(50), nullable=False)
    order_date = Column(Date, nullable=True)
    received_date = Column(Date, nullable=False)
    ingredient_id = Column(String(50), ForeignKey("ingredients.ingredient_id"), nullable=False)
    quantity_received = Column(Numeric(12, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    unit_cost_vnd = Column(Numeric(12, 2), nullable=True)
    source_id = Column(String(100), nullable=True)

    ingredient = relationship("Ingredient", back_populates="purchases")

    __table_args__ = (
        Index("idx_purchases_po_ing", "purchase_id", "ingredient_id", unique=True),
    )

class StockCount(Base):
    __tablename__ = "stock_counts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    count_id = Column(String(50), nullable=False)
    counted_at = Column(DateTime, nullable=False)
    business_date = Column(Date, nullable=False)
    ingredient_id = Column(String(50), ForeignKey("ingredients.ingredient_id"), nullable=False)
    quantity_counted = Column(Numeric(12, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    verified_by_role = Column(String(50), nullable=False)

    ingredient = relationship("Ingredient", back_populates="stock_counts")

    __table_args__ = (
        Index("idx_stock_count_ing", "count_id", "ingredient_id", unique=True),
    )

class ToppingDaily(Base):
    __tablename__ = "topping_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_date = Column(Date, nullable=False)
    store_id = Column(String(50), nullable=False)
    prepared_ingredient_id = Column(String(50), ForeignKey("ingredients.ingredient_id"), nullable=False)
    prepared_qty = Column(Numeric(12, 2), nullable=False)
    wasted_qty = Column(Numeric(12, 2), nullable=False)
    unit = Column(String(20), nullable=False)
    carry_in_qty = Column(Numeric(12, 2), nullable=False, default=0)
    carry_out_qty = Column(Numeric(12, 2), nullable=False, default=0)
    reason = Column(String(200), nullable=True)
    source_id = Column(String(100), nullable=True)

    __table_args__ = (
        Index("idx_topping_store_date_ing", "store_id", "business_date", "prepared_ingredient_id", unique=True),
    )


class User(Base):
    """Bảng người dùng và tài khoản nhân viên hệ thống BeverageOps AI."""
    __tablename__ = "users"

    username = Column(String(50), primary_key=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(String(30), nullable=False, default="STAFF_OFFICIAL")  # ADMIN, STAFF_OFFICIAL, STAFF_PROBATION
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class DailyStockMovement(Base):
    """Bảng lưu nhật ký xuất - nhập - tồn kho hàng ngày theo quy cách đóng gói (thùng/kiện/dây)."""
    __tablename__ = "daily_stock_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_date = Column(Date, nullable=False)
    ingredient_id = Column(String(50), ForeignKey("ingredients.ingredient_id"), nullable=False)
    movement_type = Column(String(20), nullable=False)  # 'INITIAL', 'IN', 'OUT', 'ACTUAL_COUNT'
    quantity = Column(Numeric(10, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="APPROVED")  # 'APPROVED', 'PENDING', 'REJECTED'
    recorded_by = Column(String(50), nullable=False, default="system")
    approved_by = Column(String(50), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(200), nullable=True)
    notes = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        Index("idx_daily_stock_date_ing_type", "business_date", "ingredient_id", "movement_type"),
        Index("idx_daily_stock_status", "status"),
    )




