# -*- coding: utf-8 -*-
"""Dịch vụ Quản lý Sổ Xuất - Nhập - Tồn Kho Hàng Ngày (Mixue Daily Stock Matrix - 31 Ngày).

Mô phỏng đầy đủ 31 ngày của tháng 10/2026 chuẩn theo mẫu ảnh Google Sheets của quán Mixue 39 Tôn Quang Phiệt.
Tích hợp quy trình phê duyệt lệnh kho (Maker-Checker):
- Nhân viên chính thức: Tạo yêu cầu lệnh xuất/nhập -> Trạng thái PENDING_APPROVAL.
- Quản lý / Chủ quán: Kiểm duyệt và phê duyệt -> Ghi nhận vào file/sổ kho và ma trận.
"""

from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple
import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

from src.database import SessionLocal, engine, Base
from src.models import DailyStockMovement, Ingredient
from src.auth import is_admin_role

# Đảm bảo bảng luôn tồn tại
Base.metadata.create_all(bind=engine)

OCTOBER_DAYS = [
    # (day_num, weekday_label, col_key, week_group)
    # Tuần 1: 01/10 - 04/10
    ("2026-10-01", "T5 1/10", "T5 1/10", "w1"),
    ("2026-10-02", "T6 2/10", "T6 2/10", "w1"),
    ("2026-10-03", "T7 3/10", "T7 3/10", "w1"),
    ("2026-10-04", "CN 4/10", "CN 4/10", "w1"),
    # Tuần 2: 05/10 - 11/10
    ("2026-10-05", "T2 5/10", "T2 5/10", "w2"),
    ("2026-10-06", "T3 6/10", "T3 6/10", "w2"),
    ("2026-10-07", "T4 7/10", "T4 7/10", "w2"),
    ("2026-10-08", "T5 8/10", "T5 8/10", "w2"),
    ("2026-10-09", "T6 9/10", "T6 9/10", "w2"),
    ("2026-10-10", "T7 10/10", "T7 10/10", "w2"),
    ("2026-10-11", "CN 11/10", "CN 11/10", "w2"),
    # Tuần 3: 12/10 - 18/10
    ("2026-10-12", "T2 12/10", "T2 12/10", "w3"),
    ("2026-10-13", "T3 13/10", "T3 13/10", "w3"),
    ("2026-10-14", "T4 14/10", "T4 14/10", "w3"),
    ("2026-10-15", "T5 15/10", "T5 15/10", "w3"),
    ("2026-10-16", "T6 16/10", "T6 16/10", "w3"),
    ("2026-10-17", "T7 17/10", "T7 17/10", "w3"),
    ("2026-10-18", "CN 18/10", "CN 18/10", "w3"),
    # Tuần 4: 19/10 - 25/10
    ("2026-10-19", "T2 19/10", "T2 19/10", "w4"),
    ("2026-10-20", "T3 20/10", "T3 20/10", "w4"),
    ("2026-10-21", "T4 21/10", "T4 21/10", "w4"),
    ("2026-10-22", "T5 22/10", "T5 22/10", "w4"),
    ("2026-10-23", "T6 23/10", "T6 23/10", "w4"),
    ("2026-10-24", "T7 24/10", "T7 24/10", "w4"),
    ("2026-10-25", "CN 25/10", "CN 25/10", "w4"),
    # Tuần 5: 26/10 - 31/10
    ("2026-10-26", "T2 26/10", "T2 26/10", "w5"),
    ("2026-10-27", "T3 27/10", "T3 27/10", "w5"),
    ("2026-10-28", "T4 28/10", "T4 28/10", "w5"),
    ("2026-10-29", "T5 29/10", "T5 29/10", "w5"),
    ("2026-10-30", "T6 30/10", "T6 30/10", "w5"),
    ("2026-10-31", "T7 31/10", "T7 31/10", "w5"),
]

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

# Tương thích ngược
SAMPLE_OCTOBER_DATA = REAL_OCTOBER_DATA


def init_sample_daily_stock(force: bool = False):
    """Khởi tạo dữ liệu thực tế từ Google Sheet của quán (01/10 - 13/10).
    Tuyệt đối không điền bừa các ngày tương lai hay số lượng thực tế khi chưa kiểm kê."""
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


init_sample_daily_stock()


