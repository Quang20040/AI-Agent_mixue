# BÁO CÁO CẢI TIẾN TẦNG BACKEND & SERVICE ENGINES
## BeverageOps AI — Quản Trị Vận Hành Chi Nhánh Mixue 39 Tôn Quang Phiệt

---

### 1. KIẾN TRÚC ĐỘNG CƠ DỰ BÁO (FORECASTING ENGINE ARCHITECTURE)

#### 1.1. Tối ưu cấu trúc tra cứu dữ liệu O(1)
Trong `src/engine/forecasting.py`:
- **Trước đây:** Mỗi khi hàm tính toán sai số hoặc dự báo cho một SKU, mã nguồn thực hiện:
  ```python
  sku_df = self.sales_df[self.sales_df["sku_name"] == sku].sort_values("date")
  ```
  Thao tác này lọc toàn phần trên tập dữ liệu hàng nghìn dòng, chi phí tính toán là $O(N)$ cho mỗi lần gọi. Trong quá trình backtest 77 ngày cho 24 SKUs, phép toán lọc diễn ra 1,848 lần, dẫn đến thời gian xử lý kéo dài hơn 14 giây.
- **Cải tiến:** Ngay tại thời điểm nạp dữ liệu (`_load_sales_data`), hệ thống tiền xử lý và lập chỉ mục sẵn toàn bộ chuỗi số lượng bán theo từng SKU vào một dictionary:
  ```python
  self._sku_series = {}
  for sku in self.skus:
      sku_df = self.sales_df[self.sales_df["sku_name"] == sku].sort_values("date")
      self._sku_series[sku] = sku_df["quantity"].to_numpy()
  ```
  Khi thực hiện backtest hoặc dự báo, hệ thống chỉ cần truy xuất `self._sku_series[sku][idx]`, đạt độ phức tạp thời gian tuyệt đối **$O(1)$**.

#### 1.2. Cơ chế đệm đa tầng (Multi-level Deterministic Cache)
- Hệ thống bổ sung hai bộ đệm bộ nhớ:
  1. `_backtest_cache`: Đệm kết quả kiểm chứng mô hình theo tham số `start_eval_day`.
  2. `_forecast_cache`: Đệm dự báo số lượng theo cặp khoá `(target_date, model_name)`.
- Nhờ cơ chế này, các cuộc gọi lặp lại từ giao diện Streamlit hoặc từ AI Agent được đáp ứng trong **< 0.05 giây** thay vì 14 giây.

---

### 2. DỊCH VỤ SỔ KHO HÀNG NGÀY & MAKER-CHECKER (DAILY STOCK SERVICE)

#### 2.1. Phân quyền nghiệp vụ Maker-Checker
Tại `src/engine/daily_stock_service.py`:
- Nhân viên chính thức (`STAFF`) chỉ có quyền tạo yêu cầu lệnh kho (`movement_type`: `IN` / `OUT` / `ACTUAL_COUNT`). Lệnh được khởi tạo ở trạng thái `PENDING`.
- Quản lý (`ADMIN`) có quyền duyệt (`APPROVED`) hoặc từ chối (`REJECTED`) kèm lý do từ chối.
- Khi lệnh được duyệt, số liệu tự động phản ánh vào ma trận xuất nhập tồn và tính toán lại tồn sổ sách cho toàn bộ 31 ngày trong tháng.

#### 2.2. Kiểm soát lũy biến (Idempotency Keying)
- Thêm lớp bảo vệ chống gửi lệnh trùng lặp trong 3 giây tại hàm `create_stock_request`:
  - Khóa kiểm tra: `(business_date, ingredient_id, movement_type, recorded_by, quantity)`.
  - Cửa sổ thời gian: `created_at >= datetime.now() - timedelta(seconds=3)`.
  - Trả về mã trạng thái `DUPLICATE` kèm thông điệp cảnh báo thân thiện, ngăn ngừa sai lệch dữ liệu kho do giật lag mạng.

---

### 3. DỊCH VỤ ĐÓNG CA & ĐỐI SOÁT TÀI CHÍNH (SHIFT CLOSING SERVICE)

#### 3.1. Bảo toàn thuộc tính mở rộng (Safe Property Merging)
Tại `src/engine/shift_service.py`:
- Hàm `save_or_update_shift_report` được tái cấu trúc hoàn toàn. Thay vì thay thế đối tượng cũ trong danh sách JSON, hàm sao chép bản ghi hiện tại và cập nhật các trường mới thông qua `.update(report_dict)`.
- Bảo toàn tuyệt đối các trường thông tin mở rộng:
  - `pos_collected_vnd`: Doanh thu đối soát từ hệ thống POS Mixue.
  - `variance_pos_vnd`: Chênh lệch giữa tiền thực thu tại ca và máy POS.
  - `reconciliation_status`: Trạng thái đối soát (`KHỚP TUYỆT ĐỐI`, `KHỚP LỆCH NHẸ`, `LỆCH CẦN GIẢI TRÌNH`).
  - `signed_by`: Chữ ký số / tên người lập báo cáo ca.

---

### 4. ĐỘNG CƠ XÁC THỰC KẾ HOẠCH ĐỘC LẬP (INDEPENDENT PLAN VALIDATOR)

Tại `src/engine/validator.py`:
- Áp dụng các quy tắc kiểm soát nghiêm ngặt theo Architectural Decision Records (ADR-005, ADR-006):
  1. Kiểm tra không âm: Số lượng pha chế và đặt hàng phải $> 0$.
  2. Kiểm tra đơn vị chuẩn: Chỉ chấp nhận các đơn vị `{"g", "ml", "pcs", "cái"}` (`ALLOWED_UNITS: ClassVar[set[str]]`).
  3. Làm tròn mẻ chuẩn (Batch Size Rounding): Định lượng topping phải là bội số nguyên của kích thước mẻ nấu (ví dụ: Trân châu đường đen 1 mẻ = 1,000g).
  4. Làm tròn kiện chuẩn (Pack Size Rounding): Đơn đặt hàng bổ sung PO phải là bội số nguyên của quy cách đóng gói (thùng/kiện/bình).
  5. Ràng buộc Human-in-the-loop: Toàn bộ đề xuất từ AI Agent bắt buộc phải có cờ `requires_manager_approval = True`.
