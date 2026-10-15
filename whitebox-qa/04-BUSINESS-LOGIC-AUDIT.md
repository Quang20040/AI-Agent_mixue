# BÁO CÁO KIỂM TOÁN LOGIC NGHIỆP VỤ & THUẬT TOÁN (BUSINESS LOGIC AUDIT)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-04-BIZ`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Đánh giá tính chính xác toán học, biên sai số, quy tắc nghiệp vụ F&B và xử lý trường hợp biên (Edge Cases)

---

## 1. MA TRẬN ĐÁNH GIÁ THUẬT TOÁN NGHIỆP VỤ CỐT LÕI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CORE BUSINESS ALGORITHM AUDIT                           │
├────────────────────┬──────────────────────┬──────────┬──────────────────────┤
│ Thuật Toán / Module│ File Nguồn & Dòng    │ Trạng    │ Đánh Giá Kỹ Thuật    │
│                    │                      │ Thái     │                      │
├────────────────────┼──────────────────────┼──────────┼──────────────────────┤
│ 1. BOM Explosion   │ bom_engine.py:78-118 │ CHÍNH XÁC│ Tính tiêu hao lý     │
│                    │                      │          │ thuyết theo công thức│
├────────────────────┼──────────────────────┼──────────┼──────────────────────┤
│ 2. Inventory Recon │ bom_engine.py:150-185│ SAI LỆCH │ Thiếu Tồn đầu kỳ     │
│                    │                      │ (BUG)    │ (initial_stock)      │
├────────────────────┼──────────────────────┼──────────┼──────────────────────┤
│ 3. Demand Forecast │ forecasting.py:64-92 │ CHÍNH XÁC│ 3 mô hình chuẩn;     │
│                    │                      │          │ WAPE, MAE, Bias đúng │
├────────────────────┼──────────────────────┼──────────┼──────────────────────┤
│ 4. Topping Prep    │ optimizer.py:139-197 │ CHÍNH XÁC│ Làm tròn mẻ 1kg/5L;  │
│                    │                      │          │ Hạn dùng 4h chuẩn SOP│
├────────────────────┼──────────────────────┼──────────┼──────────────────────┤
│ 5. Replenishment PO│ optimizer.py:199-303 │ XUẤT SẮC │ Chuẩn quy cách thùng/│
│                    │                      │          │ kiện Master Mixue    │
├────────────────────┼──────────────────────┼──────────┼──────────────────────┤
│ 6. Policy Validator│ validator.py:38-160  │ XUẤT SẮC │ Chặn số âm, bội số,  │
│                    │                      │          │ đơn vị đo Zero-Trust │
├────────────────────┼──────────────────────┼──────────┼──────────────────────┤
│ 7. Maker-Checker   │ daily_stock_service  │ CÓ RỦI RO│ Thiếu Idempotency    │
│                    │ :240-289             │          │ (Trùng lặp khi click)│
├────────────────────┼──────────────────────┼──────────┼──────────────────────┤
│ 8. POS Shift Audit │ shift_service.py     │ SAI LỆCH │ Overwrite làm mất POS│
│                    │ :184-296             │ (BUG)    │ voucher discount data│
└────────────────────┴──────────────────────┴──────────┴──────────────────────┘
```

---

## 2. PHÂN TÍCH CHI TIẾT CÁC THUẬT TOÁN

### 2.1. BOM Explosion — Tính Tiêu Hao Nguyên Liệu Lý Thuyết
- **Vị trí mã nguồn:** [src/engine/bom_engine.py:78-118](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/bom_engine.py#L78-L118)
- **Công thức triển khai:**
  $$\text{Theoretical Usage}_i = \sum_{s \in \text{Sales}} (\text{Quantity Sold}_s \times \text{BOM Quantity}_{s, i})$$
- **Đánh giá:**
  - Logic INNER JOIN giữa `SalesDaily`, `MenuItem`, `RecipeBOM` và `Ingredient` được viết chính xác.
  - Phép nhân phân rã định lượng và làm tròn 2 chữ số thập phân (`round(2)`) phù hợp với các đơn vị cân đo gram (g) và mililit (ml).
- **Trường hợp biên (Edge Case):**
  - Nếu một món trong `sales_daily` không có công thức trong `recipe_bom`, món đó sẽ bị loại bỏ khỏi kết quả do sử dụng INNER JOIN (`join`). Hệ thống hiện chưa có cảnh báo (Warning log) cho các mã SKU thiếu BOM.

---

### 2.2. Đối Soát Tồn Kho & Chênh Lệch Kiểm Kê (Inventory Reconciliation) — LỖI NGHIỆP VỤ NGHIÊM TRỌNG
- **Vị trí mã nguồn:** [src/engine/bom_engine.py:180-184](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/bom_engine.py#L180-L184)
- **Đoạn mã hiện tại:**
  ```python
  merged["expected_stock"] = merged["total_purchased"] - merged["theoretical_usage"]
  merged["variance"] = merged["actual_stock_count"] - merged["expected_stock"]
  merged["variance_pct"] = (merged["variance"] / merged["total_purchased"].replace(0, 1) * 100).round(2)
  ```
- **Phân tích sai sót kỹ thuật:**
  1. **Thiếu Tồn Kho Đầu Kỳ ($\text{Opening Stock}$):**
     Công thức chuẩn kế toán kho F&B:
     $$\text{Tồn kỳ vọng} = \text{Tồn đầu kỳ} + \text{Tổng nhập trong kỳ} - \text{Tiêu hao lý thuyết} - \text{Hao hụt sơ chế}$$
     Mã nguồn hiện tại chỉ lấy `total_purchased - theoretical_usage`. Nếu cửa hàng có 50 hộp mứt đào tồn từ tháng trước và trong 15 ngày qua không nhập thêm hộp nào (`total_purchased = 0`), nhưng có bán được 20 ly trà đào (`theoretical_usage = 1000g`), thì `expected_stock` sẽ bị tính thành **-1000g (Số âm phi lý)**!
  2. **Bóp méo Tỷ lệ Lệch Kho (`variance_pct`):**
     Đoạn mã xử lý chia cho 0 bằng `merged["total_purchased"].replace(0, 1)`. Nếu một nguyên liệu không nhập mới trong kỳ (`total_purchased = 0`) và có tồn thực tế là 5,000g, mẫu số bị biến thành `1`, dẫn đến `variance_pct` nhảy vọt lên con số kỳ dị: **+500,000%**!
- **Đề xuất công thức sửa chữa chuẩn:**
  $$\text{Expected Stock} = \text{Initial Stock} + \text{Total Purchased} - \text{Theoretical Usage} - \text{Topping Waste}$$
  $$\text{Variance \%} = \frac{\text{Actual Stock} - \text{Expected Stock}}{\text{Initial Stock} + \text{Total Purchased}} \times 100$$

---

### 2.3. Mô Hình Dự Báo Nhu Cầu & Đánh Giá Cuốn Chiếu (Forecasting & Backtesting)
- **Vị trí mã nguồn:** [src/engine/forecasting.py:64-220](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/forecasting.py#L64-L220)
- **Các giải thuật dự báo cơ sở (Baselines):**
  1. *Seasonal Naive (Chu kỳ 7 ngày):* $y_t = y_{t-7}$. Rất tốt khi bắt trọn tính chu kỳ theo tuần của các ngày cuối tuần (Thứ 7, Chủ Nhật doanh thu tăng 25-35%).
  2. *Simple Moving Average (7 ngày):* $\hat{y}_t = \frac{1}{7} \sum_{i=1}^7 y_{t-i}$. Độ mượt cao, triệt tiêu nhiễu đột biến trong ngày mưa gió.
  3. *Day-of-Week Moving Average (3 tuần cùng thứ):* Tính trung bình của cùng thứ trong 3 tuần gần nhất.
- **Chỉ số đánh giá độ chính xác:**
  - $\text{MAE} = \frac{1}{n} \sum |y - \hat{y}|$
  - $\text{WAPE} = \frac{\sum |y - \hat{y}|}{\sum y} \times 100\%$ (Chỉ số tối ưu cho F&B, tránh chia cho 0 khi ngày bán 0 ly).
  - $\text{Bias} = \frac{\sum (\hat{y} - y)}{\sum y} \times 100\%$ (Đo lường xu hướng dự báo dư thừa hay thiếu hụt).
- **Kết quả thực nghiệm 15 ngày Backtest trên 39 SKUs:**
  - `Moving Average (7 ngày)`: MAE 8.31 ly, WAPE 20.27%, Bias +0.32% $\rightarrow$ **Mô hình tối ưu nhất được thuật toán tự động chọn (`auto`)**.
  - `Day-of-Week MA`: MAE 8.92 ly, WAPE 21.76%, Bias -0.78%.
  - `Seasonal Naive`: MAE 10.35 ly, WAPE 25.24%, Bias +0.22%.
- **Ưu điểm lớn:**
  Thuật toán tự động tính dải bất định (Confidence Interval 95%): $[\hat{y} - 1.96\sigma, \hat{y} + 1.96\sigma]$ và xếp hạng độ tin cậy HIGH ($\ge 21$ ngày lịch sử), MEDIUM ($\ge 7$ ngày), LOW.

---

### 2.4. Tối Ưu Mẻ Sơ Chế Topping (Topping Preparation Batch Optimization)
- **Vị trí mã nguồn:** [src/engine/optimizer.py:139-197](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/optimizer.py#L139-L197)
- **Quy tắc nghiệp vụ SOP Mixue:**
  - Trân châu tươi (NL06) có hạn dùng **4 giờ** sau khi nấu.
  - Các loại thạch và trà lạnh (TP02, TP03, TP04, NL07, NL08) bắt buộc **đổ bỏ cuối ngày**, tuyệt đối không mang sang ngày hôm sau vì nguy cơ nhiễm khuẩn và biến chất hương vị.
  - Do đó, tồn kho đầu ngày dùng được ($\text{usable\_opening\_stock}$) luôn được đặt mặc định là `0.0`.
- **Công thức làm tròn mẻ nấu:**
  $$\text{Net Demand} = \max(0, \text{Forecasted Demand} \times (1 + \text{Buffer}_{10\%}) - \text{Usable Stock})$$
  $$\text{Batches} = \left\lceil \frac{\text{Net Demand}}{\text{Batch Size}} \right\rceil$$
  $$\text{Recommended Prep} = \text{Batches} \times \text{Batch Size}$$
  *(Quy cách: Trân châu/thạch = 1,000g/mẻ; Trà lạnh/trà sữa = 5,000ml/mẻ).*
- **Đánh giá rủi ro hao hụt:**
  Nếu tỷ lệ hao hụt kỳ vọng $> 30\%$, hệ thống tự động gán nhãn `HIGH RISK` để cảnh báo nhân viên quầy bar cần cân nhắc nấu mẻ nhỏ hoặc đợi đơn cao điểm.

---

### 2.5. Tối Ưu Đơn Đặt Hàng PO Theo Quy Cách Thùng/Kiện Chuỗi Mixue
- **Vị trí mã nguồn:** [src/engine/optimizer.py:199-303](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/optimizer.py#L199-L303)
- **Tham số vận hành:**
  - Lead Time: **2 ngày** (Thời gian từ khi đặt hàng từ kho tổng Mixue đến khi hàng về tới 39 Tôn Quang Phiệt).
  - Chu kỳ rà soát (Review Period): **7 ngày**.
  - Hệ số an toàn (Safety Factor): **1.3** (Dự phòng 30% cho biến động nhu cầu).
- **Quy tắc đóng gói chuẩn Master Mixue (`MIXUE_CARTON_SPECS`):**
  - Ốc quế: Thùng 400 cái (16 dây/thùng).
  - Bột kem: Thùng 24kg (8 túi/thùng).
  - Ly cốc 700 / Ly chữ U: Kiện 1,000 cái (20 dây/kiện).
  - Đường mật / Đường hoa quả: Kiện 26kg (4 can 6.5kg/kiện).
  - Syrup hạt dẻ / Socola: Thùng 14.4kg (12 chai/thùng).
- **Quy tắc làm tròn nguyên thùng:**
  $$\text{Packs To Order} = \left\lceil \frac{\text{Net Required}}{\text{Pack Size}} \right\rceil$$
  Tuyệt đối không xuất hiện các đơn đặt hàng dạng lẻ túi ("2.5 thùng" hoặc "350 cái cốc"), đảm bảo tính khả thi khi gửi PO cho nhà cung cấp chuỗi.
- **Phân loại độ khẩn cấp (Priority Triaging):**
  - $\text{Days of Stock} < \text{Lead Time (2 ngày)} \rightarrow$ **CRITICAL (Cần đặt gấp)**.
  - $\text{Packs} > 0 \rightarrow$ **REORDER (Đặt theo chu kỳ tuần)**.
  - Còn lại $\rightarrow$ **OK (Đủ tồn kho)**.

---

### 2.6. Quy Trình Maker-Checker Trong Quản Trị Kho 31 Ngày
- **Vị trí mã nguồn:** [src/engine/daily_stock_service.py:240-380](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/daily_stock_service.py#L240-L380)
- **Luồng phê duyệt kép:**
  - Tài khoản Nhân viên (Staff): Khi nhập số lượng xuất quầy bar hoặc nhập kho, lệnh được tạo ở trạng thái `PENDING`. Sổ thẻ kho 31 ngày **chưa ghi nhận biến động**.
  - Tài khoản Quản lý / Chủ quán: Nhận danh sách chờ tại tab Duyệt Lệnh Kho. Chỉ sau khi bấm nút **"Duyệt Ghi Sổ"**, lệnh mới chuyển sang `APPROVED` và ma trận kho được cập nhật ngay lập tức.
- **Lỗ hổng phát hiện:**
  - Không có kiểm tra trùng lặp (Idempotency Check). Nếu mạng chập chờn hoặc nhân viên bấm nút gửi 2 lần liên tiếp cách nhau 500ms, hệ thống sẽ sinh ra 2 bản ghi `DailyStockMovement` riêng biệt có cùng ngày, cùng mặt hàng và cùng số lượng.

---

## 3. TỔNG HỢP KIỂM THỬ TRƯỜNG HỢP BIÊN (BOUNDARY VALUE ANALYSIS)

| Trường Hợp Biên | Đầu Vào Thử Nghiệm | Kết Quả Thực Tế | Đánh Giá |
|---|---|---|---|
| **Số lượng âm** | Nhập `quantity = -5` tại lệnh xuất kho | Bị chặn bởi `validator.py` và `daily_stock_service.py` | **ĐẠT (PASS)** |
| **Chia cho 0** | Bán 0 ly trên ngày tính giá AOV | Đã bọc `if total_cups > 0` | **ĐẠT (PASS)** |
| **Ngày ngoài kỳ** | Truy vấn doanh thu ngày `30/02/2026` | Trả về `NO_DATA` an toàn | **ĐẠT (PASS)** |
| **BOM trống** | Món không có nguyên liệu | Bỏ qua dòng, không crash | **CẦN WARNING** |
| **Tồn kho âm** | Bán vượt quá tồn đầu kỳ | `bom_engine.py` tính ra variance âm kỳ dị | **LỖI (FAIL)** |
| **Trùng lặp lệnh** | Double click gửi yêu cầu xuất kho | Tạo 2 bản ghi trùng nhau | **LỖI (FAIL)** |
