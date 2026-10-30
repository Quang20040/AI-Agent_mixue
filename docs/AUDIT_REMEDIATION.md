# Bản sửa sau kiểm toán — 22/10/2026

Cập nhật sau bản sửa: PostgreSQL đã được khởi động, chuyển dữ liệu và xác minh MCP thật; xem [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md). Những giới hạn PostgreSQL chưa chạy trong báo cáo dưới đây là trạng thái tại lần kiểm thử trước chuyển.

Bản kiểm toán trong `audit-reports/` giữ nguyên làm bằng chứng trước sửa. Tài liệu này mô tả thay đổi trong mã nguồn và kết quả kiểm thử bổ sung; không đổi các FAIL cũ thành PASS bằng cách sửa báo cáo.

## Thay đổi theo phát hiện

| Phát hiện | Thay đổi | Bằng chứng hồi quy |
|---|---|---|
| BUG-01,04 | Không seed tài khoản mặc định ngoài demo; role lạ bị từ chối; provisioning riêng; mật khẩu mạnh và mật khẩu tạm ngẫu nhiên | test_audit_remediation: default_admin, auth_role |
| BUG-02,03,05 | Service đọc tài khoản thật, kiểm active/role; chỉ duyệt hoặc từ chối phiếu PENDING; chốt ca bắt buộc người thực hiện | stock authorization/transitions và shift authorization |
| BUG-06,07 | Kiểm ngày/ca, số tiền nguyên hữu hạn, giới hạn giá trị; merge trước khi tính lại tổng | money validation/partial update |
| BUG-08,09 | JSON hỏng báo lỗi, không sinh báo cáo mẫu; báo cáo phân biệt per_shift/daily_cumulative, hỗ trợ cash=0 | corruption và cashless summary |
| BUG-10 | BOM theo ngày hiệu lực, không cộng công thức optional; chặn phiên bản chồng lấn | BOM và optimizer effective date |
| BUG-11,17 | Sales/forecast được giới hạn STORE_ID; một cửa hàng có thể suy ra, nhiều cửa hàng phải cấu hình; thiếu dự báo không hiển thị thành số 0 | tenant isolation/store inference |
| BUG-12,13,14 | Bảng kho theo lịch tháng và toàn danh mục; cho phép kiểm kê 0; kiểm nguyên liệu và FK; sửa ô tổng không duyệt nhầm phiếu chờ | monthly matrix/zero count/entity/manual aggregate |
| BUG-15 | DATABASE_URL của tiến trình quyết định backend, không cần POSTGRES_ACTIVE và không tự chuyển PostgreSQL lỗi thành SQLite | engine-selection test; chưa có PostgreSQL thật để kiểm kết nối |
| BUG-16 | Mã TP không tồn tại không nhận citation của mã khác; mã tường minh giới hạn tập kết quả | synthetic explicit entity test/SOP tests |
| GAP-01 | Lưu số lần đăng nhập sai trong DB, chặn tạm sau 8 lần, có hồi phục | throttle expiry test |
| OPP-01 | Nạp dữ liệu bảng kho bằng hai query theo lô | query-count test |
| SUS-01, GAP-02 | Runtime Docker dùng /opt/venv; loại secrets, DB, ảnh, backup khỏi build context | kiểm tra mã/cấu hình; chưa build Docker |
| SUS-02,03 | Giữ số 0 trong OCR; khóa file liên tiến trình cho JSON và kho; fsync trước thay thế JSON | OCR confirm/missing field và 4-process write test; UI OCR ảnh thật chưa chạy |

## LangGraph, RAG và bộ nhớ

Graph có state và đường chuyển có điều kiện, gọi tool có kiểm quyền, giới hạn số bước/thời gian, chờ duyệt và tiếp tục theo thread. Kiểm thử kiểm tra việc thực sự chạy service trong vòng model–tool, từ chối thao tác không có quyền và khôi phục hội thoại. Trước lượt mới, checkpoint hiện hành được thu gọn theo giới hạn lịch sử; transcript vẫn được lưu riêng. Những phiên bản checkpoint cũ trên đĩa cần chính sách lưu giữ riêng, chưa tự xóa dữ liệu người dùng.

