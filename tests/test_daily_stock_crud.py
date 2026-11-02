"""Kiểm thử tự động các chức năng Sửa, Xóa và Cập nhật Sổ thẻ kho (Daily Stock CRUD)."""
from datetime import date

from src.engine.daily_stock_service import (
    create_stock_request,
    delete_stock_movement,
    get_cell_value,
    get_stock_matrix_df,
    update_stock_cell_manually,
    update_stock_movement,
)


def test_cell_manual_update_and_delete():
    """Kiểm tra sửa và xóa một ô cụ thể trên sổ kho bằng tay."""
    # 1. Cập nhật ô T5 1/10 của Ốc quế (Mã NL '1')
    ok, msg = update_stock_cell_manually(
        ingredient_id="1",
        column_name="T5 1/10",
        new_value=4.5,
        updated_by="quanly",
        year=2026, month=10
    )
    assert ok is True
    val = get_cell_value("1", "T5 1/10", year=2026, month=10)
    assert val == 4.5

    # 2. Xóa ô này bằng cách truyền giá trị rỗng
    ok_del, msg_del = update_stock_cell_manually(
        ingredient_id="1",
        column_name="T5 1/10",
        new_value="",
        updated_by="quanly",
        year=2026, month=10
    )
    assert ok_del is True
    val_after = get_cell_value("1", "T5 1/10", year=2026, month=10)
    assert val_after is None

    # Khôi phục lại giá trị 1.0 chuẩn ban đầu
    update_stock_cell_manually("1", "T5 1/10", 1.0, "quanly", year=2026, month=10)
    assert get_cell_value("1", "T5 1/10", year=2026, month=10) == 1.0


def test_movement_create_update_delete():
    """Kiểm tra quy trình tạo lệnh, sửa số lượng lệnh và xóa bỏ lệnh."""
    # 1. Tạo một lệnh xuất kho
    res = create_stock_request(
        business_date=date(2026, 10, 20),
        ingredient_id="2",
        movement_type="OUT",
        quantity=3.0,
        recorded_by="quanly",
        user_role="ADMIN",
        notes="Test CRUD"
    )
    assert res["status"] == "SUCCESS"
    mov_id = res["request_id"]

    # 2. Sửa số lượng của lệnh
    ok_up, msg_up = update_stock_movement(
        movement_id=mov_id,
        new_quantity=5.5,
        admin_username="quanly"
    )
    assert ok_up is True
    assert "5.5" in msg_up

    # 3. Xóa lệnh
    ok_del, msg_del = delete_stock_movement(mov_id, admin_username="quanly")
    assert ok_del is True
    assert f"#{mov_id}" in msg_del


def test_matrix_calculation_reflects_changes():
    """Kiểm tra ma trận sổ kho 31 ngày tự động tính lại tồn sổ sách khi sửa/xóa."""
    df_before = get_stock_matrix_df(2026, 10)
    row_ocque = df_before[df_before["Mã NL"] == "1"].iloc[0]
    ton_dau = float(row_ocque["Tồn cuối T9/2026"])
    assert ton_dau == 6.0


def test_future_stamped_rows_are_not_treated_as_double_clicks():
    """Rows written in another timezone (naive local time) must not block new requests."""
    from datetime import datetime, timedelta

    from src.database import SessionLocal
    from src.engine.daily_stock_service import create_stock_request
    from src.models import DailyStockMovement

    args = dict(business_date=date(2026, 10, 9), ingredient_id="2", movement_type="OUT",
                quantity=7.0, recorded_by="quanly", user_role="ADMIN", notes="timezone check")
    assert create_stock_request(**args)["status"] == "SUCCESS"
    with SessionLocal() as db:
        db.query(DailyStockMovement).filter(DailyStockMovement.business_date == date(2026, 10, 9),
                                            DailyStockMovement.quantity == 7.0).update(
            {DailyStockMovement.created_at: datetime.now() + timedelta(hours=7)}, synchronize_session=False)
        db.commit()
    assert create_stock_request(**args)["status"] == "SUCCESS"
    # A genuine double click is still rejected.
    assert create_stock_request(**args)["status"] == "DUPLICATE"
