# BÁO CÁO KIỂM TOÁN CƠ SỞ DỮ LIỆU & TÍNH TOÀN VẸN DỮ LIỆU (DATABASE AUDIT)
## HỆ THỐNG: BEVERAGE-OPS AI — CHI NHÁNH MIXUE 39 TÔN QUANG PHIỆT
**Mã tài liệu:** `WB-AUDIT-07-DB`  
**Phiên bản:** 2.0.0-PROD-AUDIT  
**Đối tượng:** Đánh giá lược đồ ORM (`src/models.py`), cấu hình CSDL (`src/database.py`), tính toàn vẹn tham chiếu, chỉ mục và quản lý Migration

---

## 1. PHÂN TÍCH LƯỢC ĐỒ CƠ SỞ DỮ LIỆU (DATABASE SCHEMA AUDIT)

Hệ thống sử dụng SQLAlchemy 2.0 ORM với 9 bảng thực thể chính được định nghĩa trong [src/models.py](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/models.py).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATABASE SCHEMA SUMMARY                            │
├──────────────────────┬─────────────┬─────────────┬──────────────────────────┤
│ Bảng (Table Name)    │ Khóa Chính  │ Khóa Ngoại  │ Chỉ Mục Tối Ưu (Indexes) │
├──────────────────────┼─────────────┼─────────────┼──────────────────────────┤
│ menu_items           │ sku_id (PK) │ Không       │ None (PK indexed)        │
├──────────────────────┼─────────────┼─────────────┼──────────────────────────┤
│ ingredients          │ ingredient_ │ Không       │ None (PK indexed)        │
│                      │ id (PK)     │             │                          │
├──────────────────────┼─────────────┼─────────────┼──────────────────────────┤
│ recipe_bom           │ id (PK Auto)│ sku_id,     │ idx_recipe_sku_ing       │
│                      │             │ ingredient_ │                          │
├──────────────────────┼─────────────┼─────────────┼──────────────────────────┤
│ sales_daily          │ id (PK Auto)│ sku_id      │ idx_sales_store_date_sku │
│                      │             │             │ (Unique composite)       │
├──────────────────────┼─────────────┼─────────────┼──────────────────────────┤
│ purchases            │ id (PK Auto)│ ingredient_ │ idx_purchases_po_ing     │
│                      │             │ id          │ (Unique composite)       │
├──────────────────────┼─────────────┼─────────────┼──────────────────────────┤
│ stock_counts         │ id (PK Auto)│ ingredient_ │ idx_stock_count_ing      │
│                      │             │ id          │ (Unique composite)       │
├──────────────────────┼─────────────┼─────────────┼──────────────────────────┤
│ topping_daily        │ id (PK Auto)│ prepared_   │ idx_topping_store_date_  │
│                      │             │ ingredient_ │ ing (Unique composite)   │
├──────────────────────┼─────────────┼─────────────┼──────────────────────────┤
│ users                │ username(PK)│ Không       │ None (PK indexed)        │
├──────────────────────┼─────────────┼─────────────┼──────────────────────────┤
│ daily_stock_movements│ id (PK Auto)│ ingredient_ │ idx_daily_stock_date_ing_│
│                      │             │ id          │ type, idx_status         │
└──────────────────────┴─────────────┴─────────────┴──────────────────────────┘
```

### 1.1. Đánh Giá Điểm Mạnh Trong Thiết Kế Schema
1. **Toàn Vẹn Tham Chiếu Khóa Ngoại (Foreign Key Constraints):**
   Mối liên kết giữa các bảng định lượng `recipe_bom`, bán hàng `sales_daily`, mua hàng `purchases`, kiểm kê `stock_counts` và thẻ kho `daily_stock_movements` đều có khóa ngoại tham chiếu chặt chẽ về `menu_items.sku_id` và `ingredients.ingredient_id`.
2. **Chỉ Mục Độc Nhất Phức Hợp (Unique Composite Indexes):**
   - Chỉ mục `idx_sales_store_date_sku` trên `sales_daily (store_id, business_date, sku_id)` ngăn chặn tuyệt đối tình trạng một mã món bị ghi đúp 2 dòng doanh thu trong cùng một ngày.
   - Chỉ mục `idx_purchases_po_ing` ngăn ngừa trùng lặp một mặt hàng trong cùng một mã đơn nhập kho `purchase_id`.

---

## 2. CÁC THIẾU SÓT THỰC THỂ & LỖ HỔNG THIẾT KẾ (SCHEMA DEFECTS)

### 2.1. Thực Thể Bị Thiếu: `ShiftReport` và `ShiftExpense` (Báo Cáo Chốt Ca)
- **Vấn đề nghiêm trọng nhất:** Toàn bộ dữ liệu doanh thu chốt ca theo từng ca làm việc (ca sáng, ca chiều, ca tối), tiền mặt, chuyển khoản, đối soát POS và chi phí phát sinh **hoàn toàn không có bảng trong CSDL**!
- Thay vào đó, dữ liệu này đang nằm trong tệp [data/shift_reports.json](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/data/shift_reports.json).
- **Hậu quả:** Không thể thực hiện ràng buộc khóa ngoại với bảng `users` (ai là người chốt sổ), không thể chạy trigger, không thể backup tập trung cùng CSDL và là nguyên nhân trực tiếp gây ra 2 lỗi FAILED trong bộ unit test kiểm thử chốt ca.

### 2.2. Thiếu Cột `store_id` Trong Bảng `daily_stock_movements`
- Tại [src/models.py:149-170](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/models.py#L149-L170):
  Bảng `daily_stock_movements` (Sổ xuất - nhập - tồn kho hàng ngày 31 ngày) chỉ có các cột: `id`, `business_date`, `ingredient_id`, `movement_type`, `quantity`, `status`, `recorded_by`, `approved_by`.
  **Hoàn toàn không có cột `store_id`!**
- Trong khi đó, bảng `sales_daily` và `topping_daily` đều có cột `store_id`.
- **Hậu quả:** Nếu chuỗi Mixue mở thêm chi nhánh thứ hai (ví dụ: Mixue Cầu Giấy hoặc Mixue Nghĩa Tân), hệ thống không có cách nào phân biệt được lệnh xuất kho này là của chi nhánh 39 Tôn Quang Phiệt hay chi nhánh mới.

### 2.3. Thiếu Bảng Lưu Trữ Kế Hoạch Dự Thảo (`OperationalDraftPlan`)
- Các kế hoạch do AI tạo ra (`PLAN_PREP_...` và `PLAN_PO_...`) hiện đang lưu trong bộ nhớ RAM (`self.draft_plans`).
- Cần bổ sung bảng `operational_draft_plans` với các trường:
  `plan_id (PK)`, `plan_type (PREP/PO)`, `target_date`, `status (DRAFT/APPROVED/REJECTED)`, `plan_payload (JSON)`, `created_by`, `approved_by`, `approved_at`.

---

## 3. ĐÁNH GIÁ KIỂU DỮ LIỆU & TÍNH CHÍNH XÁC SỐ HỌC (DATA TYPES & PRECISION)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DATA TYPE PRECISION AUDIT                             │
├────────────────────┬─────────────────────┬──────────┬───────────────────────┤
│ Trường Dữ Liệu     │ Kiểu Khai Báo ORM   │ Đánh Giá │ Rủi Ro Kỹ Thuật       │
├────────────────────┼─────────────────────┼──────────┼───────────────────────┤
│ selling_price_vnd  │ Numeric(12, 0)      │ CHUẨN    │ Phù hợp tiền VND      │
│ revenue_vnd        │ Numeric(14, 0)      │ CHUẨN    │ Đủ sức chứa hàng tỷ đ │
├────────────────────┼─────────────────────┼──────────┼───────────────────────┤
│ quantity_per_item  │ Numeric(10, 2)      │ TỐT      │ Định lượng gram/ml    │
│ quantity_received  │ Numeric(12, 2)      │ TỐT      │ Định lượng nhập kho   │
├────────────────────┼─────────────────────┼──────────┼───────────────────────┤
│ Pandas astype()    │ .astype(float)      │ CẢNH BÁO │ Chuyển Decimal sang   │
│ in bom_engine.py   │                     │          │ Float64 gây trôi số học│
└────────────────────┴─────────────────────┴──────────┴───────────────────────┘
```

