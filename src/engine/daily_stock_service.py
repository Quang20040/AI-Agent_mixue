"""Dịch vụ Quản lý Sổ Xuất - Nhập - Tồn Kho Hàng Ngày (Mixue Daily Stock Matrix - 31 Ngày).

Sổ kho theo tháng (đủ số ngày thực của tháng), theo mẫu Google Sheets của quán Mixue 39 Tôn Quang Phiệt.
Tích hợp quy trình phê duyệt lệnh kho (Maker-Checker):
- Nhân viên chính thức: Tạo yêu cầu lệnh xuất/nhập -> Trạng thái PENDING_APPROVAL.
- Quản lý / Chủ quán: Kiểm duyệt và phê duyệt -> Ghi nhận vào file/sổ kho và ma trận.
"""

import io
import calendar
import math
from pathlib import Path
from functools import wraps
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from src.auth import is_admin_role, normalize_role
from src.database import Base, SessionLocal, engine
from src.models import DailyStockMovement, Ingredient, User
from src.runtime_settings import demo_enabled
from src.engine.storage_lock import FileTransactionLock
from src.engine.stock_matrix import column_map_for_period, today_vn

# Đảm bảo bảng luôn tồn tại
Base.metadata.create_all(bind=engine)

_STOCK_LOCK = FileTransactionLock(lambda: (
    Path(engine.url.database).with_suffix('.stock.lock') if engine.dialect.name == 'sqlite' and engine.url.database != ':memory:'
    else Path(__file__).resolve().parents[2] / 'data' / 'stock-write.lock'))



# Identical stock requests inside this window are treated as a double click.
DUPLICATE_WINDOW_SECONDS = 3

def _serialize_stock_write(function):
    @wraps(function)
    def call(*args, **kwargs):
        with _STOCK_LOCK:
            return function(*args, **kwargs)
    return call

REAL_OCTOBER_DATA = [
    {
        "stt": 1,
        "ing_id": "1",
        "name": "Ốc quế (400 cái/thùng, 25 cái/dây)",
        "initial": 6.0,
        "inflow": {"2026-10-01": 0.0},
        "outflow": {"2026-10-01": 1.0, "2026-10-04": 1.0, "2026-10-08": 1.0, "2026-10-11": 1.0}
    },
    {
        "stt": 2,
        "ing_id": "2",
        "name": "Bột kem (3kg*8 túi)",
        "initial": 2.0,
        "inflow": {"2026-10-01": 1.0, "2026-10-12": 2.0},
        "outflow": {"2026-10-03": 1.0, "2026-10-08": 1.0, "2026-10-11": 1.0}
    },
    {
        "stt": 3,
        "ing_id": "3",
        "name": "Bột trà sữa (2kg x 10 túi)",
        "initial": 1.0,
        "inflow": {"2026-10-01": 1.0, "2026-10-12": 2.0},
        "outflow": {"2026-10-05": 1.0, "2026-10-09": 1.0, "2026-10-13": 1.0}
    },
    {
        "stt": 4,
        "ing_id": "4",
        "name": "Bột pudding (1kg*20 túi, thùng 20kg)",
        "initial": 1.0,
        "inflow": {"2026-10-01": 0.0, "2026-10-12": 1.0},
        "outflow": {"2026-10-05": 1.0}
    },
    {
        "stt": 6,
        "ing_id": "6",
        "name": "Cốc 700 (1 dây 50c, 20 dây/kiện)",
        "initial": 1.0,
        "inflow": {"2026-10-01": 2.0, "2026-10-12": 2.0},
        "outflow": {"2026-10-02": 1.0, "2026-10-07": 1.0, "2026-10-10": 1.0, "2026-10-13": 1.0}
    },
    {
        "stt": 7,
        "ing_id": "7",
        "name": "Cốc 500 (1 dây 50c, 20 dây/kiện)",
        "initial": 0.0,
        "inflow": {"2026-10-01": 1.0, "2026-10-12": 1.0},
        "outflow": {"2026-10-08": 1.0}
    },
    {
        "stt": 8,
        "ing_id": "8",
        "name": "Cốc chữ U (1 dây 50c, 20 dây/kiện)",
        "initial": 0.0,
        "inflow": {"2026-10-01": 1.0, "2026-10-12": 1.0},
        "outflow": {"2026-10-13": 1.0}
    },
    {
        "stt": 9,
        "ing_id": "9",
        "name": "Đường quả (Syrup hoa quả) 6.5kg/bình, 4 bình/kiện",
        "initial": 1.0,
        "inflow": {"2026-10-01": 2.0, "2026-10-12": 1.0},
        "outflow": {"2026-10-01": 1.0, "2026-10-10": 2.0, "2026-10-13": 1.0}
    },
    {
        "stt": 10,
        "ing_id": "10",
        "name": "Đường mật (đường mía) 6.5kg/bình, 4 bình/kiện",
        "initial": 1.0,
        "inflow": {"2026-10-01": 4.0, "2026-10-12": 4.0},
        "outflow": {"2026-10-01": 3.0, "2026-10-11": 1.0, "2026-10-13": 1.0}
    },
    {
        "stt": 11,
        "ing_id": "11",
        "name": "Đường đen (1,2kg*12 chai)",
        "initial": 0.0,
        "inflow": {"2026-10-01": 2.0},
        "outflow": {"2026-10-01": 1.0, "2026-10-13": 1.0}
    },
    {
        "stt": 12,
        "ing_id": "12",
        "name": "Trân châu đen (1kg*16 túi, thùng 16kg)",
        "initial": 1.0,
        "inflow": {"2026-10-01": 2.0, "2026-10-12": 4.0},
        "outflow": {"2026-10-03": 1.0, "2026-10-07": 1.0, "2026-10-10": 1.0}
    },
    {
        "stt": 13,
        "ing_id": "13",
        "name": "Hồng trà (8KG,50G*160túi)",
        "initial": 0.5,
        "inflow": {"2026-10-01": 1.0, "2026-10-12": 1.0},
        "outflow": {"2026-10-07": 0.5, "2026-10-13": 0.5}
    },
]

