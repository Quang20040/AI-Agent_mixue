"""SQLAlchemy ORM models for BeverageOps AI."""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    JSON,
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


class LoginThrottle(Base):
    __tablename__ = 'login_throttles'

    username = Column(String(50), primary_key=True)
    failed_attempts = Column(Integer, nullable=False, default=0)
    blocked_until = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=False, default=datetime.utcnow)


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






class OperationPlan(Base):
    """Durable plan snapshot including all lines and approval audit information."""
    __tablename__ = "operation_plans"

    plan_id = Column(String(50), primary_key=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class ShiftReportRecord(Base):
    """Bảng lưu trữ báo cáo chốt ca trong CSDL quan hệ (đồng bộ ACID cùng shift_reports.json)."""
    __tablename__ = "shift_reports"

    report_id = Column(String(100), primary_key=True)
    business_date = Column(String(20), nullable=False)
    shift_code = Column(String(30), nullable=False)
    cash_vnd = Column(Numeric(14, 0), nullable=False, default=0)
    bank_transfer_vnd = Column(Numeric(14, 0), nullable=False, default=0)
    total_collected_vnd = Column(Numeric(14, 0), nullable=False, default=0)
    status = Column(String(30), nullable=False, default="APPROVED")
    signed_by = Column(String(100), nullable=True)
    payload = Column(JSON, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_shift_reports_date_code", "business_date", "shift_code"),
    )


class StaffShiftPreference(Base):
    """Ca chính của từng nhân viên (CA_SANG / CA_CHIEU / CA_TOI) — AI ưu tiên xếp vào ca này."""
    __tablename__ = "staff_shift_preferences"

    username = Column(String(50), primary_key=True)
    main_shift = Column(String(20), nullable=True)
    note = Column(String(200), nullable=True)
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class StaffUnavailability(Base):
    """Một ngày / một ca nhân viên báo bận — AI không xếp người đó vào ca này."""
    __tablename__ = "staff_unavailability"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False)
    work_date = Column(Date, nullable=False)
    shift_code = Column(String(20), nullable=True)   # None = bận cả ngày
    reason = Column(String(200), nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (Index("idx_staff_unavail_date", "work_date", "username"),)


class ScheduleResponse(Base):
    """Nhân viên đã trả lời đợt hỏi lịch bận của một tuần chưa (báo bận hoặc xác nhận không bận)."""
    __tablename__ = "schedule_responses"

    username = Column(String(50), primary_key=True)
    week_start = Column(Date, primary_key=True)
    status = Column(String(20), nullable=False)          # NO_BUSY | BUSY_REPORTED
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class AttendanceNetwork(Base):
    """Địa chỉ mạng (IP công cộng của WiFi quán) được phép chấm công."""
    __tablename__ = "attendance_networks"

    ip = Column(String(64), primary_key=True)
    label = Column(String(100), nullable=True)
    added_by = Column(String(100), nullable=True)
    added_at = Column(DateTime, nullable=False, default=datetime.now)


class FaceProfile(Base):
    """Ảnh khuôn mặt mẫu của nhân viên (nhân viên đồng ý, Quản lý duyệt) để AI so khi chấm công."""
    __tablename__ = "face_profiles"

    username = Column(String(50), primary_key=True)
    photo_path = Column(String(300), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")   # PENDING | APPROVED | REJECTED
    consent_at = Column(DateTime, nullable=False, default=datetime.now)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)


class AttendanceRecord(Base):
    """Một lần check-in / check-out: thời điểm, mạng, kết quả so khuôn mặt, đúng giờ / muộn / về sớm, duyệt."""
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False)
    work_date = Column(Date, nullable=False)
    kind = Column(String(4), nullable=False)                  # IN | OUT
    at = Column(DateTime, nullable=False)
    shift_codes = Column(String(40), nullable=True)           # "CA_SANG,CA_CHIEU" or None (ngoài lịch)
    ip = Column(String(64), nullable=True)
    photo_path = Column(String(300), nullable=True)
    face_result = Column(String(20), nullable=False)          # MATCH | NO_MATCH | UNSURE | NO_FACE | SPOOF | UNAVAILABLE
    face_confidence = Column(Numeric(4, 2), nullable=True)
    face_reason = Column(String(300), nullable=True)
    timing = Column(String(20), nullable=False)               # ON_TIME | LATE | OK | EARLY | OFF_SCHEDULE
    minutes = Column(Integer, nullable=False, default=0)      # phút muộn / về sớm
    status = Column(String(20), nullable=False)               # AUTO_OK | NEEDS_REVIEW | APPROVED | REJECTED
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("idx_attendance_day", "work_date", "username"),)
