# BeverageOps AI — Hệ thống Điều phối Vận hành Cửa hàng Mixue 39 Tôn Quang Phiệt

> **Chi nhánh triển khai thực tế:** Mixue 39 Tôn Quang Phiệt · **Mã cửa hàng:** 2132 (`MX-2132`)  
> **Chủ quán:** Nguyễn Hạnh Chi · **Quản lý điều hành:** Bùi Văn Quang  
> **Địa chỉ:** Số 39 Tôn Quang Phiệt, P. Cổ Nhuế 1, Q. Bắc Từ Liêm, TP. Hà Nội  
> **Giao diện nhận diện:** Linh vật Tuyết Vương (Snow King / 雪王) & Ứng dụng My Mixue  
> **Nguyên tắc thiết kế:** Evidence-Driven · Deterministic Optimization · Human-in-the-Loop Governance · An toàn Vận hành Thực phẩm (SOP).

---

## 1. Kiến trúc Hệ thống & Chức năng Cốt lõi

Hệ thống được phát triển tuân thủ đầy đủ quy trình 30 ngày (Checkpoints CP1 $\rightarrow$ CP6) theo `01_PRD_BeverageOps_AI.md` và `02_ARD_ADR_BeverageOps_AI.md`:

```
Dữ liệu chuẩn hóa 30 ngày (1.170 sales, 120 BOM, tồn kho, kiểm kê, waste)
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│               Database & Ingestion (CP1)               │
│  SQLite Local / PostgreSQL · SQLAlchemy 7 Data Models  │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│             BOM & Analytics Engine (CP2)               │
│  BOM Explosion · Doanh số · Hao hụt · Đối soát Kho     │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│           Forecasting & Backtesting Engine (CP2)       │
│  Moving Average (WAPE 20.27%) · Seasonal Naive         │
│  Dự báo nhu cầu D+1 toàn menu (39 SKUs)                │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│         Optimization & Policy Validator (CP3)          │
│  Tính mẻ sơ chế topping · Dự thảo đơn nhập hàng (PO)   │
│  Làm tròn theo quy cách mẻ/pack · Kiểm định độc lập    │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│           AI Operations Agent & RBAC (CP4)             │
│  LangGraph / LangChain tool contracts                  │
│  Giải mã tem nhãn ly · Phân quyền duyệt Manager/Owner  │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│         Interactive Web Dashboard (CP5 & CP6)          │
│  Streamlit Dashboard: 6 Tabs Vận hành Toàn diện        │
└────────────────────────────────────────────────────────┘
```

---

## 2. Hướng dẫn Khởi chạy Nhanh

### 2.1. Cài đặt Môi trường
Môi trường yêu cầu Python 3.11+:
```powershell
python -m pip install -r requirements.txt
```

Cài mới không tạo tài khoản với mật khẩu mặc định. Cấp tài khoản quản lý bằng `python scripts/provision_admin.py quanly --name "Quản lý"`; mật khẩu được nhập riêng và cần 12–128 ký tự. Tài khoản quản lý cũ dùng mật khẩu công khai cần đặt lại bằng cùng lệnh có thêm `--reset-existing`. Không bật `APP_DEMO_MODE` khi sử dụng thật.

Database chính nhận `DATABASE_URL` từ môi trường tiến trình, sau đó từ `.env`; khi không có URL, ứng dụng dùng SQLite cục bộ trong `data/`. PostgreSQL đã cấu hình mà không kết nối được sẽ báo lỗi. Để kiểm tra cấu hình PostgreSQL/MCP mà không lộ mật khẩu, chạy `python scripts/check_database_setup.py`. Hướng dẫn PostgreSQL MCP nằm trong [docs/POSTGRES_MCP.md](docs/POSTGRES_MCP.md). Chi tiết bản sửa và giới hạn xác minh: [docs/AUDIT_REMEDIATION.md](docs/AUDIT_REMEDIATION.md).

### 2.2. Nạp Dữ liệu vào Database (Ingestion)
Đọc và nạp toàn bộ 30 ngày dữ liệu nghiệp vụ chuẩn hóa:
```powershell
python src/ingestion.py
```

### 2.3. Khởi động Web Dashboard (Streamlit)
```powershell
streamlit run src/dashboard/app.py
```
Giao diện sẽ tự động hiển thị tại `http://localhost:8501`.