def create_stock_request(
    business_date: date,
    ingredient_id: str,
    movement_type: str,
    quantity: float,
    recorded_by: str,
    user_role: str,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Tạo đề xuất lệnh xuất/nhập kho.
    - Quản lý / Chủ quán: Tự động DUYỆT NGAY và ghi thẳng vào sổ kho.
    - Nhân viên chính thức: Tạo lệnh ở trạng thái PENDING chờ Quản lý duyệt.
    """
    if quantity <= 0:
        return {"status": "ERROR", "message": "Số lượng phải lớn hơn 0!"}

    clean_type = movement_type.strip().upper()
    if clean_type not in ("IN", "OUT", "ACTUAL_COUNT", "INITIAL"):
        return {"status": "ERROR", "message": f"Loại giao dịch không hợp lệ: {clean_type}"}

    is_admin = is_admin_role(user_role)
    status = "APPROVED" if is_admin else "PENDING"
    approved_by = recorded_by if is_admin else None
    approved_at = datetime.now() if is_admin else None

    db = SessionLocal()
    try:
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
        return {"status": "ERROR", "message": f"Lỗi cơ sở dữ liệu: {str(e)}"}
    finally:
        db.close()


def record_daily_movement(
    business_date: date,
    ingredient_id: str,
    movement_type: str,
    quantity: float,
    recorded_by: str = "admin",
    notes: Optional[str] = None
) -> Dict[str, Any]:
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


def get_pending_requests() -> List[Dict[str, Any]]:
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


def approve_stock_request(request_id: int, admin_username: str) -> Tuple[bool, str]:
    """Quản lý / Chủ quán duyệt lệnh xuất/nhập kho của nhân viên."""
    db = SessionLocal()
    try:
        rec = db.query(DailyStockMovement).filter(DailyStockMovement.id == request_id).first()
        if not rec:
            return False, f"Không tìm thấy yêu cầu lệnh kho #{request_id}."
        if rec.status == "APPROVED":
            return False, f"Lệnh #{request_id} đã được duyệt trước đó."

        rec.status = "APPROVED"
        rec.approved_by = admin_username
        rec.approved_at = datetime.now()
        db.commit()

        ing = db.query(Ingredient).filter(Ingredient.ingredient_id == rec.ingredient_id).first()
        ing_name = ing.ingredient_name if ing else rec.ingredient_id
        return True, f"Đã phê duyệt lệnh #{request_id}: {rec.movement_type} {rec.quantity} món '{ing_name}' của nhân viên '{rec.recorded_by}'. Dữ liệu đã được ghi vào sổ kho 31 ngày."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi phê duyệt: {str(e)}"
    finally:
        db.close()


def reject_stock_request(request_id: int, admin_username: str, reason: str = "") -> Tuple[bool, str]:
    """Quản lý từ chối lệnh xuất/nhập kho của nhân viên."""
    db = SessionLocal()
    try:
        rec = db.query(DailyStockMovement).filter(DailyStockMovement.id == request_id).first()
        if not rec:
            return False, f"Không tìm thấy yêu cầu lệnh kho #{request_id}."

        rec.status = "REJECTED"
        rec.approved_by = admin_username
        rec.rejection_reason = reason or "Quản lý từ chối"
        db.commit()
        return True, f"Đã từ chối lệnh kho #{request_id}. Lệnh này sẽ không được ghi vào sổ kho."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi từ chối: {str(e)}"
    finally:
        db.close()


def get_user_requests(username: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
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


COLUMN_TO_MOVEMENT_MAP: Dict[str, Tuple[str, str]] = {
    "Tồn T9": ("2026-09-30", "INITIAL"),
    "Nhập 1/10": ("2026-10-01", "IN"),
    "T5 1/10": ("2026-10-01", "OUT"),
    "T6 2/10": ("2026-10-02", "OUT"),
    "T7 3/10": ("2026-10-03", "OUT"),
    "CN 4/10": ("2026-10-04", "OUT"),
    "T2 5/10": ("2026-10-05", "OUT"),
    "T3 6/10": ("2026-10-06", "OUT"),
    "T4 7/10": ("2026-10-07", "OUT"),
    "T5 8/10": ("2026-10-08", "OUT"),
    "T6 9/10": ("2026-10-09", "OUT"),
    "T7 10/10": ("2026-10-10", "OUT"),
    "CN 11/10": ("2026-10-11", "OUT"),
    "Nhập 12/10": ("2026-10-12", "IN"),
    "T2 12/10": ("2026-10-12", "OUT"),
    "T3 13/10": ("2026-10-13", "OUT"),
    "T4 14/10": ("2026-10-14", "OUT"),
    "T5 15/10": ("2026-10-15", "OUT"),
    "T6 16/10": ("2026-10-16", "OUT"),
    "T7 17/10": ("2026-10-17", "OUT"),
    "CN 18/10": ("2026-10-18", "OUT"),
    "Nhập 19/10": ("2026-10-19", "IN"),
    "T2 19/10": ("2026-10-19", "OUT"),
    "T3 20/10": ("2026-10-20", "OUT"),
    "T4 21/10": ("2026-10-21", "OUT"),
    "T5 22/10": ("2026-10-22", "OUT"),
    "T6 23/10": ("2026-10-23", "OUT"),
    "T7 24/10": ("2026-10-24", "OUT"),
    "CN 25/10": ("2026-10-25", "OUT"),
    "T2 26/10": ("2026-10-26", "OUT"),
    "T3 27/10": ("2026-10-27", "OUT"),
    "T4 28/10": ("2026-10-28", "OUT"),
    "T5 29/10": ("2026-10-29", "OUT"),
    "T6 30/10": ("2026-10-30", "OUT"),
    "T7 31/10": ("2026-10-31", "OUT"),
    "Tồn thực tế": ("2026-10-31", "ACTUAL_COUNT"),
}


def delete_stock_movement(movement_id: int, admin_username: str = "admin") -> Tuple[bool, str]:
    """Xóa bỏ hoàn toàn một bản ghi giao dịch kho theo ID (Sổ kho tự động tính toán lại ngay)."""
    db = SessionLocal()
    try:
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
        return False, f"Lỗi xóa bản ghi: {str(e)}"
    finally:
        db.close()


def update_stock_movement(
    movement_id: int,
    new_quantity: float,
    admin_username: str = "admin",
    new_date: Optional[date] = None,
    notes: Optional[str] = None
) -> Tuple[bool, str]:
    """Sửa đổi trực tiếp thông tin số lượng/ngày của một bản ghi giao dịch kho."""
    db = SessionLocal()
    try:
        rec = db.query(DailyStockMovement).filter(DailyStockMovement.id == movement_id).first()
        if not rec:
            return False, f"Không tìm thấy bản ghi giao dịch kho #{movement_id}."

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
        return False, f"Lỗi cập nhật: {str(e)}"
    finally:
        db.close()


def get_cell_value(ingredient_id: str, column_name: str) -> Optional[float]:
    """Lấy số lượng hiện tại được duyệt trong cơ sở dữ liệu của một ô cụ thể."""
    if column_name not in COLUMN_TO_MOVEMENT_MAP:
        return None
    date_str, m_type = COLUMN_TO_MOVEMENT_MAP[column_name]
    b_date = date.fromisoformat(date_str)
    db = SessionLocal()
    try:
        rec = db.query(DailyStockMovement).filter(
            DailyStockMovement.business_date == b_date,
            DailyStockMovement.ingredient_id == str(ingredient_id),
            DailyStockMovement.movement_type == m_type,
            DailyStockMovement.status == "APPROVED"
        ).first()
        if rec:
            return float(rec.quantity)
        return None
    finally:
        db.close()


def get_all_movements_detailed(limit: int = 300) -> List[Dict[str, Any]]:
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


def update_stock_cell_manually(
    ingredient_id: str,
    column_name: str,
    new_value: Any,
    updated_by: str = "admin"
) -> Tuple[bool, str]:
    """Cập nhật hoặc xóa giá trị một ô bằng tay (Manual Cell Update / Delete)."""
    if column_name not in COLUMN_TO_MOVEMENT_MAP:
        return False, f"Cột '{column_name}' là cột công thức tự động, không thể sửa trực tiếp."

    date_str, m_type = COLUMN_TO_MOVEMENT_MAP[column_name]
    b_date = date.fromisoformat(date_str)

    # Xử lý các giá trị xóa / rỗng / NaN
    is_delete = False
    new_qty: Optional[float] = None

    if new_value is None or pd.isna(new_value):
        is_delete = True
    else:
        s_val = str(new_value).strip().lower()
        if s_val in ("", "—", "-", "none", "nan", "null", "xóa", "delete"):
            is_delete = True
        else:
            try:
                new_qty = float(s_val.replace(",", "."))
                if new_qty < 0:
                    return False, "Số lượng không thể âm."
                if new_qty == 0 and m_type == "OUT":
                    is_delete = True
            except ValueError:
                return False, f"Giá trị '{new_value}' không phải là số hợp lệ."

    db = SessionLocal()
    try:
        existing = db.query(DailyStockMovement).filter(
            DailyStockMovement.business_date == b_date,
            DailyStockMovement.ingredient_id == str(ingredient_id),
            DailyStockMovement.movement_type == m_type
        ).first()

        ing = db.query(Ingredient).filter(Ingredient.ingredient_id == str(ingredient_id)).first()
        ing_name = ing.ingredient_name if ing else f"Mã {ingredient_id}"

        if is_delete or new_qty is None:
            if existing:
                db.delete(existing)
                db.commit()
                return True, f"Đã xóa dữ liệu ô '{column_name}' của '{ing_name}'."
            return True, f"Ô '{column_name}' của '{ing_name}' hiện đã trống."
        else:
            if existing:
                existing.quantity = new_qty
                existing.status = "APPROVED"
                existing.approved_by = updated_by
                existing.approved_at = datetime.now()
                existing.notes = f"Sửa trực tiếp bằng tay bởi {updated_by}"
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
                    notes=f"Nhập trực tiếp bằng tay bởi {updated_by}"
                )
                db.add(new_rec)
            db.commit()
            return True, f"Đã lưu giá trị {new_qty:g} vào ô '{column_name}' của '{ing_name}'."
    except Exception as e:
        db.rollback()
        return False, f"Lỗi cập nhật: {str(e)}"
    finally:
        db.close()


def update_stock_matrix_from_editor(
    edited_df: pd.DataFrame,
    original_df: pd.DataFrame,
    updated_by: str = "admin",
    editor_session_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Cập nhật hàng loạt các thay đổi từ bảng chỉnh sửa trực tiếp (st.data_editor).
    Hỗ trợ đọc trực tiếp delta từ st.session_state[editor_key]['edited_rows'] và so sánh DataFrame.
    """
    updated_count = 0
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
                if col_name not in COLUMN_TO_MOVEMENT_MAP:
                    continue
                ok, msg = update_stock_cell_manually(ing_id, col_name, val_new, updated_by)
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
                if col_name not in COLUMN_TO_MOVEMENT_MAP:
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

                ok, msg = update_stock_cell_manually(ing_id, col_name, val_new, updated_by)
                if ok:
                    updated_count += 1
                else:
                    errors.append(msg)

    return {
        "status": "SUCCESS" if not errors else "PARTIAL",
        "updated_count": updated_count,
        "errors": errors
    }


def get_stock_matrix_df(year: int = 2026, month: int = 10) -> pd.DataFrame:
    """Tạo bảng ma trận Xuất - Nhập - Tồn kho ĐẦY ĐỦ 31 NGÀY tháng 10/2026.
    Chỉ tổng hợp các giao dịch đã được Quản lý duyệt (status == 'APPROVED').
    """
    db = SessionLocal()
    try:
        ings = db.query(Ingredient).order_by(Ingredient.ingredient_id).all()
        ing_map = {i.ingredient_id: i.ingredient_name for i in ings}

        rows = []
        for idx, item in enumerate(SAMPLE_OCTOBER_DATA, 1):
            ing_id = item["ing_id"]
            name = ing_map.get(ing_id, item["name"])

            # 1. Tồn đầu kỳ
            init_rec = db.query(DailyStockMovement).filter(
                DailyStockMovement.ingredient_id == ing_id,
                DailyStockMovement.movement_type == "INITIAL",
                DailyStockMovement.status == "APPROVED"
            ).first()
            ton_dau = float(init_rec.quantity) if init_rec else item["initial"]

            # 2. Toàn bộ giao dịch APPROVED
            approved_movs = db.query(DailyStockMovement).filter(
                DailyStockMovement.ingredient_id == ing_id,
                DailyStockMovement.status == "APPROVED"
            ).all()

            in_by_date: Dict[str, float] = {}
            out_by_date: Dict[str, float] = {}
            for m in approved_movs:
                d_str = m.business_date.strftime("%Y-%m-%d")
                if m.movement_type == "IN":
                    in_by_date[d_str] = in_by_date.get(d_str, 0.0) + float(m.quantity)
                elif m.movement_type == "OUT":
                    out_by_date[d_str] = out_by_date.get(d_str, 0.0) + float(m.quantity)

            # --- Tuần 1: 01/10 - 04/10 ---
            nhap_w1 = in_by_date.get("2026-10-01", 0.0)
            out_01 = out_by_date.get("2026-10-01", 0.0)
            out_02 = out_by_date.get("2026-10-02", 0.0)
            out_03 = out_by_date.get("2026-10-03", 0.0)
            out_04 = out_by_date.get("2026-10-04", 0.0)
            xuat_w1 = out_01 + out_02 + out_03 + out_04
            ton_w1 = ton_dau + nhap_w1 - xuat_w1

            # --- Tuần 2: 05/10 - 11/10 ---
            out_05 = out_by_date.get("2026-10-05", 0.0)
            out_06 = out_by_date.get("2026-10-06", 0.0)
            out_07 = out_by_date.get("2026-10-07", 0.0)
            out_08 = out_by_date.get("2026-10-08", 0.0)
            out_09 = out_by_date.get("2026-10-09", 0.0)
            out_10 = out_by_date.get("2026-10-10", 0.0)
            out_11 = out_by_date.get("2026-10-11", 0.0)
            xuat_w2 = out_05 + out_06 + out_07 + out_08 + out_09 + out_10 + out_11
            ton_w2 = ton_w1 - xuat_w2

            # --- Tuần 3: 12/10 - 18/10 ---
            nhap_w3 = in_by_date.get("2026-10-12", 0.0)
            out_12 = out_by_date.get("2026-10-12", 0.0)
            out_13 = out_by_date.get("2026-10-13", 0.0)
            out_14 = out_by_date.get("2026-10-14", 0.0)
            out_15 = out_by_date.get("2026-10-15", 0.0)
            out_16 = out_by_date.get("2026-10-16", 0.0)
            out_17 = out_by_date.get("2026-10-17", 0.0)
            out_18 = out_by_date.get("2026-10-18", 0.0)
            xuat_w3 = out_12 + out_13 + out_14 + out_15 + out_16 + out_17 + out_18
            ton_w3 = ton_w2 + nhap_w3 - xuat_w3

            # --- Tuần 4: 19/10 - 25/10 ---
            nhap_w4 = in_by_date.get("2026-10-19", 0.0)
            out_19 = out_by_date.get("2026-10-19", 0.0)
            out_20 = out_by_date.get("2026-10-20", 0.0)
            out_21 = out_by_date.get("2026-10-21", 0.0)
            out_22 = out_by_date.get("2026-10-22", 0.0)
            out_23 = out_by_date.get("2026-10-23", 0.0)
            out_24 = out_by_date.get("2026-10-24", 0.0)
            out_25 = out_by_date.get("2026-10-25", 0.0)
            xuat_w4 = out_19 + out_20 + out_21 + out_22 + out_23 + out_24 + out_25
            ton_w4 = ton_w3 + nhap_w4 - xuat_w4

            # --- Tuần 5: 26/10 - 31/10 ---
            out_26 = out_by_date.get("2026-10-26", 0.0)
            out_27 = out_by_date.get("2026-10-27", 0.0)
            out_28 = out_by_date.get("2026-10-28", 0.0)
            out_29 = out_by_date.get("2026-10-29", 0.0)
            out_30 = out_by_date.get("2026-10-30", 0.0)
            out_31 = out_by_date.get("2026-10-31", 0.0)
            xuat_w5 = out_26 + out_27 + out_28 + out_29 + out_30 + out_31

            # Tổng hợp cả tháng trong thời gian thực (Real-time)
            tong_nhap = sum(in_by_date.values())
            tong_xuat = sum(out_by_date.values())
            ton_so_sach = ton_dau + tong_nhap - tong_xuat

            # Tồn thực tế kiểm kê: CHỈ hiển thị nếu có phiếu kiểm kê ACTUAL_COUNT được duyệt!
            actual_rec = db.query(DailyStockMovement).filter(
                DailyStockMovement.ingredient_id == ing_id,
                DailyStockMovement.movement_type == "ACTUAL_COUNT",
                DailyStockMovement.status == "APPROVED"
            ).order_by(DailyStockMovement.business_date.desc(), DailyStockMovement.id.desc()).first()

            if actual_rec is not None:
                ton_thuc_te = int(float(actual_rec.quantity)) if float(actual_rec.quantity) == int(float(actual_rec.quantity)) else float(actual_rec.quantity)
                diff = float(actual_rec.quantity) - ton_so_sach
                chenh_lech = int(diff) if diff == int(diff) else diff
            else:
                # Chưa có kiểm kê thực tế -> để "—", tuyệt đối không điền bừa
                ton_thuc_te = "—"
                chenh_lech = "—"

            def _c(v: float, is_import: bool = False, keep_zero: bool = False) -> Any:
                if v == 0:
                    return 0 if keep_zero else ""
                return int(v) if v == int(v) else v

            def _n(v: float) -> Any:
                return int(v) if v == int(v) else v

            keep_zero_nhap1 = (ing_id in ("1", "4") and nhap_w1 == 0)

            row = {
                "STT": item.get("stt", idx),
                "Mã NL": ing_id,
                "Tên mặt hàng (Quy cách)": name,
                "Tồn T9": _n(ton_dau),
                # Tuần 1 (01/10 - 04/10)
                "Nhập 1/10": _c(nhap_w1, is_import=True, keep_zero=keep_zero_nhap1),
                "T5 1/10": _c(out_01),
                "T6 2/10": _c(out_02),
                "T7 3/10": _c(out_03),
                "CN 4/10": _c(out_04),
                "Tồn T1": _n(ton_w1),
                # Tuần 2 (05/10 - 11/10)
                "T2 5/10": _c(out_05),
                "T3 6/10": _c(out_06),
                "T4 7/10": _c(out_07),
                "T5 8/10": _c(out_08),
                "T6 9/10": _c(out_09),
                "T7 10/10": _c(out_10),
                "CN 11/10": _c(out_11),
                "Tồn T2": _n(ton_w2),
                # Tuần 3 (12/10 - 18/10)
                "Nhập 12/10": _c(nhap_w3, is_import=True),
                "T2 12/10": _c(out_12),
                "T3 13/10": _c(out_13),
                "T4 14/10": _c(out_14),
                "T5 15/10": _c(out_15),
                "T6 16/10": _c(out_16),
                "T7 17/10": _c(out_17),
                "CN 18/10": _c(out_18),
                "Tồn T3": _n(ton_w3),
                # Tuần 4 (19/10 - 25/10)
                "Nhập 19/10": _c(nhap_w4, is_import=True),
                "T2 19/10": _c(out_19),
                "T3 20/10": _c(out_20),
                "T4 21/10": _c(out_21),
                "T5 22/10": _c(out_22),
                "T6 23/10": _c(out_23),
                "T7 24/10": _c(out_24),
                "CN 25/10": _c(out_25),
                "Tồn T4": _n(ton_w4) if (nhap_w4 > 0 or xuat_w4 > 0) else "",
                # Tuần 5 (26/10 - 31/10)
                "T2 26/10": _c(out_26),
                "T3 27/10": _c(out_27),
                "T4 28/10": _c(out_28),
                "T5 29/10": _c(out_29),
                "T6 30/10": _c(out_30),
                "T7 31/10": _c(out_31),
                # Cuối tháng
                "Tổng nhập": _n(tong_nhap),
                "Tổng xuất": _n(tong_xuat),
                "Tồn sổ sách": _n(ton_so_sach),
                "Tồn thực tế": ton_thuc_te,
                "Chênh lệch": chenh_lech
            }
            rows.append(row)

        return pd.DataFrame(rows)
    finally:
        db.close()


def generate_excel_export() -> bytes:
    """Tạo file Excel ĐẦY ĐỦ 31 NGÀY THÁNG 10/2026 chuẩn màu sắc Google Sheets."""
    df = get_stock_matrix_df(2026, 10)

    wb = Workbook()
    ws = wb.active
    ws.title = "Kho tháng 10-2026"

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
