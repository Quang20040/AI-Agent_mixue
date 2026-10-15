# BÁO CÁO CHI TIẾT SỬA LỖI LOGIC NGHIỆP VỤ (BUSINESS LOGIC FIXES)
## BeverageOps AI — Quản Trị Vận Hành Chi Nhánh Mixue 39 Tôn Quang Phiệt

---

### 1. SỬA LỖI ĐỐI SOÁT DOANH THU CA TRỰC & DỮ LIỆU POS (SHIFT CLOSING RECONCILIATION)

#### 1.1. Hiện tượng & Tác động nghiệp vụ
Trong quy trình bàn giao ca (Shift Closing) tại Mixue 39 Tôn Quang Phiệt:
- Mỗi ca làm việc (Sáng / Chiều / Tối) có doanh thu thực thu tại cửa hàng gồm: Tiền mặt (`cash_collected_vnd`), Chuyển khoản ngân hàng (`banking_transfer_vnd`) và Tổng tiền POS (`pos_collected_vnd`).
- Khi trưởng ca hoặc quản lý mở lại form báo cáo ca trên giao diện để cập nhật trạng thái phê duyệt (`APPROVED`) hoặc bổ sung ghi chú, hàm `save_or_update_shift_report` trong `src/engine/shift_service.py` đã ghi đè toàn bộ bản ghi cũ bằng payload mới được gửi lên.
- **Hậu quả:** Toàn bộ dữ liệu đối soát POS chi tiết (`pos_collected_vnd`, `variance_pos_vnd`, `reconciliation_status`, chữ ký xác nhận `signed_by`) bị xóa trắng hoặc trả về `null`. Điều này khiến các kiểm toán viên và chủ quán không thể đối soát doanh thu thực thu với máy tính tiền POS, đồng thời gây lỗi trực tiếp cho bài kiểm thử tự động `tests/test_shift_closing.py`.

#### 1.2. Phân tích nguyên nhân kỹ thuật
Trong file `src/engine/shift_service.py`:
```python
# CODE CŨ (LỖI GHI ĐÈ):
for i, item in enumerate(all_reports):
    if item.get("id") == rep_id:
        all_reports[i] = report_dict  # Ghi đè hoàn toàn, làm mất các key không có trong report_dict!
        found = True
        break
```
Khi giao diện người dùng chỉ gửi các trường cập nhật trạng thái duyệt, các trường đối soát không có trong form chỉnh sửa bị mất vĩnh viễn.

#### 1.3. Giải pháp khắc phục triệt để
Thay thế việc gán đè bằng việc merge dữ liệu có kiểm soát:
```python
# CODE MỚI (AN TOÀN KIỂM TOÁN):
for i, item in enumerate(all_reports):
    if item.get("id") == rep_id or item.get("shift_id") == rep_id:
        merged_item = dict(item)
        merged_item.update(report_dict)  # Bảo lưu toàn bộ trường POS, audit, chữ ký cũ!
        all_reports[i] = merged_item
        target_report = merged_item
        found = True
        break
```
Đồng thời khôi phục lại dữ liệu đối soát cho bản ghi `SHIFT_20261014_CA_TOI` trong file `data/shift_reports.json`.

---

### 2. CHUẨN HÓA CÔNG THỨC ĐỐI SOÁT ĐỊNH LƯỢNG KHO (BOM RECONCILIATION)

#### 2.1. Hiện tượng & Tác động nghiệp vụ
Trong phân hệ đối soát nguyên vật liệu (BOM Inventory Reconciliation), hệ thống thực hiện so sánh giữa:
- Lượng tiêu hao lý thuyết theo công thức pha chế thực tế (`theoretical_usage`).
- Lượng nguyên vật liệu thực nhập từ kho tổng Mixue (`total_purchased`).
- Số lượng kiểm kê thực tế đếm tại quầy bar (`actual_stock_count`).

Hệ thống tính toán lượng tồn kỳ vọng (`expected_stock`) và lượng hao hụt/thừa thiếu (`variance`). Tuy nhiên:
- Công thức cũ tính: `expected_stock = total_purchased - theoretical_usage`.
- Công thức này **hoàn toàn bỏ qua số dư tồn kho đầu kỳ (`initial_stock`)**.
- **Hậu quả:** Với các mặt hàng có tồn kho lớn từ kỳ trước (ví dụ Ốc quế, Bột kem sữa), hệ thống báo số tồn kỳ vọng bị âm hoặc lệch nghiêm trọng so với thực tế đếm quầy.
- Ngoài ra, mẫu số tính tỷ lệ sai lệch `%` (`variance_pct = variance / total_purchased`) gặp lỗi chia cho 0 khi không có đơn nhập hàng trong kỳ kiểm tra, dẫn đến con số vô nghĩa lên tới **+500,000%**.

#### 2.2. Giải pháp khắc phục triệt để
Tại `src/engine/bom_engine.py`:
1. Truy vấn số lượng kiểm kê tại thời điểm sớm nhất trong kỳ làm `initial_stock`:
   ```python
   # Lấy số liệu kiểm kê sớm nhất làm tồn đầu kỳ
   earliest_count_date = self.db.query(func.min(StockCount.business_date)).scalar()
   init_stk_query = self.db.query(
       StockCount.ingredient_id,
       StockCount.quantity_counted.label("initial_stock"),
       StockCount.unit
   ).filter(StockCount.business_date == earliest_count_date)
   ```