### Giao diện Mixue mới

- Trang chủ và đăng nhập đỏ–trắng, ảnh sản phẩm chính thức Mixue xếp lớp và linh vật Tuyết Vương; hỗ trợ màn hình điện thoại.
- GSAP chạy từ thư viện lưu tại máy: chuyển cảnh xuất hiện, thẻ nghiêng 3D theo con trỏ, hiệu ứng nổi và chuyển động theo cuộn. Chuyển động lặp tự bật theo yêu cầu thiết kế; có nút tạm dừng hiệu ứng.
- Ảnh thực đơn ánh xạ riêng cho 39 SKU trong `src/dashboard/assets/product-images.json`; các phiên bản Việt quất hiện tại có ghi chú trên thẻ. Nguồn ảnh và thư viện ghi trong `src/dashboard/assets/SOURCES.md`.
- Thực đơn đọc tên món, giá và biến thể từ database; tìm kiếm không dấu, lọc nhóm và phân trang.
- Nút **Xem công thức** gửi mã món sang trợ lý Tuyết Vương ở cột bên phải. Lịch sử trả lời giữ nguồn dữ liệu để đối chiếu.
- Điều hướng đến báo cáo/kho, dự báo, sơ chế, nhập hàng và tem/công thức; chat luôn có sẵn.
- Mở thanh bên bằng nút góc trên trái để chọn vai trò mô phỏng. Đây là chế độ demo, chưa phải đăng nhập xác thực.
- Ảnh minh họa nằm trong `src/dashboard/assets`; giao diện trong `src/dashboard/brand_ui.py` và `brand.css`. Tông sáng được cấu hình tại `.streamlit/config.toml`.

Kiểm tra luồng giao diện: `python -m pytest tests/test_dashboard.py -q`.

---

## 3. Kiểm thử & Đánh giá Tự động

### 3.1. Chạy Pytest Suite (15/15 Passed)
```powershell
pytest tests/ -v
```
Kiểm thử toàn diện:
- `test_bom.py`: Đối soát BOM explosion, lượng tiêu thụ lý thuyết, hao hụt topping.
- `test_forecasting.py`: Dự báo 39 SKU, đánh giá WAPE/MAE/Bias qua 15 ngày backtesting.
- `test_optimizer.py`: Quy cách làm tròn mẻ, quy cách đóng gói pack, từ chối lượng âm.
- `test_agent.py`: Tool contracts, giải mã tem dán ly, chặn quyền duyệt từ Staff.

### 3.2. Đánh giá 30 Kịch bản Vận hành (Golden Dataset - 100% Passed)
```powershell
python -X utf8 experiments/evaluate_golden.py
```
Đánh giá độc lập 30 kịch bản vận hành thực tế:
- Doanh số & phân tích bán hàng.
- Dự báo nhu cầu D+1.
- Kế hoạch sơ chế theo mẻ (tròn 5.000 ml trà, 1.000 g thạch/trân châu).
- Đề xuất nhập hàng (cảnh báo nguy cấp < Lead Time 2 ngày).
- Giải mã mã tem 5 chữ số Mixue (ví dụ: `24101` $\rightarrow$ Trà đào, 30% đường, nóng, thêm trân châu).
- Cơ chế Human-in-the-Loop & Phân quyền RBAC nghiêm ngặt.

---

## 4. Tài liệu Tham khảo

- [01_PRD_BeverageOps_AI.md](01_PRD_BeverageOps_AI.md): Yêu cầu sản phẩm & bài toán nghiệp vụ.
- [02_ARD_ADR_BeverageOps_AI.md](02_ARD_ADR_BeverageOps_AI.md): Kiến trúc kỹ thuật & các quyết định ADR.
- [03_Checkpoints_30_Ngay.md](03_Checkpoints_30_Ngay.md): Lộ trình 30 ngày triển khai thực tế.
- [docs/demo.md](docs/demo.md): Kịch bản chi tiết hướng dẫn chạy Demo và thuyết minh bảo vệ.
- [reports/benchmark_v1.md](reports/benchmark_v1.md): Báo cáo so sánh mô hình và kết quả thực nghiệm.
- [Bang_Du_Lieu_Mixue.xlsx](Bang_Du_Lieu_Mixue.xlsx): Sổ tay 19 sheet số hóa toàn bộ tài liệu và công thức Mixue.
