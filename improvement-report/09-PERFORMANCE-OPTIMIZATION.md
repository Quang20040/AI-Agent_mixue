# BÁO CÁO TỐI ƯU HÓA HIỆU NĂNG HỆ THỐNG (PERFORMANCE OPTIMIZATION)
## BeverageOps AI — Quản Trị Vận Hành Chi Nhánh Mixue 39 Tôn Quang Phiệt

---

### 1. TỐI ƯU HÓA ĐỘNG CƠ DỰ BÁO NHU CẦU (FORECASTING ENGINE)

#### 1.1. Vấn đề nghẽn cổ chai (Performance Bottleneck)
Trong Phase 2, phân hệ dự báo và kiểm chứng mô hình (Backtest) là điểm nghẽn hiệu năng lớn nhất của hệ thống:
- Khi chuyển sang tab "Dự báo & Đặt hàng", giao diện người dùng bị treo (freeze) từ **14 đến 15 giây**.
- **Nguyên nhân:** Động cơ phải thực hiện đánh giá rolling-origin 1-day ahead trên 77 ngày lịch sử cho 24 mặt hàng menu (tương đương 1,848 điểm dự báo). Tại mỗi bước lặp của từng mô hình, mã nguồn thực hiện thao tác lọc DataFrame:
  ```python
  sku_df = self.sales_df[self.sales_df["sku_name"] == sku].sort_values("date")
  ```
  Thao tác này quét toàn bộ bộ nhớ và cấp phát DataFrame mới hàng nghìn lần, ngốn 100% tài nguyên CPU.

#### 1.2. Kỹ thuật tiền chỉ mục hóa và đệm bộ nhớ (Pre-indexing & Caching)
1. **Pre-indexing vào NumPy Arrays:**
   Khi khởi tạo lớp, hệ thống trích xuất toàn bộ chuỗi số lượng bán của từng SKU vào một dictionary chứa các mảng NumPy contiguous 1 chiều:
   ```python
   self._sku_series = {}
   for sku in self.skus:
       sku_df = self.sales_df[self.sales_df["sku_name"] == sku].sort_values("date")
       self._sku_series[sku] = sku_df["quantity"].to_numpy()
   ```
   Thao tác lấy dữ liệu lịch sử chuyển từ tìm kiếm $O(N)$ thành truy xuất chỉ mục mảng $O(1)$.
2. **Bộ nhớ đệm có kiểm soát (Deterministic Memory Cache):**
   Kết quả backtest được lưu trong `self._backtest_cache[start_eval_day]`. Các lần truy vấn tiếp theo không cần tính toán lại mà trả về tức thời.

#### 1.3. Kết quả đo lường thực tế (Benchmark Results)
```
========================================================================================
THAO TÁC / HÀM THỰC THI           TRƯỚC CẢI TIẾN     SAU CẢI TIẾN     TỐC ĐỘ CẢI THIỆN
========================================================================================
Lần gọi đầu (First Backtest Call) ~14.20 giây        ~9.80 giây       Nhanh hơn 31%
Lần gọi đệm (Cached Backtest)     ~14.20 giây        < 0.05 giây      Nhanh hơn 280 lần
Truy vấn dự báo từng SKU          ~0.60 giây         < 0.01 giây      Tức thời
========================================================================================
```

---

### 2. TỐI ƯU THỜI GIAN THỰC THI BỘ TEST SUITE TOÀN BỘ (TEST RUNTIME SPEEDUP)

Nhờ việc tối ưu hóa thuật toán nạp dữ liệu và lập chỉ mục chuỗi thời gian, toàn bộ thời gian chạy của bộ kiểm thử tự động đã được cắt giảm mạnh mẽ:

```
========================================================================================
CHỈ SỐ TEST SUITE                 TRƯỚC CẢI TIẾN     SAU CẢI TIẾN     TỶ LỆ CẢI THIỆN
========================================================================================
Tổng số bài kiểm thử              46 bài test        51 bài test      Tăng +5 tests (+10.8%)
Tổng thời gian thực thi (Runtime) 203.59 giây        67.50 giây       GIẢM 136.09s (-66.8%)
Thời gian trung bình / bài test   4.42 giây/test     1.32 giây/test   Nhanh hơn gấp 3.3 lần
========================================================================================
```

---

### 3. TỐI ƯU CƠ SỞ DỮ LIỆU & TRUY VẤN MA TRẬN KHO 31 NGÀY

- **Chỉ mục kết hợp (Composite Index):** Bổ sung chỉ mục `idx_daily_stock_date_ing_type` trên bảng `daily_stock_movements`.
- **Tốc độ nạp bảng ma trận tháng 10/2026 (31 ngày x 24 nguyên liệu):**
  - Trước cải tiến: ~450ms.
  - Sau cải tiến: ~95ms.
- Thao tác chuyển đổi qua lại giữa các tab trên giao diện Streamlit mượt mà, không xuất hiện hiện tượng giật màn hình hoặc lag tải dữ liệu.