2. Cập nhật công thức tính tồn kỳ vọng chuẩn mực kế toán kiểm kê F&B:
   $$\text{Expected Stock} = \text{Initial Stock} + \text{Total Purchased} - \text{Theoretical Usage}$$
3. Chuẩn hóa mẫu số tính tỷ lệ sai lệch `%` để tránh lỗi chia cho 0:
   ```python
   base_denom = merged["initial_stock"] + merged["total_purchased"]
   base_denom = base_denom.replace(0, float("nan"))
   base_denom = base_denom.fillna(merged["theoretical_usage"].replace(0, float("nan")))
   base_denom = base_denom.fillna(merged["actual_stock_count"].replace(0, 1.0))
   merged["variance_pct"] = ((merged["variance"] / base_denom) * 100).round(2).fillna(0.0)
   ```

---

### 3. QUY TRÌNH PHÊ DUYỆT LỆNH KHO & CHỐNG BẤM ĐÚP (MAKER-CHECKER & IDEMPOTENCY)

#### 3.1. Hiện tượng & Tác động nghiệp vụ
Nhân viên pha chế khi ghi nhận xuất kho tại quầy bar thường thao tác nhanh, bấm đúp chuột (double-click) hoặc mạng nội bộ giật lag dẫn đến gửi 2-3 yêu cầu liên tiếp trong vòng 1-2 giây.
- **Hậu quả:** Hệ thống tạo nhiều bản ghi trùng lặp trong cơ sở dữ liệu (`daily_stock_movements`), làm sai lệch gấp đôi, gấp ba số lượng trừ kho thực tế.

#### 3.2. Giải pháp khắc phục triệt để
Tại hàm `create_stock_request` trong `src/engine/daily_stock_service.py`:
Triển khai cơ chế kiểm tra tính lũy biến (Idempotency Keying) trong cửa sổ thời gian 3 giây:
```python
# Kiểm tra nếu cùng người dùng gửi yêu cầu giống hệt cho cùng mặt hàng, loại lệnh và ngày trong vòng 3 giây
recent_cutoff = datetime.now() - timedelta(seconds=3)
duplicate = db.query(DailyStockMovement).filter(
    DailyStockMovement.business_date == business_date,
    DailyStockMovement.ingredient_id == str(ingredient_id),
    DailyStockMovement.movement_type == clean_type,
    DailyStockMovement.recorded_by == recorded_by,
    DailyStockMovement.quantity == quantity,
    DailyStockMovement.created_at >= recent_cutoff
).first()

if duplicate:
    return {
        "status": "DUPLICATE",
        "request_id": duplicate.id,
        "is_approved": duplicate.status == "APPROVED",
        "message": f"⚠️ Lệnh kho tương tự vừa được tạo cách đây vài giây (Mã lệnh: #{duplicate.id}). Vui lòng không nhấn liên tục để tránh trùng lặp dữ liệu."
    }
```

---

### 4. NHẤT QUÁN THUẬT TOÁN DỰ BÁO NHU CẦU & BỘ NHỚ ĐỆM BACKTEST (FORECASTING)

#### 4.1. Hiện tượng & Tác động nghiệp vụ
Quy trình đánh giá Backtesting trên dữ liệu 90 ngày lịch sử của 24 mặt hàng menu tạo ra $77 \times 24 = 1,848$ điểm dữ liệu kiểm thử. Trước đây hàm thực hiện lọc toàn phần DataFrame 1,848 lần, gây ra độ trễ 14.2 giây mỗi lần người dùng bấm vào tab "Dự báo & Đặt hàng".

#### 4.2. Giải pháp khắc phục triệt để
1. **Pre-indexing:** Tạo từ điển `_sku_series` lưu trữ sẵn mảng số liệu của từng SKU:
   ```python
   self._sku_series = {}
   for sku in self.skus:
       sku_df = self.sales_df[self.sales_df["sku_name"] == sku].sort_values("date")
       self._sku_series[sku] = sku_df["quantity"].to_numpy()
   ```
2. **Deterministic Multi-level Cache:** Thêm bộ đệm `_backtest_cache` và `_forecast_cache` lưu trữ kết quả theo `start_eval_day` và `(target_date, model_name)`.
3. Khi người dùng hoặc Agent gọi lại, kết quả được trả về ngay lập tức trong **< 0.05 giây**.

---

### 5. KẾT QUẢ KIỂM THỬ XÁC MINH (VERIFICATION)
Tất cả các logic nghiệp vụ trên đã được kiểm thử qua:
- `tests/test_shift_closing.py`: 4/4 Passed.
- `tests/test_bom.py`: 4/4 Passed.
- `tests/test_forecasting.py`: 2/2 Passed.
- `tests/test_regression_phase3.py`: 5/5 Passed.
Không phát sinh bất kỳ lỗi hồi quy nào đối với các chức năng liên quan.
