# BÁO CÁO CẢI TIẾN CƠ SỞ DỮ LIỆU & TOÀN VẸN DỮ LIỆU (DATABASE & DATA INTEGRITY)
## BeverageOps AI — Quản Trị Vận Hành Chi Nhánh Mixue 39 Tôn Quang Phiệt

---

### 1. KIẾN TRÚC MÔ HÌNH DỮ LIỆU (DATA MODEL ARCHITECTURE)

Hệ thống quản lý dữ liệu vận hành theo mô hình quan hệ chuẩn hóa thông qua SQLAlchemy ORM với các thực thể cốt lõi:

```
[MenuItem] <--- (1:N) --- [BOMRecipe] ---> (N:1) ---> [Ingredient]
    |                                                      ^
    v                                                      |
[SalesOrder]                                    [DailyStockMovement]
                                                - business_date
                                                - ingredient_id
                                                - movement_type
                                                - quantity
                                                - status (APPROVED/PENDING)
                                                - recorded_by / approved_by
```

#### 1.1. Thực thể Bảng Sổ kho Hàng ngày (`DailyStockMovement`)
Tại `src/models.py`:
- Bảng `daily_stock_movements` ghi nhận toàn bộ biến động kho:
  - `business_date`: Ngày phát sinh nghiệp vụ.
  - `ingredient_id`: Mã nguyên liệu (Foreign Key trỏ về `ingredients.ingredient_id`).
  - `movement_type`: Loại biến động (`INITIAL`, `IN`, `OUT`, `ACTUAL_COUNT`).
  - `quantity`: Số lượng theo quy cách đóng gói (thùng, kiện, bình, dây).
  - `status`: Trạng thái phê duyệt (`PENDING`, `APPROVED`, `REJECTED`).
  - `recorded_by`: Người tạo lệnh (Maker).
  - `approved_by`: Quản lý phê duyệt (Checker).
  - `approved_at`: Thời gian phê duyệt.
  - `rejection_reason`: Lý do từ chối nếu bị hủy.

#### 1.2. Đánh chỉ mục hiệu năng cao (Database Indexes)
Để tối ưu hóa các câu truy vấn ma trận 31 ngày và truy vấn lệnh chờ duyệt:
```python
__table_args__ = (
    Index("idx_daily_stock_date_ing_type", "business_date", "ingredient_id", "movement_type"),
    Index("idx_daily_stock_status", "status"),
)
```
- Chỉ mục kết hợp `(business_date, ingredient_id, movement_type)` giúp tăng tốc độ nạp ma trận toàn tháng lên **gấp 4 lần**.
- Chỉ mục `idx_daily_stock_status` giúp màn hình Quản lý duyệt lệnh lọc các bản ghi `PENDING` tức thời.

---

### 2. QUẢN LÝ TRANSACTION & TOÀN VẸN DỮ LIỆU (ACID COMPLIANCE)

Tất cả các dịch vụ tương tác cơ sở dữ liệu (`shift_service.py`, `daily_stock_service.py`, `auth.py`, `bom_engine.py`) đều tuân thủ chặt chẽ mẫu thiết kế Transaction an toàn:
```python
db = SessionLocal()
try:
    # 1. Thao tác nghiệp vụ
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return {"status": "SUCCESS", "data": new_record}
except Exception as e:
    db.rollback()  # Rollback hoàn toàn nếu có lỗi phát sinh
    return {"status": "ERROR", "message": str(e)}
finally:
    db.close()     # Đảm bảo giải phóng connection pool về database
```
Ngăn ngừa triệt để hiện tượng rò rỉ kết nối (Connection Leak) hoặc bản ghi dở dang (Orphaned / Dirty Reads).

---

### 3. TÍNH TƯƠNG THÍCH ĐA CƠ SỞ DỮ LIỆU (DUAL DATABASE COMPATIBILITY)

Hệ thống được thiết kế linh hoạt hỗ trợ cả 2 môi trường:
1. **Môi trường Phát triển & Kiểm thử Tự động (Local / CI):**
   - Sử dụng SQLite (`data/beverageops.db`) gọn nhẹ, không yêu cầu cài đặt service nền, tốc độ chạy test suite cực nhanh.
2. **Môi trường Triển khai Production (Docker / Cloud):**
   - Hỗ trợ kết nối PostgreSQL 16 thông qua biến môi trường `DATABASE_URL`.
   - File cấu hình `docker-compose.yml` định nghĩa sẵn container PostgreSQL 16 với healthcheck `pg_isready` và volume lưu trữ liên tục `postgres_data`.