def init_sample_daily_stock(force: bool = False):
    """Khởi tạo dữ liệu thực tế từ Google Sheet của quán (01/10 - 13/10).
    Tuyệt đối không điền bừa các ngày tương lai hay số lượng thực tế khi chưa kiểm kê."""
    if not demo_enabled():
        return
    db = SessionLocal()
    try:
        count = db.query(DailyStockMovement).count()
        if count == 0 or force:
            if force:
                db.query(DailyStockMovement).delete()
            records = []
            for item in REAL_OCTOBER_DATA:
                ing_id = item["ing_id"]
                # 1. Tồn đầu kỳ tháng 9
                records.append(DailyStockMovement(
                    business_date=date(2026, 9, 30),
                    ingredient_id=ing_id,
                    movement_type="INITIAL",
                    quantity=item["initial"],
                    status="APPROVED",
                    recorded_by="admin_seed",
                    approved_by="chucuahang",
                    approved_at=datetime.now(),
                    notes="Tồn cuối tháng 9/2026 chuyển sang"
                ))
                # 2. Các đợt nhập thực tế từ xe hàng tổng
                for d_str, qty in item["inflow"].items():
                    records.append(DailyStockMovement(
                        business_date=date.fromisoformat(d_str),
                        ingredient_id=ing_id,
                        movement_type="IN",
                        quantity=qty,
                        status="APPROVED",
                        recorded_by="quanly",
                        approved_by="quanly",
                        approved_at=datetime.now(),
                        notes="Nhập hàng xe tổng Mixue"
                    ))
                # 3. Các ngày xuất dùng thực tế tại quầy
                for d_str, qty in item["outflow"].items():
                    records.append(DailyStockMovement(
                        business_date=date.fromisoformat(d_str),
                        ingredient_id=ing_id,
                        movement_type="OUT",
                        quantity=qty,
                        status="APPROVED",
                        recorded_by="nhanvien",
                        approved_by="quanly",
                        approved_at=datetime.now(),
                        notes="Xuất quầy bar pha chế"
                    ))
            db.add_all(records)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[daily_stock_service] Lỗi khởi tạo: {e}")
    finally:
        db.close()


# No sample movements are written on import: the stock book shows only what the shop recorded.
# Seed explicitly for a demo: `python -c "from src.engine.daily_stock_service import init_sample_daily_stock as f; f(True)"`.