Truy xuất hiện dùng BM25, character n-gram và reranker theo thực thể/quy tắc, không phải cross-encoder học sâu. Chunk có định danh/hash; bộ đánh giá yêu cầu đúng file và mã nguyên liệu. Kết quả tool lỗi không được dùng làm bằng chứng. Citation giúp truy vết nguồn, không chứng minh mọi câu trong câu trả lời được nguồn hỗ trợ. Chưa có đánh giá độc lập đủ rộng về semantic entailment, tài liệu mâu thuẫn và câu hỏi ngoài tập chuẩn.

PostgreSQL MCP có hai tool chỉ đọc, transport stdio thật và kiểm thử protocol; xem `POSTGRES_MCP.md`. Chưa bật MCP trên dữ liệu cửa hàng.

## Backup và vận hành

`scripts/backup_restore.py --backup --maintenance` tạo bundle gồm SQLite, JSON chốt ca, checkpoint/hội thoại và ảnh trong `data/`, có SHA256 và kiểm tra integrity. Phải dừng worker ghi trước khi chạy; cờ maintenance là xác nhận điều kiện này, không tự dừng ứng dụng. Restore kiểm tra toàn bundle trước khi ghi, giữ bản an toàn của dữ liệu hiện tại. Công cụ từ chối PostgreSQL hoặc datastore ngoài thư mục được hỗ trợ; PostgreSQL cần quy trình pg_dump/restore riêng.

Production không có nút vào nhanh bằng tài khoản mẫu. Chưa đặt lại mật khẩu của người dùng hiện hữu; quản trị dùng `scripts/provision_admin.py --reset-existing` với mật khẩu nhập kín. Không đưa thông tin đăng nhập vào chat/log.

## Phạm vi xác minh và việc còn lại

- Lượt tổng hợp cuối: **122 PASS, 0 FAIL** trong 93,60 giây, bằng chứng `output/remediation-final-results.xml`. Bao gồm hồi quy sau kiểm toán, LangGraph, bộ nhớ, SOP retrieval, câu trả lời có nguồn, thời tiết/dự báo, scorecard và MCP. Ruff và compile kiểm tra thành công. Đây là nhóm kiểm thử được chọn cho phạm vi sửa, không phải tuyên bố toàn bộ suite cũ đều đạt.
- Trong nhóm trên, MCP có 7 ca đạt, bao gồm discovery/gọi qua stdio, timeout, chặn tool ngoài danh sách, che thông tin kết nối và transaction chỉ đọc (DB giả). Các lần chạy thất bại trước sửa schema SDK được giữ nguyên làm lịch sử; kết quả cuối độc lập `output/mcp-results-6.xml`: 7 PASS.
- UI smoke trên bản sao chỉ chứa dữ liệu giả: đăng nhập production, không có lối vào demo, mở kho và chuyển tháng 11 đều đạt. Bằng chứng `output/remediation-ui-9bd1d901/result.txt`. Đây là Streamlit AppTest, chưa phải kiểm thử trình duyệt toàn bộ hay thiết bị thật.
- PostgreSQL trong `.env` trỏ `127.0.0.1:5432/beverageops`; cổng chưa hoạt động, driver khai báo chưa cài, URL MCP chưa có. Database chính mặc định vẫn là SQLite nếu tiến trình không được cấp DATABASE_URL. Chưa chuyển dữ liệu thật hoặc tạo server PostgreSQL.
- Chưa build/run Docker do daemon không hoạt động. Chưa đo tải 100 người dùng, chưa chứng minh khả năng nhiều máy chủ, chưa nghiệm thu OCR/model thật hay chất lượng RAG trên tập độc lập mới.
- Kho/JSON vẫn theo mô hình một cửa hàng mỗi cài đặt; scope sales không đồng nghĩa toàn bộ hệ thống đã hỗ trợ SaaS nhiều cửa hàng.

Không kết luận hệ thống sẵn sàng production chỉ từ các kiểm thử này. Các kiểm thử cũ phụ thuộc danh mục/dữ liệu riêng cần được chuyển sang fixture độc lập trước khi dùng toàn suite làm cổng phát hành.