- **Rủi ro trôi số học do ép kiểu `float`:**
  Tại [src/engine/bom_engine.py:44, 108-110, 143-144](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/engine/bom_engine.py#L44), sau khi truy vấn các trường `Numeric` từ SQLAlchemy, mã nguồn sử dụng:
  ```python
  df["revenue_vnd"] = df["revenue_vnd"].astype(float)
  df["quantity_sold"] = df["quantity_sold"].astype(int)
  ```
  Trong chuẩn xử lý tài chính (Financial Systems), việc chuyển đổi kiểu dữ liệu chính xác tuyệt đối `Decimal` sang số thực dấu phẩy động `float64` có thể phát sinh sai số vi mô (ví dụ: `0.1 + 0.2 = 0.30000000000000004`). Đối với doanh thu chốt ca và kiểm kê kho F&B, cần giữ nguyên kiểu `Decimal` hoặc làm tròn nguyên số tiền đồng.

---

## 4. PHÂN TÍCH ĐỘC QUYỀN KẾT NỐI VÀ KHÓA CSDL (SQLITE VS POSTGRESQL CONCURRENCY)

### 4.1. Cấu Hình Cơ Sở Dữ Liệu Hiện Tại
- Tại [src/database.py:12-26](file:///c:/Users/Admin/OneDrive/Desktop/DATN/AI-Agent_mixue/src/database.py#L12-L26):
  ```python
  db_url = os.getenv("DATABASE_URL")
  if not db_url or "postgresql" in db_url and not os.getenv("POSTGRES_ACTIVE"):
      sqlite_path = ROOT / "data" / "beverageops.db"
      DATABASE_URL = f"sqlite:///{sqlite_path.as_posix()}"
  else:
      DATABASE_URL = db_url

  engine = create_engine(
      DATABASE_URL,
      echo=False,
      connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
  )
  ```
- **Rủi ro với SQLite trong môi trường đa người dùng:**
  - Cờ `connect_args={"check_same_thread": False}` cho phép nhiều thread chia sẻ kết nối SQLite. Tuy nhiên, SQLite sử dụng cơ chế **khóa cấp độ toàn bộ tệp (File-level Database Lock)** khi ghi dữ liệu.
  - Khi nhân viên thu ngân gửi lệnh chốt ca hoặc duyệt thẻ kho cùng lúc với một tiến trình khác đang ghi nhật ký, SQLite sẽ ném ra lỗi `sqlite3.OperationalError: database is locked`.
  - Chưa bật chế độ ghi nhật ký trước (WAL Mode - Write-Ahead Logging): Mặc định SQLite ở chế độ Rollback Journal. Cần kích hoạt `PRAGMA journal_mode=WAL;` để cho phép đọc đồng thời trong khi đang ghi.

---

## 5. THIẾU HỤT CÔNG CỤ QUẢN LÝ THAY ĐỔI LƯỢC ĐỒ (NO ALEMBIC MIGRATION TOOL)

- **Thực trạng:** Toàn bộ repository hoàn toàn **không có thư mục `alembic/` hoặc tệp cấu hình `alembic.ini`**.
- Mọi thao tác tạo bảng phụ thuộc vào lệnh `Base.metadata.create_all(bind=engine)`.
- **Rủi ro sản xuất cực lớn:**
  - Lệnh `create_all()` **chỉ tạo mới các bảng chưa tồn tại**.
  - Nếu lập trình viên thêm một cột mới (ví dụ: thêm cột `store_id` vào `daily_stock_movements` hoặc thêm cột `is_verified` vào `users`), lệnh `create_all()` sẽ **hoàn toàn bỏ qua và không cập nhật bảng đã có** trên máy chủ!
  - Lập trình viên buộc phải xóa file DB cũ (mất sạch dữ liệu) hoặc phải dùng tool SQLite Browser để gõ lệnh `ALTER TABLE` bằng tay, vi phạm nghiêm trọng quy trình triển khai phần mềm an toàn.

---

## 6. KHUYẾN NGHỊ TỐI ƯU HÓA CƠ SỞ DỮ LIỆU (DATABASE HARDENING ROADMAP)

1. **Chuyển Toàn Bộ Sang PostgreSQL 16 (Khuyên Dùng Cho Production):**
   Kích hoạt container PostgreSQL đã có trong `docker-compose.yml`, chuyển chuỗi kết nối trong `.env` sang `postgresql://postgres:password@localhost:5432/beverageops` để loại bỏ hoàn toàn nguy cơ khóa file của SQLite.
2. **Khởi Tạo Alembic Migrations:**
   Chạy lệnh `alembic init alembic`, cấu hình `target_metadata = Base.metadata` và sinh bản migration đầu tiên (`001_initial_schema.py`) để quản lý phiên bản CSDL chặt chẽ qua Git.
3. **Bổ Sung Bảng `shift_reports` và `shift_expenses`:**
   Đưa dữ liệu chốt ca từ file JSON vào CSDL quan hệ chuẩn, tạo quan hệ `ForeignKey` với bảng `users`.
4. **Bổ Sung Cột `store_id`:**
   Cập nhật `daily_stock_movements` với cột `store_id = Column(String(50), nullable=False, default="2132")` để đảm bảo tính sẵn sàng mở rộng chuỗi.
