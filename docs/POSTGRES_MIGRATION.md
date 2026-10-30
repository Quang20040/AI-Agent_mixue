# Chuyển SQLite sang PostgreSQL — 22/10/2026

PostgreSQL 16 chạy bằng Docker Compose tại `127.0.0.1:15432`, database `beverageops`. Cổng 5432 bị Windows chặn nên dùng 15432. Không xóa hoặc sửa dữ liệu SQLite gốc.

## Sao lưu trước chuyển

- Bundle toàn bộ dữ liệu ứng dụng: `backups/snapshot_20261022_103910_9826d8d4/`, có manifest và checksum, gồm SQLite, JSON, bộ nhớ/checkpoint và ảnh.
- PostgreSQL trước chuyển: `backups/postgres_before_migration_20261022_103925/postgres.dump`, định dạng pg_dump custom.
- Snapshot SQLite dùng để chuyển: `backups/sqlite_to_postgres_20261022_01/source.sqlite`.
- PostgreSQL sau chuyển: `backups/sqlite_to_postgres_20261022_01/postgres_after_migration.dump`; đã kiểm tra pg_restore đọc được danh mục dump.

Không có tiến trình ứng dụng Python/Streamlit đang chạy tại thời điểm kiểm tra trước sao lưu. SQLite integrity_check đạt, foreign_key_check không có vi phạm. Các bảng PostgreSQL đều trống trước chuyển.

## Kết quả

| Bảng | SQLite | PostgreSQL |
|---|---:|---:|
| ingredients | 73 | 73 |
| menu_items | 39 | 39 |
| operation_plans | 93 | 93 |
| users | 4 | 4 |
| daily_stock_movements | 138 | 138 |
| purchases | 468 | 468 |
| recipe_bom | 120 | 120 |
| sales_daily | 3.588 | 3.588 |
| stock_counts | 240 | 240 |
| topping_daily | 552 | 552 |

Tổng bán hàng: **152.072 ly**, **3.554.264.000 đồng**. Mỗi bản ghi được đọc bằng kiểu dữ liệu schema ứng dụng và so sánh SHA256 của toàn bộ trường sau chuẩn hóa JSON, ngày và Decimal. Kiểm tra không chỉ dựa vào số dòng. PostgreSQL sequence được đưa về sau ID lớn nhất để lần ghi tiếp theo không đụng ID cũ.

Chuyển trong một transaction PostgreSQL, khóa các bảng trước kiểm tra trống, không có thao tác xóa/ghi đè. Công cụ dừng khi đích không trống, schema khác hoặc checksum không khớp. Kiểm thử riêng xác minh giữ nguyên trường, từ chối ghi đè và rollback khi insert thất bại.

Bằng chứng: `backups/sqlite_to_postgres_20261022_01/verification.json`.

## MCP và cấu hình ứng dụng

MCP đã gọi server stdio và tra bán hàng bằng tài khoản `mixue_mcp`. Tổng ly/doanh thu khớp snapshot SQLite. Kiểm tra quyền bằng tài khoản thật: đọc sales được phép; INSERT sales và đọc users đều không được phép. Bằng chứng: `backups/sqlite_to_postgres_20261022_01/mcp-verification.json`.

Đã bật POSTGRES_MCP_ENABLED=true sau khi kiểm tra. Xác minh ứng dụng thật: backend PostgreSQL, tool bán hàng trả backend postgresql_mcp, tổng bán BOM khớp 152.072 ly và bảng kho có 73 nguyên liệu. Bằng chứng `backups/sqlite_to_postgres_20261022_01/application-verification.json`. Nhóm hồi quy cho lần chuyển: 49 PASS trong `output/remediation-postgres-switch-tests.xml`.

Database ứng dụng đọc DATABASE_URL theo thứ tự: môi trường tiến trình → `.env` → SQLite mặc định nếu URL trống. Không tự chuyển sang SQLite khi PostgreSQL đã cấu hình nhưng bị lỗi. MCP có URL riêng dùng tài khoản chỉ đọc, cùng database và STORE_ID với ứng dụng.

Sau chuyển, mở PowerShell mới để tránh biến DATABASE_URL cũ còn lưu trong terminal. Khởi động bằng `python -m streamlit run src/dashboard/app.py`. Không chạy `src/ingestion.py` để nhập lại dữ liệu vừa chuyển.

JSON chốt ca, ảnh, transcript/checkpoint vẫn ở các file hiện hữu; lần chuyển này chuyển các bảng nghiệp vụ ORM sang PostgreSQL, không chuyển toàn bộ file thành bảng. SQLite cũ là bản lưu tại thời điểm chuyển, không còn đồng bộ các thay đổi mới của PostgreSQL.

## Quay lại và sao lưu tiếp theo

Trước khi quay về SQLite, dừng worker ghi và sao lưu PostgreSQL mới nhất. Đặt DATABASE_URL về file SQLite dự kiến và POSTGRES_MCP_ENABLED=false; khởi động lại trong terminal mới. Nếu PostgreSQL đã có thay đổi sau chuyển, phải đối soát/chuyển ngược trước khi quay về để không bỏ mất thay đổi đó.

`scripts/backup_restore.py` là công cụ bundle SQLite/file, từ chối cấu hình PostgreSQL để tránh báo sao lưu nhầm. Từ nay phải sao lưu PostgreSQL bằng pg_dump cùng với backup các file JSON/media/checkpoint. Các bản dump/backup chứa dữ liệu riêng, không commit lên Git.