@_serialize_stock_write
def create_stock_request(
    business_date: date,
    ingredient_id: str,
    movement_type: str,
    quantity: float,
    recorded_by: str,
    user_role: str,
    notes: str | None = None
) -> dict[str, Any]:
    """Tạo đề xuất lệnh xuất/nhập kho.
    - Quản lý / Chủ quán: Tự động DUYỆT NGAY và ghi thẳng vào sổ kho.
    - Nhân viên chính thức: Tạo lệnh ở trạng thái PENDING chờ Quản lý duyệt.
    """
    clean_type = movement_type.strip().upper()
    if clean_type not in ("IN", "OUT", "ACTUAL_COUNT", "INITIAL"):
        return {"status": "ERROR", "message": f"Loại giao dịch không hợp lệ: {clean_type}"}
    if (not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not math.isfinite(quantity)
            or quantity < 0 or quantity > 99_999_999 or (quantity == 0 and clean_type in {'IN', 'OUT'})):
        return {'status': 'ERROR', 'message': 'Số lượng không hợp lệ; kiểm kê có thể bằng 0, nhập/xuất phải lớn hơn 0.'}

    is_admin = is_admin_role(user_role)
    status = "APPROVED" if is_admin else "PENDING"
    approved_by = recorded_by if is_admin else None
    approved_at = datetime.now() if is_admin else None

    db = SessionLocal()
    try:
        actor = db.get(User, recorded_by)
        if (not actor or not actor.is_active or normalize_role(actor.role) != normalize_role(user_role)
                or not (is_admin_role(actor.role) or normalize_role(actor.role) == 'STAFF_OFFICIAL')):
            return {'status': 'FORBIDDEN', 'message': 'Tài khoản không có quyền ghi lệnh kho.'}
        if clean_type == 'INITIAL' and not is_admin:
            return {'status': 'FORBIDDEN', 'message': 'Chỉ quản lý được nhập tồn đầu kỳ.'}
        ing = db.query(Ingredient).filter(Ingredient.ingredient_id == str(ingredient_id)).with_for_update().first()
        if not ing:
            return {'status': 'ERROR', 'message': 'Mã nguyên liệu không tồn tại.'}
        # Idempotency / Double-click check: reject duplicate identical requests within 3 seconds
        now = datetime.now()
        recent_cutoff = now - timedelta(seconds=DUPLICATE_WINDOW_SECONDS)
        duplicate = db.query(DailyStockMovement).filter(
            DailyStockMovement.business_date == business_date,
            DailyStockMovement.ingredient_id == str(ingredient_id),
            DailyStockMovement.movement_type == clean_type,
            DailyStockMovement.recorded_by == recorded_by,
            DailyStockMovement.quantity == quantity,
            DailyStockMovement.created_at >= recent_cutoff,
            # Upper bound: rows stamped in another timezone (naive local time) can look
            # hours "in the future" and must not be mistaken for a double click.
            DailyStockMovement.created_at <= now + timedelta(seconds=1),
        ).first()

        if duplicate:
            return {
                "status": "DUPLICATE",
                "request_id": duplicate.id,
                "is_approved": duplicate.status == "APPROVED",
                "message": f"⚠️ Lệnh kho tương tự vừa được tạo cách đây vài giây (Mã lệnh: #{duplicate.id}). Vui lòng không nhấn liên tục để tránh trùng lặp dữ liệu."
            }

        ing = db.query(Ingredient).filter(Ingredient.ingredient_id == str(ingredient_id)).first()
        ing_name = ing.ingredient_name if ing else f"Mã {ingredient_id}"

        new_rec = DailyStockMovement(
            business_date=business_date,
            ingredient_id=str(ingredient_id),
            movement_type=clean_type,
            quantity=quantity,
            status=status,
            recorded_by=recorded_by,
            approved_by=approved_by,
            approved_at=approved_at,
            notes=notes
        )
        db.add(new_rec)
        db.commit()

        type_vi = "Nhập kho" if clean_type == "IN" else ("Xuất quầy bar" if clean_type == "OUT" else "Kiểm kê đếm kho")
        if is_admin:
            msg = f"✅ [Quản trị] Đã ghi nhận và duyệt tự động lệnh {type_vi}: {quantity} đơn vị cho món '{ing_name}' ngày {business_date.strftime('%d/%m/%Y')}."
        else:
            msg = f"⏳ [Nhân viên] Đã gửi yêu cầu lệnh {type_vi}: {quantity} đơn vị cho món '{ing_name}' đến Quản lý. Lệnh sẽ được ghi vào sổ kho ngay sau khi Quản lý duyệt."

        return {
            "status": "SUCCESS",
            "request_id": new_rec.id,
            "is_approved": is_admin,
            "message": msg
        }
    except Exception as e:
        db.rollback()
        return {"status": "ERROR", "message": f"Lỗi cơ sở dữ liệu: {e!s}"}
    finally:
        db.close()


def record_daily_movement(
    business_date: date,
    ingredient_id: str,
    movement_type: str,
    quantity: float,
    recorded_by: str = "admin",
    notes: str | None = None
) -> dict[str, Any]:
    """Ghi nhận trực tiếp lệnh kho (tự động duyệt cho admin hoặc tương thích ngược)."""
    return create_stock_request(
        business_date=business_date,
        ingredient_id=ingredient_id,
        movement_type=movement_type,
        quantity=quantity,
        recorded_by=recorded_by,
        user_role="ADMIN",
        notes=notes
    )


