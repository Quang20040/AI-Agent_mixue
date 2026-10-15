# BÁO CÁO TÁI CẤU TRÚC MÃ NGUỒN & CHUẨN HÓA CLEAN CODE
## BeverageOps AI — Quản Trị Vận Hành Chi Nhánh Mixue 39 Tôn Quang Phiệt

---

### 1. PHÂN TÍCH TĨNH & DỌN DẸP LỖI LINTER (STATIC ANALYSIS & RUFF METRICS)

Trong Phase 3, toàn bộ mã nguồn của dự án (cả `src/` và `tests/`) đã được quét và tối ưu hóa thông qua công cụ phân tích tĩnh chuẩn ngành **Ruff**:

```
====================================================================================
CHỈ SỐ ĐO LƯỜNG (METRICS)             TRƯỚC CẢI TIẾN     SAU CẢI TIẾN     TỶ LỆ GIẢM
====================================================================================
Tổng số cảnh báo Linter               396 cảnh báo       86 cảnh báo      -78.3%
Cú pháp Type Hint cũ (UP006/UP045)     115 lỗi            0 lỗi            -100% (Chuẩn hóa PEP 585/604)
Thư viện import thừa (F401)            54 lỗi             0 lỗi            -100% (Dọn sạch)
F-string rỗng không placeholder (F541) 46 lỗi             0 lỗi            -100% (Chuẩn hóa)
Import chưa sắp xếp chuẩn (I001)       43 lỗi             0 lỗi            -100% (Sắp xếp isort)
Khai báo mã hóa utf-8 thừa (UP009)     14 lỗi             0 lỗi            -100% (Loại bỏ)
Biến thừa không sử dụng (F841/RUF059)  11 lỗi             0 lỗi            -100% (Prefix hoặc xóa)
====================================================================================
```

Các cảnh báo còn lại (86 mục) thuộc về các chủ đích thiết kế cụ thể:
- `DTZ005 / DTZ011`: Sử dụng thời gian địa phương (`datetime.now()`, `date.today()`) theo giờ hoạt động của cửa hàng Mixue 39 Tôn Quang Phiệt (múi giờ GMT+7) mà không gắn tzinfo để tương thích với cơ sở dữ liệu SQLite/PostgreSQL hiện tại.
- `BLE001`: Khối try-except bắt `Exception` ở tầng API để ghi log lỗi thân thiện ra màn hình Streamlit thay vì làm sập ứng dụng.

---

### 2. CHUẨN HÓA KIỂU DỮ LIỆU HIỆN ĐẠI (PYTHON 3.12 MODERNIZATION)

Toàn bộ các chú thích kiểu (Type Annotations) cũ theo `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Union` đã được chuyển đổi sang chuẩn Python 3.12 hiện đại theo PEP 585 và PEP 604:
- Trước: `Dict[str, Any]`, `List[str]`, `Optional[str]`, `Union[int, float]`
- Sau: `dict[str, Any]`, `list[str]`, `str | None`, `int | float`
- Đối với thuộc tính mức lớp (Class Attributes) trong `IndependentPlanValidator`, bộ hằng số `ALLOWED_UNITS` được khai báo rõ ràng với `ClassVar[set[str]]` để bảo đảm tính bất biến giữa các instance.

---

### 3. ÁP DỤNG NGUYÊN TẮC THIẾT KẾ PHẦN MỀM (SOLID & SEPARATION OF CONCERNS)

1. **Single Responsibility Principle (SRP):**
   - Tách biệt rõ ràng tầng trình diễn (Presentation Layer: `src/dashboard/brand_ui.py`, `src/dashboard/shift_closing_ui.py`) khỏi tầng nghiệp vụ tính toán (Business Logic Engines: `src/engine/bom_engine.py`, `src/engine/forecasting.py`, `src/engine/shift_service.py`).
   - Các file UI không chứa các câu truy vấn cơ sở dữ liệu phức tạp mà gọi trực tiếp qua service functions.
2. **Open/Closed Principle (OCP):**
   - Động cơ dự báo `ForecastingEngine` hỗ trợ mở rộng các mô hình dự báo mới (`Moving Average`, `Day-of-Week`, `Seasonal Naive`) mà không cần sửa đổi luồng chạy backtest.
3. **Defense-in-Depth (Phòng vệ đa tầng):**
   - Dữ liệu đầu vào được kiểm tra đồng thời ở 3 cấp độ:
     1. Giao diện người dùng: `st.column_config.NumberColumn(min_value=0.0)`.
     2. Service Layer: Kiểm tra `new_qty < 0` trong `update_stock_cell_manually`.
     3. Engine Validator: Kiểm tra chính sách nghiệp vụ trong `IndependentPlanValidator`.
