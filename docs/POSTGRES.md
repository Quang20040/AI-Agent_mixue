# Chuyển cơ sở dữ liệu sang PostgreSQL

Bật bằng **một biến môi trường**: `DATABASE_URL=postgresql://…`. Lần khởi động đầu tiên, `scripts/bootstrap_postgres.py`
tạo bảng rồi chép **một lần** toàn bộ dữ liệu từ file SQLite trên ổ đĩa (`PERSIST_DIR/beverageops.db`) sang PostgreSQL:
một transaction, so khớp từng trường bằng SHA-256, báo cáo lưu ở `PERSIST_DIR/migrations/<thời điểm>/verification.json`.
PostgreSQL đã có dữ liệu thì không bao giờ bị ghi đè; file SQLite cũ được giữ nguyên để quay lại khi cần
(xóa `DATABASE_URL` là app chạy lại trên SQLite).

Chuyển sang PostgreSQL: bảng tài khoản, thực đơn, nguyên liệu, công thức, doanh thu, kho, phiếu kho, nhập hàng, kế hoạch.
Vẫn là file trên ổ đĩa: báo cáo chốt ca đã duyệt (`shift_reports.json`), ảnh, lịch sử chat, checkpoint agent,
nhật ký kiểm toán, log chi phí AI. Phiên đăng nhập không chuyển: mọi người đăng nhập lại một lần.

## Render
1. Tải bản sao lưu (Quản lý nhân viên → Tạo bản sao lưu).
2. Render → New → PostgreSQL, cùng region **Singapore**; gói Basic (bản Free tự xóa sau 30 ngày).
3. Copy **Internal Database URL** → service web → Environment → `DATABASE_URL` → Save, rebuild and deploy.
4. Log khởi động có `Migration committed; all copied fields verified.` và số dòng từng bảng.

CI (`postgres-migration-smoke`) chạy đúng quy trình này mỗi lần push: SQLite → PostgreSQL, kiểm tra API, trình duyệt,
sao lưu và khởi động lại không chép lần hai.
