# Hướng dẫn Chạy & Demo — BeverageOps AI (Mixue 39 Tôn Quang Phiệt)

> **Cửa hàng thực tế:** Mixue 39 Tôn Quang Phiệt · **Mã cửa hàng:** 2132 (`MX-2132`)  
> **Chủ quán:** Nguyễn Hạnh Chi · **Quản lý:** Bùi Văn Quang  
> **Địa chỉ:** Số 39 Tôn Quang Phiệt, Bắc Từ Liêm, Hà Nội  
> **Linh vật & Giao diện:** Tuyết Vương AI (Snow King / 雪王) & My Mixue App  

## 1. Khởi động Web Dashboard (Streamlit)

Để mở giao diện điều hành và phân tích trực quan:

```bash
streamlit run src/dashboard/app.py
```

Dashboard sẽ tự động mở trên trình duyệt tại địa chỉ: `http://localhost:8501`.

---

## 2. Các Tab Chức năng trong Demo

### Tab 1: 📊 Doanh số & Tồn kho
- **Mục tiêu:** Giám sát tổng quan doanh thu, sản lượng bán theo ngày và đối soát kho.
- **Thao tác demo:**
  - Xem 4 thẻ KPI tổng hợp (Doanh thu 30 ngày, Sản lượng bán, Trung bình ngày, Số lượng món).
  - Quan sát biểu đồ xu hướng bán hàng theo ngày.
  - Xem bảng đối soát kho: Tiêu thụ lý thuyết theo công thức BOM so với lượng kiểm kê thực tế.

### Tab 2: 📈 Dự báo nhu cầu D+1
- **Mục tiêu:** Dự báo nhu cầu bán lẻ cho ngày mai và kiểm chứng sai số bằng backtesting rolling-origin.
- **Thao tác demo:**
  - Xem bảng so sánh chỉ số sai số backtesting (MAE, WAPE, Bias) giữa 3 mô hình (`Moving Average`, `Seasonal Naive`, `Day-of-Week MA`).
  - Chọn ngày dự báo (ví dụ: `2026-10-13`) và nhấn **"🚀 Chạy Mô hình Dự báo"**.
  - Bảng kết quả sẽ hiển thị số ly dự kiến kèm khoảng tin cậy trên/dưới và mức độ tin cậy.

### Tab 3: 🥣 Kế hoạch Sơ chế Topping
- **Mục tiêu:** Tính toán số mẻ trà, thạch, trân châu cần nấu mỗi ngày để đảm bảo không thiếu hàng nhưng hạn chế tối đa việc phải đổ bỏ cuối ngày.
- **Thao tác demo:**
  - Điều chỉnh thanh trượt **Tỷ lệ đệm an toàn (Buffer)** (ví dụ: 10%).
  - Nhấn **"⚡ Tính toán Kế hoạch Sơ chế"**.
  - Xem số mẻ gợi ý, lượng cần nấu tròn theo dung tích bình/nồi (5.000 ml cho trà, 1.000 g cho thạch/trân châu) và trạng thái kiểm định `VERIFIED`.
  - Nhấn **"✅ Phê duyệt Kế hoạch Sơ chế"** (kiểm tra phân quyền theo vai trò ở sidebar).

### Tab 4: 📦 Dự thảo Đơn nhập hàng
- **Mục tiêu:** Lập dự thảo đơn đặt hàng nguyên liệu thô (syrup, mứt, bột, bao bì ly cốc) dựa trên tồn kho hiện tại, Lead Time và chu kỳ đặt hàng.
- **Thao tác demo:**
  - Nhập Lead Time (ví dụ: 2 ngày).
  - Nhấn **"📋 Tạo Dự thảo Đơn đặt hàng"**.
  - Hệ thống tự động lọc ra các mặt hàng có nguy cơ cạn kho (`CRITICAL`) và làm tròn theo quy cách bao/gói/thùng.
  - Phê duyệt đơn hàng bởi Quản lý (Manager).

### Tab 5: 🏷️ Tra cứu Tem & Công thức
- **Mục tiêu:** Hỗ trợ nhân viên quầy bar giải mã tem in nhãn tự động và tra cứu công thức pha chế.
- **Thao tác demo:**
  - Nhập mã tem ly: `24101` $\rightarrow$ Nhấn **"Giải mã Tem"** $\rightarrow$ Hệ thống lập tức đọc ra: *Món 24 (Trà đào), 30% đường, nóng, thêm 1 vá trân châu nguyên vị* kèm quy tắc trừ 5g đường chuẩn Mixue.
  - Chọn một món bất kỳ từ menu (ví dụ: `TS1 - Trà sữa trân châu`) để xem bảng định lượng nguyên liệu chi tiết.

### Tab 6: 🤖 Trợ lý Vận hành AI (AI Operations Agent)
- **Mục tiêu:** Hỏi đáp tự nhiên về tình hình vận hành cửa hàng.
- **Thao tác demo:**
  - Nhấn vào các nút tác vụ nhanh hoặc gõ câu hỏi:
    - *"Ngày mai nên sơ chế bao nhiêu topping?"*
    - *"Có cần nhập hàng gì gấp không?"*
    - *"Dự báo doanh số ngày mai"*
    - *"Tại sao tuần này hủy topping nhiều?"*
  - Xem phản hồi có cấu trúc, mã dự thảo và trích dẫn bằng chứng dữ liệu (`evidence_refs`).

---

## 3. Chạy Kiểm thử Tự động (Automated Verification)

Chạy bộ kiểm thử toàn diện 15 test cases:
```bash
pytest tests/ -v
```

Chạy bộ đánh giá 30 kịch bản Golden Cases:
```bash
python -X utf8 experiments/evaluate_golden.py
```
