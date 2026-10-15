"""Kiểm thử tự động tính năng Quản lý nhân viên & Luồng đổi mật khẩu 6 số bắt buộc."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from src.auth import (
    change_user_password,
    create_employee,
    get_all_employees,
    is_staff_role,
    reset_employee_password,
    verify_user,
)
from src.database import SessionLocal
from src.models import User


@pytest.fixture(autouse=True)
def cleanup_test_staff():
    """Tự động dọn dẹp các tài khoản test trước và sau mỗi test case."""
    db = SessionLocal()
    db.query(User).filter(User.username.like("test_staff_%")).delete(synchronize_session=False)
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(User).filter(User.username.like("test_staff_%")).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_create_employee_flow():
    """Kiểm tra tạo nhân viên mới: MK mặc định 123456 và cờ must_change_password = True."""
    test_user = "test_staff_99"
    ok, msg = create_employee(
        admin_username="quanly",
        username=test_user,
        full_name="Nguyễn Văn Test",
        phone="0999888777",
        role="STAFF_PROBATION"
    )
    assert ok is True
    assert "thành công" in msg

    # Kiểm tra đăng nhập với pass mặc định 123456
    user_info = verify_user(test_user, "123456")
    assert user_info is not None
    assert user_info["username"] == test_user
    assert user_info["must_change_password"] is True
    assert is_staff_role(user_info["role"]) is True


def test_password_change_validation():
    """Kiểm tra quy tắc mật khẩu mới: bắt buộc đúng 6 chữ số và khác 123456."""
    test_user = "test_staff_99"
    create_employee("quanly", test_user, "Nguyễn Văn Test", "0999888777", "STAFF_PROBATION")

    # 1. Sai độ dài / có chữ -> Thất bại
    ok1, msg1 = change_user_password(test_user, "123456", "abc123")
    assert ok1 is False
    assert "6 chữ số" in msg1

    ok2, msg2 = change_user_password(test_user, "123456", "12345")  # 5 số
    assert ok2 is False
    assert "6 chữ số" in msg2

    # 2. Trùng mật khẩu mặc định 123456 -> Thất bại
    ok3, msg3 = change_user_password(test_user, "123456", "123456")
    assert ok3 is False
    assert "không được trùng với mật khẩu mặc định" in msg3

    # 3. Mật khẩu 6 số hợp lệ -> Thành công
    ok4, msg4 = change_user_password(test_user, "123456", "686868")
    assert ok4 is True
    assert "thành công" in msg4

    # Xác thực sau khi đổi thành công: cờ must_change_password phải chuyển sang False
    user_updated = verify_user(test_user, "686868")
    assert user_updated is not None
    assert user_updated["must_change_password"] is False


def test_admin_reset_password_flow():
    """Kiểm tra Admin reset mật khẩu nhân viên: về 123456 và kích hoạt lại cờ must_change_password."""
    test_user = "test_staff_99"
    create_employee("quanly", test_user, "Nguyễn Văn Test", "0999888777", "STAFF_PROBATION")
    # Đổi sang mật khẩu khác trước
    change_user_password(test_user, "123456", "686868")

    # Reset mật khẩu
    ok, msg = reset_employee_password(admin_username="quanly", target_username=test_user)
    assert ok is True
    assert "123456" in msg

    # Kiểm tra đăng nhập lại với 123456 và cờ must_change_password được bật lại
    user_reset = verify_user(test_user, "123456")
    assert user_reset is not None
    assert user_reset["must_change_password"] is True


def test_get_all_employees_includes_fields():
    """Kiểm tra hàm lấy danh sách nhân viên cho Admin view."""
    employees = get_all_employees()
    assert len(employees) >= 4
    sample = employees[0]
    for key in ["username", "full_name", "role", "role_badge", "must_change_password", "is_active"]:
        assert key in sample


def test_daily_stock_matrix_and_export():
    """Kiểm tra ghi nhận xuất/nhập kho và xuất file Excel ma trận kho."""
    from datetime import date

    from src.engine.daily_stock_service import (
        generate_excel_export,
        get_stock_matrix_df,
        record_daily_movement,
    )

    # Ghi nhận xuất kho
    res = record_daily_movement(
        business_date=date(2026, 10, 15),
        ingredient_id="1",
        movement_type="OUT",
        quantity=1.0,
        recorded_by="admin",
        notes="Khui ốc quế quầy bar"
    )
    assert res["status"] == "SUCCESS"

    # Lấy ma trận
    df = get_stock_matrix_df(2026, 10)
    assert len(df) >= 10
    assert "Tên mặt hàng (Quy cách)" in df.columns
    assert "Tồn T9" in df.columns
    # Kiểm tra các cột 31 ngày và các tuần
    assert "T5 1/10" in df.columns
    assert "CN 4/10" in df.columns
    assert "Tồn T1" in df.columns
    assert "Tồn T2" in df.columns
    assert "Tồn T3" in df.columns
    assert "Tồn T4" in df.columns
    assert "T7 31/10" in df.columns
    assert "Tổng nhập" in df.columns
    assert "Tổng xuất" in df.columns
    assert "Tồn sổ sách" in df.columns

    # Xuất Excel
    excel_bytes = generate_excel_export()
    assert len(excel_bytes) > 1000


def test_maker_checker_stock_approval_workflow():
    """Kiểm tra quy trình kiểm soát kho 2 bước (Nhân viên đề xuất -> Quản lý duyệt)."""
    from datetime import date

    from src.engine.daily_stock_service import (
        approve_stock_request,
        create_stock_request,
        get_pending_requests,
        get_user_requests,
        reject_stock_request,
    )

    # 1. Nhân viên chính thức tạo đề xuất lệnh xuất kho
    req_res = create_stock_request(
        business_date=date(2026, 10, 20),
        ingredient_id="2",
        movement_type="OUT",
        quantity=3.0,
        recorded_by="nhanvien",
        user_role="STAFF",
        notes="Ca sáng khui bột kem"
    )
    assert req_res["status"] == "SUCCESS"
    assert req_res["is_approved"] is False
    req_id = req_res["request_id"]

    # 2. Kiểm tra lệnh xuất hiện trong danh sách PENDING của Quản lý
    pending = get_pending_requests()
    pending_ids = [p["id"] for p in pending]
    assert req_id in pending_ids

    # 3. Kiểm tra danh sách lệnh của nhân viên hiển thị trạng thái chờ duyệt
    user_reqs = get_user_requests(username="nhanvien")
    matching = [r for r in user_reqs if r["Mã lệnh"] == f"#{req_id}"]
    assert len(matching) == 1
    assert "Chờ Quản lý duyệt" in matching[0]["Trạng thái"]

    # 4. Quản lý duyệt lệnh
    ok, msg = approve_stock_request(request_id=req_id, admin_username="quanly")
    assert ok is True
    assert "phê duyệt" in msg.lower()

    # 5. Sau khi duyệt, lệnh không còn trong hòm thư PENDING
    pending_after = get_pending_requests()
    assert req_id not in [p["id"] for p in pending_after]

    # 6. Kiểm tra lại lịch sử lệnh của nhân viên đã chuyển thành 'Đã duyệt'
    user_reqs_after = get_user_requests(username="nhanvien")
    matching_after = [r for r in user_reqs_after if r["Mã lệnh"] == f"#{req_id}"]
    assert "Đã duyệt ghi sổ" in matching_after[0]["Trạng thái"]

    # 7. Thử quy trình từ chối lệnh (Reject)
    req_rej = create_stock_request(
        business_date=date(2026, 10, 21),
        ingredient_id="3",
        movement_type="IN",
        quantity=99.0,
        recorded_by="nhanvien",
        user_role="STAFF",
        notes="Nhập nhầm số lượng"
    )
    rej_id = req_rej["request_id"]
    ok_rej, msg_rej = reject_stock_request(request_id=rej_id, admin_username="quanly", reason="Số lượng sai")
    assert ok_rej is True
    assert "từ chối" in msg_rej.lower()

    # Lệnh bị từ chối không có trong pending
    assert rej_id not in [p["id"] for p in get_pending_requests()]
    # Và hiển thị 'Đã từ chối' trong lịch sử
    user_reqs_rej = get_user_requests(username="nhanvien")
    rej_matching = [r for r in user_reqs_rej if r["Mã lệnh"] == f"#{rej_id}"]
    assert "Đã từ chối" in rej_matching[0]["Trạng thái"]


def test_manual_stock_editing_and_batch_editor():
    """Kiểm tra chức năng sửa số liệu kho trực tiếp bằng tay (từng ô và cả bảng editor)."""
    from src.engine.daily_stock_service import (
        get_stock_matrix_df,
        update_stock_cell_manually,
        update_stock_matrix_from_editor,
    )

    # 1. Sửa bằng tay 1 ô: Cập nhật T5 1/10 cho Ốc quế (Mã 1) thành 3.0
    ok, msg = update_stock_cell_manually(
        ingredient_id="1",
        column_name="T5 1/10",
        new_value="3",
        updated_by="quanly"
    )
    assert ok is True
    assert "3" in msg

    # Kiểm tra ma trận phản ánh số 3
    df1 = get_stock_matrix_df(2026, 10)
    row_ocque = df1[df1["Mã NL"] == "1"].iloc[0]
    assert row_ocque["T5 1/10"] == 3

    # 2. Sửa bằng tay Tồn thực tế kiểm kê thành 5
    ok_count, msg_count = update_stock_cell_manually(
        ingredient_id="1",
        column_name="Tồn thực tế",
        new_value="5",
        updated_by="quanly"
    )
    assert ok_count is True
    df_count = get_stock_matrix_df(2026, 10)
    row_count = df_count[df_count["Mã NL"] == "1"].iloc[0]
    assert row_count["Tồn thực tế"] == 5
    assert row_count["Chênh lệch"] != "—"

    # 3. Test sửa hàng loạt từ editor
    df_original = get_stock_matrix_df(2026, 10)
    df_edited = df_original.copy()
    # Giả lập người dùng gõ sửa ô T3 13/10 của Bột trà sữa (Mã 3) thành 2
    row_idx = df_edited[df_edited["Mã NL"] == "3"].index[0]
    df_edited.at[row_idx, "T3 13/10"] = 2

    res_batch = update_stock_matrix_from_editor(df_edited, df_original, updated_by="chucuahang")
    assert res_batch["status"] == "SUCCESS"
    assert res_batch["updated_count"] >= 1

    # Kiểm tra lại DB sau khi lưu batch editor
    df_after_batch = get_stock_matrix_df(2026, 10)
    row_trasua = df_after_batch[df_after_batch["Mã NL"] == "3"].iloc[0]
    assert row_trasua["T3 13/10"] == 2

    # 4. Trả lại giá trị ban đầu cho Ốc quế và Bột trà sữa
    update_stock_cell_manually("1", "T5 1/10", "1", "quanly")
    update_stock_cell_manually("1", "Tồn thực tế", "", "quanly")
    update_stock_cell_manually("3", "T3 13/10", "1", "quanly")

