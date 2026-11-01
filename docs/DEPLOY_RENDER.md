# Deploy lên Render (dùng thật cho quán)

Cấu hình nằm trong `render.yaml`: dịch vụ Docker, gói **Starter**, vùng Singapore, ổ đĩa bền vững 1 GB gắn ở `/var/data`.
Mọi dữ liệu quán ghi ra (CSDL, báo cáo chốt ca, ảnh chứng từ, checkpoint LangGraph, nhật ký audit) nằm trên ổ đĩa này nên không mất khi deploy lại.

## Lần đầu

1. Render → **New → Blueprint** → chọn repo `Quang20040/AI-Agent_mixue`, nhánh `fix/quality-improvement`.
2. Nhập các biến bí mật Render hỏi:
   - `OWNER_USERNAME`: tên đăng nhập chủ quán (3–30 ký tự chữ thường/số/gạch dưới), ví dụ `chuquan`.
   - `OWNER_FULL_NAME`: tên hiển thị.
   - `OWNER_INITIAL_PASSWORD`: mật khẩu tạm 12–128 ký tự. Lần đăng nhập đầu sẽ bắt buộc đổi.
   - `GEMINI_API_KEY`: khóa Gemini để đọc ảnh chứng từ. Không có thì để trống và đổi `LLM_ENABLED` thành `false` (Agent chạy luật offline, OCR báo chưa bật).
3. **Apply**. Lần build đầu mất vài phút. Khi trạng thái là *Live*, mở URL `https://<tên-dịch-vụ>.onrender.com`.
4. Đăng nhập bằng tài khoản chủ quán → đổi mật khẩu → vào **Quản lý nhân viên** tạo tài khoản cho nhân viên.
5. Sau khi đã đổi mật khẩu, có thể xóa `OWNER_INITIAL_PASSWORD` khỏi Environment (lần khởi động sau sẽ báo `Owner bootstrap: SKIPPED`).

## Những lần sau

- Mỗi lần merge vào `fix/quality-improvement`, Render chờ CI (test + Docker smoke) pass rồi mới tự deploy (`autoDeployTrigger: checksPass`); CI lỗi thì bản đang chạy giữ nguyên. Dữ liệu trên `/var/data` được giữ nguyên.
- Nhật ký khởi động có một dòng `Owner bootstrap: …`:
  `PROVISIONED` (vừa tạo), `EXISTS` (đã có, không đụng mật khẩu), `SKIPPED` (không cấu hình), `WEAK_PASSWORD` / `INVALID_USERNAME` (cần sửa biến).

## An toàn

- `APP_ENV=production`: tắt nút đăng nhập nhanh và từ chối mọi mật khẩu demo `123` / `123456`.
- Ảnh chứng từ chỉ được gửi tới Gemini khi `ALLOW_EXTERNAL_DATA_TRANSFER=true`.
- Sao lưu: tab **Disks** của dịch vụ trên Render có snapshot hằng ngày; có thể tải bản sao bằng `scripts/backup_restore.py` qua Shell.

## Kiểm chứng trước khi deploy

Job CI `docker-production-smoke` build đúng image này và chạy như Render (ổ đĩa thuộc root, chế độ production):
kiểm tra health, dữ liệu nằm trên ổ đĩa, tiến trình chạy bằng `appuser`, và khởi động lại không ghi đè mật khẩu chủ quán.
