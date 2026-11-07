# PostgreSQL MCP

Ứng dụng có MCP server nội bộ chạy qua stdio, dùng SDK MCP 2.2.0. Server chỉ cung cấp `get_data_coverage` và `get_daily_sales`; không cung cấp công cụ SQL tùy ý, đọc tài khoản hay ghi dữ liệu. Agent vẫn kiểm tra quyền trước khi gọi tool. `STORE_ID` được đặt tại server, không nhận từ câu hỏi của mô hình.

Mỗi truy vấn dùng tham số ràng buộc, transaction PostgreSQL `READ ONLY`, giới hạn thời gian 5 giây và giới hạn kết quả. Client có thời gian chờ, danh sách tool cho phép, lệnh khởi chạy cố định và không chuyển khóa LLM vào môi trường server. Lỗi kết nối không được biến thành doanh thu bằng 0 và không trả URL/mật khẩu cho mô hình.

## Kiểm tra cấu hình hiện tại

Chạy `python scripts/check_database_setup.py`. Lệnh chỉ đọc cấu hình và thử mở cổng, không đăng nhập hay sửa database. Không in tài khoản/mật khẩu. Cổng mở không chứng minh đăng nhập thành công.

Đặt cấu hình trong `.env` cục bộ, không commit file này:

```dotenv
POSTGRES_MCP_ENABLED=false
POSTGRES_MCP_DATABASE_URL=postgresql+psycopg2://<readonly-user>:<password>@127.0.0.1:5432/beverageops
STORE_ID=2132
```

Tạo tài khoản PostgreSQL chỉ đọc riêng, chỉ cấp CONNECT database, USAGE schema public và SELECT trên `public.sales_daily`, `public.menu_items`. Không dùng tài khoản quản trị cho MCP. Server yêu cầu hai bảng này theo schema của ứng dụng. Không tự tạo hoặc di chuyển dữ liệu từ SQLite.

Cài dependency bằng `python -m pip install -r requirements.txt`. Nếu cấu hình URL có `+psycopg`, cần driver psycopg v3 tương ứng; dependency mặc định của dự án là psycopg2. Chọn URL đúng driver đã cài.

Sau khi PostgreSQL đã chạy và có dữ liệu, kiểm tra:

```powershell
python scripts/check_postgres_mcp.py
python scripts/check_postgres_mcp.py --query-coverage
```

Lệnh đầu kiểm tra discovery, không đọc số liệu. Lệnh sau kiểm tra quyền đọc thật. Chỉ bật `POSTGRES_MCP_ENABLED=true` khi bước đọc thật trả SUCCESS hoặc NO_DATA đúng với database dự kiến. Khi bật, lỗi MCP được trả rõ ràng; không chuyển ngầm sang một database khác.

## Giới hạn

Cập nhật triển khai 22/10/2026: đã chuyển dữ liệu thật sang PostgreSQL và kiểm tra MCP trên cùng số liệu, xem [POSTGRES.md](POSTGRES.md). Ghi chú chưa kết nối database thật bên dưới mô tả trạng thái trước lần triển khai này.

MCP hiện phục vụ hai chức năng bán hàng; các tool kho, BOM và OCR vẫn dùng service ứng dụng. Nguồn MCP được gắn `backend=postgresql_mcp` và `source_refs`; đây là dấu vết nguồn truy vấn, không phải bảo đảm diễn giải ngôn ngữ của AI luôn đúng. Đã có kiểm thử protocol với dữ liệu tổng hợp; kết nối database thật phải được xác minh riêng.

Tài liệu SDK: https://py.sdk.modelcontextprotocol.io/ và https://py.sdk.modelcontextprotocol.io/client/transports/.