def get_pending_requests() -> list[dict[str, Any]]:
    """Lấy danh sách các lệnh xuất/nhập kho đang chờ Quản lý duyệt."""
    db = SessionLocal()
    try:
        reqs = db.query(DailyStockMovement).filter(
            DailyStockMovement.status == "PENDING"
        ).order_by(DailyStockMovement.created_at.desc()).all()

        ing_map = {i.ingredient_id: i.ingredient_name for i in db.query(Ingredient).all()}
        result = []
        for r in reqs:
            type_vi = "📤 Xuất quầy bar" if r.movement_type == "OUT" else ("📥 Nhập kho tổng" if r.movement_type == "IN" else "🔍 Kiểm kê")
            result.append({
                "id": r.id,
                "business_date": r.business_date.strftime("%d/%m/%Y"),
                "ingredient_id": r.ingredient_id,
                "ingredient_name": ing_map.get(r.ingredient_id, f"Mã {r.ingredient_id}"),
                "movement_type": r.movement_type,
                "type_vi": type_vi,
                "quantity": float(r.quantity),
                "recorded_by": r.recorded_by,
                "notes": r.notes or "—",
                "created_at": r.created_at.strftime("%d/%m/%Y %H:%M") if r.created_at else "—"
            })
        return result
    finally:
        db.close()


@_serialize_stock_write
def approve_stock_request(request_id: int, admin_username: str) -> tuple[bool, str]:
    """Quản lý / Chủ quán duyệt lệnh xuất/nhập kho của nhân viên."""
    db = SessionLocal()
    try:
        actor = db.get(User, admin_username)
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, 'Chỉ quản lý đang hoạt động được duyệt lệnh kho.'
        rec = db.query(DailyStockMovement).filter(DailyStockMovement.id == request_id).first()
        if not rec:
            return False, f"Không tìm thấy yêu cầu lệnh kho #{request_id}."
        if rec.status != 'PENDING':
            return False, f"Lệnh #{request_id} đã được duyệt trước đó."
        changed = db.query(DailyStockMovement).filter(DailyStockMovement.id == request_id, DailyStockMovement.status == 'PENDING').update(
            {'status': 'APPROVED', 'approved_by': admin_username, 'approved_at': datetime.now()}, synchronize_session=False)
        if not changed:
            db.rollback()
            return False, 'Lệnh đã được xử lý bởi một phiên khác.'
        db.commit()

        ing = db.query(Ingredient).filter(Ingredient.ingredient_id == rec.ingredient_id).first()
        ing_name = ing.ingredient_name if ing else rec.ingredient_id
        return True, f"Đã phê duyệt lệnh #{request_id}: {rec.movement_type} {rec.quantity} món '{ing_name}' của nhân viên '{rec.recorded_by}'. Dữ liệu đã được ghi vào sổ kho 31 ngày."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi phê duyệt: {e!s}"
    finally:
        db.close()


@_serialize_stock_write
def reject_stock_request(request_id: int, admin_username: str, reason: str = "") -> tuple[bool, str]:
    """Quản lý từ chối lệnh xuất/nhập kho của nhân viên."""
    db = SessionLocal()
    try:
        actor = db.get(User, admin_username)
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, 'Chỉ quản lý đang hoạt động được từ chối lệnh kho.'
        rec = db.query(DailyStockMovement).filter(DailyStockMovement.id == request_id).first()
        if not rec:
            return False, f"Không tìm thấy yêu cầu lệnh kho #{request_id}."

        changed = db.query(DailyStockMovement).filter(DailyStockMovement.id == request_id, DailyStockMovement.status == 'PENDING').update(
            {'status': 'REJECTED', 'approved_by': admin_username, 'approved_at': datetime.now(),
             'rejection_reason': reason or 'Quản lý từ chối'}, synchronize_session=False)
        if not changed:
            db.rollback()
            return False, 'Chỉ được từ chối lệnh đang chờ duyệt.'
        db.commit()
        return True, f"Đã từ chối lệnh kho #{request_id}. Lệnh này sẽ không được ghi vào sổ kho."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi từ chối: {e!s}"
    finally:
        db.close()


def get_user_requests(username: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Lấy danh sách các lệnh của nhân viên để theo dõi trạng thái duyệt."""
    db = SessionLocal()
    try:
        query = db.query(DailyStockMovement)
        if username:
            query = query.filter(DailyStockMovement.recorded_by == username)
        reqs = query.order_by(DailyStockMovement.created_at.desc()).limit(limit).all()

        ing_map = {i.ingredient_id: i.ingredient_name for i in db.query(Ingredient).all()}
        result = []
        for r in reqs:
            status_badge = "⏳ Chờ Quản lý duyệt" if r.status == "PENDING" else ("✅ Đã duyệt ghi sổ" if r.status == "APPROVED" else "❌ Đã từ chối")
            type_vi = "📤 Xuất quầy" if r.movement_type == "OUT" else ("📥 Nhập hàng" if r.movement_type == "IN" else "🔍 Kiểm kê")
            result.append({
                "Mã lệnh": f"#{r.id}",
                "Ngày": r.business_date.strftime("%d/%m/%Y"),
                "Mặt hàng": ing_map.get(r.ingredient_id, r.ingredient_id),
                "Loại lệnh": type_vi,
                "Số lượng": float(r.quantity),
                "Trạng thái": status_badge,
                "Người duyệt": r.approved_by or "—",
                "Ghi chú": r.notes or "—",
                "Thời gian gửi": r.created_at.strftime("%H:%M %d/%m") if r.created_at else "—"
            })
        return result
    finally:
        db.close()


# Column → (date, movement type) is built per month by stock_matrix.column_map_for_period(year, month).


@_serialize_stock_write
def delete_stock_movement(movement_id: int, admin_username: str = "admin") -> tuple[bool, str]:
    """Xóa bỏ hoàn toàn một bản ghi giao dịch kho theo ID (Sổ kho tự động tính toán lại ngay)."""
    db = SessionLocal()
    try:
        actor = db.get(User, admin_username)
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, 'Chỉ quản lý đang hoạt động được xóa lệnh kho.'
        rec = db.query(DailyStockMovement).filter(DailyStockMovement.id == movement_id).first()
        if not rec:
            return False, f"Không tìm thấy bản ghi giao dịch kho #{movement_id}."

        ing = db.query(Ingredient).filter(Ingredient.ingredient_id == rec.ingredient_id).first()
        ing_name = ing.ingredient_name if ing else f"Mã {rec.ingredient_id}"
        type_str = "Xuất quầy" if rec.movement_type == "OUT" else ("Nhập kho" if rec.movement_type == "IN" else ("Tồn đầu kỳ" if rec.movement_type == "INITIAL" else "Kiểm kê"))
        date_str = rec.business_date.strftime("%d/%m/%Y")
        qty = float(rec.quantity)

        db.delete(rec)
        db.commit()
        return True, f"Đã xóa thành công lệnh #{movement_id}: {type_str} {qty:g} món '{ing_name}' (Ngày {date_str})."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi xóa bản ghi: {e!s}"
    finally:
        db.close()


@_serialize_stock_write
def update_stock_movement(
    movement_id: int,
    new_quantity: float,
    admin_username: str = "admin",
    new_date: date | None = None,
    notes: str | None = None
) -> tuple[bool, str]:
    """Sửa đổi trực tiếp thông tin số lượng/ngày của một bản ghi giao dịch kho."""
    db = SessionLocal()
    try:
        actor = db.get(User, admin_username)
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, 'Chỉ quản lý đang hoạt động được sửa lệnh kho.'
        if not math.isfinite(float(new_quantity)) or not 0 <= float(new_quantity) <= 99_999_999:
            return False, 'Số lượng không hợp lệ.'
        rec = db.query(DailyStockMovement).filter(DailyStockMovement.id == movement_id).first()
        if not rec:
            return False, f"Không tìm thấy bản ghi giao dịch kho #{movement_id}."
        if float(new_quantity) == 0 and rec.movement_type in {'IN', 'OUT'}:
            return False, 'Lượng nhập/xuất phải lớn hơn 0.'

        old_qty = float(rec.quantity)
        rec.quantity = float(new_quantity)
        if new_date:
            rec.business_date = new_date
        if notes is not None:
            rec.notes = notes
        rec.approved_by = admin_username
        rec.approved_at = datetime.now()
        db.commit()

        ing = db.query(Ingredient).filter(Ingredient.ingredient_id == rec.ingredient_id).first()
        ing_name = ing.ingredient_name if ing else f"Mã {rec.ingredient_id}"
        return True, f"Đã cập nhật lệnh #{movement_id} ({ing_name}): số lượng đổi từ {old_qty:g} sang {float(new_quantity):g}."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi cập nhật: {e!s}"
    finally:
        db.close()


def get_cell_value(ingredient_id: str, column_name: str, *, year=None, month=None) -> float | None:
    """Lấy số lượng hiện tại được duyệt trong cơ sở dữ liệu của một ô cụ thể."""
    if year is None or month is None:
        from src.engine.stock_matrix import current_period
        year, month = current_period()
    mapping = column_map_for_period(year, month)
    if column_name not in mapping:
        return None
    date_str, m_type = mapping[column_name]
    b_date = date.fromisoformat(date_str)
    db = SessionLocal()
    try:
        records = db.query(DailyStockMovement).filter(
            DailyStockMovement.business_date == b_date,
            DailyStockMovement.ingredient_id == str(ingredient_id),
            DailyStockMovement.movement_type == m_type,
            DailyStockMovement.status == "APPROVED"
        ).order_by(DailyStockMovement.id).all()
        if records:
            return float(records[-1].quantity) if m_type == 'ACTUAL_COUNT' else sum(float(rec.quantity) for rec in records)
        return None
    finally:
        db.close()


def get_all_movements_detailed(limit: int = 300) -> list[dict[str, Any]]:
    """Lấy toàn bộ danh sách giao dịch kho chi tiết để hỗ trợ xem, sửa và xóa trực tiếp."""
    db = SessionLocal()
    try:
        ings = {i.ingredient_id: i.ingredient_name for i in db.query(Ingredient).all()}
        movs = db.query(DailyStockMovement).order_by(
            DailyStockMovement.business_date.desc(),
            DailyStockMovement.id.desc()
        ).limit(limit).all()

        results = []
        for m in movs:
            type_label = {
                "INITIAL": "📌 Tồn đầu kỳ",
                "IN": "📥 Nhập hàng",
                "OUT": "📤 Xuất quầy bar",
                "ACTUAL_COUNT": "🔍 Kiểm kê thực tế"
            }.get(m.movement_type, m.movement_type)

            results.append({
                "id": m.id,
                "business_date": m.business_date.strftime("%d/%m/%Y"),
                "date_iso": m.business_date.isoformat(),
                "ingredient_id": m.ingredient_id,
                "ingredient_name": ings.get(m.ingredient_id, f"Mã {m.ingredient_id}"),
                "movement_type": m.movement_type,
                "type_label": type_label,
                "quantity": float(m.quantity),
                "status": m.status,
                "recorded_by": m.recorded_by or "—",
                "approved_by": m.approved_by or "—",
                "notes": m.notes or "—",
                "created_at": m.created_at.strftime("%H:%M %d/%m") if m.created_at else "—"
            })
        return results
    finally:
        db.close()


@_serialize_stock_write
def update_stock_cell_manually(
    ingredient_id: str,
    column_name: str,
    new_value: Any,
    updated_by: str = "admin",
    *, year: int | None = None, month: int | None = None
) -> tuple[bool, str]:
    """Cập nhật hoặc xóa giá trị một ô bằng tay (Manual Cell Update / Delete)."""
    if year is None or month is None:
        from src.engine.stock_matrix import current_period
        year, month = current_period()
    mapping = column_map_for_period(year, month)
    if column_name not in mapping:
        return False, f"Cột '{column_name}' là cột công thức tự động, không thể sửa trực tiếp."

    date_str, m_type = mapping[column_name]
    b_date = date.fromisoformat(date_str)
    if m_type == "INITIAL":
        # Correcting last month's closing stock: it becomes this month's opening balance, and the same figure is
        # written as last month's end-of-month count so last month's sheet shows it (Tồn thực tế / Chênh lệch).
        ok, msg = _write_cell(ingredient_id, b_date, "INITIAL", new_value, updated_by, column_name)
        if ok:
            _write_cell(ingredient_id, b_date, "ACTUAL_COUNT", new_value, updated_by, column_name)
        return ok, msg
    if m_type == "ACTUAL_COUNT" and b_date.day == calendar.monthrange(b_date.year, b_date.month)[1]:
        # The end-of-month count is next month's opening balance.
        ok, msg = _write_cell(ingredient_id, b_date, "ACTUAL_COUNT", new_value, updated_by, column_name)
        if ok:
            _write_cell(ingredient_id, b_date, "INITIAL", new_value, updated_by, column_name)
        return ok, msg
    return _write_cell(ingredient_id, b_date, m_type, new_value, updated_by, column_name)


def _write_cell(ingredient_id, b_date, m_type, new_value, updated_by, column_name):
    # Xử lý các giá trị xóa / rỗng / NaN
    is_delete = False
    new_qty: float | None = None

    if new_value is None or pd.isna(new_value):
        is_delete = True
    else:
        s_val = str(new_value).strip().lower()
        if s_val in ("", "—", "-", "none", "nan", "null", "xóa", "delete"):
            is_delete = True
        else:
            try:
                new_qty = float(s_val.replace(",", "."))
                if not math.isfinite(new_qty) or not 0 <= new_qty <= 99_999_999:
                    return False, "Số lượng không thể âm."
                if new_qty == 0 and m_type == "OUT":
                    is_delete = True
            except ValueError:
                return False, f"Giá trị '{new_value}' không phải là số hợp lệ."

    db = SessionLocal()
    try:
        actor = db.get(User, updated_by)
        if not actor or not actor.is_active or not is_admin_role(actor.role):
            return False, 'Chỉ quản lý đang hoạt động được sửa sổ kho.'
        approved_rows = db.query(DailyStockMovement).filter(
            DailyStockMovement.business_date == b_date,
            DailyStockMovement.ingredient_id == str(ingredient_id),
            DailyStockMovement.movement_type == m_type,
            DailyStockMovement.status == 'APPROVED'
        ).order_by(DailyStockMovement.id.desc()).all()
        existing = approved_rows[0] if approved_rows else None

        ing = db.query(Ingredient).filter(Ingredient.ingredient_id == str(ingredient_id)).first()
        if not ing:
            return False, 'Mã nguyên liệu không tồn tại.'
        ing_name = ing.ingredient_name if ing else f"Mã {ingredient_id}"

        if is_delete or new_qty is None:
            if existing:
                for row in approved_rows:
                    db.delete(row)
                db.commit()
                return True, f"Đã xóa dữ liệu ô '{column_name}' của '{ing_name}'."
            return True, f"Ô '{column_name}' của '{ing_name}' hiện đã trống."
        else:
            if existing:
                # A cell is the aggregate of all approved rows; pending requests
                # remain separate and must pass the normal approval action.
                for row in approved_rows[1:]:
                    db.delete(row)
                existing.quantity = new_qty
                existing.status = "APPROVED"
                existing.approved_by = updated_by
                existing.approved_at = datetime.now()
                existing.notes = (f"Điều chỉnh tồn cuối tháng bởi {updated_by}" if (m_type in ("INITIAL", "ACTUAL_COUNT") and b_date.day == calendar.monthrange(b_date.year, b_date.month)[1])
                                  else f"Sửa trực tiếp bằng tay bởi {updated_by}")
            else:
                new_rec = DailyStockMovement(
                    business_date=b_date,
                    ingredient_id=str(ingredient_id),
                    movement_type=m_type,
                    quantity=new_qty,
                    status="APPROVED",
                    recorded_by=updated_by,
                    approved_by=updated_by,
                    approved_at=datetime.now(),
                    notes=(f"Điều chỉnh tồn cuối tháng bởi {updated_by}" if (m_type in ("INITIAL", "ACTUAL_COUNT") and b_date.day == calendar.monthrange(b_date.year, b_date.month)[1])
                           else f"Nhập trực tiếp bằng tay bởi {updated_by}")
                )
                db.add(new_rec)
            db.commit()
            return True, f"Đã lưu giá trị {new_qty:g} vào ô '{column_name}' của '{ing_name}'."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi cập nhật: {e!s}"
    finally:
        db.close()


def update_stock_matrix_from_editor(
    edited_df: pd.DataFrame,
    original_df: pd.DataFrame,
    updated_by: str = "admin",
    editor_session_data: dict[str, Any] | None = None,
    *, year: int | None = None, month: int | None = None
) -> dict[str, Any]:
    """Cập nhật hàng loạt các thay đổi từ bảng chỉnh sửa trực tiếp (st.data_editor).
    Hỗ trợ đọc trực tiếp delta từ st.session_state[editor_key]['edited_rows'] và so sánh DataFrame.
    """
    updated_count = 0
    if year is None or month is None:
        from src.engine.stock_matrix import current_period
        year, month = current_period()
    column_mapping = column_map_for_period(year, month)
    errors = []

    # 1. Nếu có session state delta 'edited_rows' từ Streamlit data_editor
    if editor_session_data and "edited_rows" in editor_session_data:
        edited_rows_dict = editor_session_data["edited_rows"]
        for row_idx_str, col_updates in edited_rows_dict.items():
            row_idx = int(row_idx_str)
            if row_idx < 0 or row_idx >= len(original_df):
                continue
            orig_row = original_df.iloc[row_idx]
            ing_id = str(orig_row.get("Mã NL", ""))
            if not ing_id:
                continue

            for col_name, val_new in col_updates.items():
                if col_name not in column_mapping:
                    continue
                ok, msg = update_stock_cell_manually(ing_id, col_name, val_new, updated_by, year=year, month=month)
                if ok:
                    updated_count += 1
                else:
                    errors.append(msg)

    # 2. Nếu không có delta hoặc delta chưa ghi nhận, kiểm tra so sánh DataFrame diff
    if updated_count == 0:
        orig_rows = list(original_df.iterrows())
        edited_rows = list(edited_df.iterrows())

        for idx, (_, row) in enumerate(edited_rows):
            if idx >= len(orig_rows):
                break
            orig_row = orig_rows[idx][1]
            ing_id = str(orig_row.get("Mã NL", row.get("Mã NL", "")))
            if not ing_id:
                continue

            for col_name in row.index:
                if col_name not in column_mapping:
                    continue

                val_new = row[col_name]
                val_orig = orig_row.get(col_name)

                # Chuẩn hóa để so sánh
                if pd.isna(val_new) and pd.isna(val_orig):
                    continue
                str_new = str(val_new).strip() if (val_new is not None and not pd.isna(val_new)) else ""
                str_orig = str(val_orig).strip() if (val_orig is not None and not pd.isna(val_orig)) else ""

                if str_new == str_orig:
                    continue

                # Thử so sánh số học nếu cả 2 là số (tránh 1 vs 1.0)
                try:
                    f_new = float(str_new)
                    f_orig = float(str_orig)
                    if f_new == f_orig:
                        continue
                except ValueError:
                    pass

                ok, msg = update_stock_cell_manually(ing_id, col_name, val_new, updated_by, year=year, month=month)
                if ok:
                    updated_count += 1
                else:
                    errors.append(msg)

    return {
        "status": "SUCCESS" if not errors else "PARTIAL",
        "updated_count": updated_count,
        "errors": errors
    }


def get_stock_matrix_df(year: int | None = None, month: int | None = None) -> pd.DataFrame:
    """Approved movements within the requested calendar month (default: this month, Vietnam time)."""
    from src.engine.stock_matrix import build_stock_matrix, current_period
    if year is None or month is None:
        year, month = current_period()
    with SessionLocal() as db:
        return build_stock_matrix(db, year, month)



def generate_excel_export(year: int | None = None, month: int | None = None) -> bytes:
    """File kho Excel của tháng được chọn (mặc định tháng hiện tại), đủ số ngày thực của tháng."""
    from src.engine.stock_matrix import current_period
    if year is None or month is None:
        year, month = current_period()
    df = get_stock_matrix_df(year, month)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Kho tháng {month}-{year}"

    fill_header = PatternFill(start_color="FFF1F2", end_color="FFF1F2", fill_type="solid")
    fill_import = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")
    fill_stock = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    font_bold = Font(name="Arial", size=10, bold=True)
    font_regular = Font(name="Arial", size=10)
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    cols = [c for c in df.columns if c != "Mã NL"]
    ws.append(cols)

    for col_num in range(1, len(cols) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = font_bold
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border_thin
        col_name = cols[col_num - 1]
        if "Nhập" in col_name:
            cell.fill = fill_import
        elif "Tồn" in col_name:
            cell.fill = fill_stock
        else:
            cell.fill = fill_header

    for r_idx, row in df.iterrows():
        row_vals = [row[c] for c in cols]
        ws.append(row_vals)
        current_row = ws.max_row
        for c_idx in range(1, len(row_vals) + 1):
            c_cell = ws.cell(row=current_row, column=c_idx)
            c_cell.font = font_regular
            c_cell.border = border_thin
            col_name = cols[c_idx - 1]
            if "Nhập" in col_name:
                c_cell.fill = fill_import
                c_cell.alignment = Alignment(horizontal="center")
            elif "Tồn" in col_name:
                c_cell.fill = fill_stock
                c_cell.font = font_bold
                c_cell.alignment = Alignment(horizontal="center")
            elif col_name == "Tên mặt hàng (Quy cách)":
                c_cell.alignment = Alignment(horizontal="left")
            else:
                c_cell.alignment = Alignment(horizontal="center")

    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 44
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def ledger_balances(as_of: date | None = None) -> dict[str, float]:
    """Book stock per ingredient on a day, in the ledger's units (cartons/packs), same rule as the stock sheet:
    the latest opening balance (INITIAL) on or before the day, plus approved stock-in, minus approved stock-out after it.
    Ingredients without any opening balance are left out (their stock is unknown, not zero)."""
    as_of = as_of or today_vn()
    db = SessionLocal()
    try:
        rows = (db.query(DailyStockMovement)
                .filter(DailyStockMovement.status == "APPROVED", DailyStockMovement.business_date <= as_of)
                .order_by(DailyStockMovement.business_date, DailyStockMovement.id).all())
    finally:
        db.close()
    balances: dict[str, float] = {}
    for movement in rows:
        ing = str(movement.ingredient_id)
        if movement.movement_type == "INITIAL":
            balances[ing] = float(movement.quantity)
        elif ing in balances and movement.movement_type == "IN":
            balances[ing] += float(movement.quantity)
        elif ing in balances and movement.movement_type == "OUT":
            balances[ing] -= float(movement.quantity)
    return balances
