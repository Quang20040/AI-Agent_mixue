# 📅 Lịch làm tuần

**Chu kỳ hằng tuần (giờ Việt Nam):**

1. **Thứ 7 00:00 → Chủ nhật 18:00** — mỗi nhân viên (chính thức, thử việc) thấy nhắc trên mọi trang: báo ngày / ca bận
   tuần sau, hoặc bấm **"Tuần sau tôi rảnh"**. Báo được trên trang 📅 Lịch làm hoặc nói với Tuyết Vương
   ("mai em bận ca tối", "tuần sau em rảnh"). Quản lý xem ai đã / chưa trả lời.
2. **Chủ nhật 18:00** — Tuyết Vương tự xếp lịch tuần sau (ai không trả lời = rảnh cả tuần) và để bản nháp trong hàng chờ
   duyệt của Quản lý. Chạy một lần (không xếp lại nếu tuần đó đã có lịch — kể cả lịch đã bị Quản lý hủy).
3. **Quản lý** sửa từng ô nếu cần → **Duyệt & gửi** → nhân viên thấy lịch trên trang chủ / trang Lịch làm / hỏi AI.
4. **Nhắc ca:** trong app, 3 giờ trước ca ("Sắp đến ca chiều lúc 13:00"), trong ca, và từ 17:00 hôm trước ("Mai bạn làm ca sáng").

**Quy tắc xếp:** không xếp vào ca đã báo bận; tối đa 2 ca/ngày và phải liền nhau; ưu tiên ca chính; chia đều;
mỗi ca có ít nhất 1 nhân viên chính thức nếu được. Số người mặc định sáng 1 · chiều 2 · tối 2, sửa được từng ngày.

**Cấu hình (Render → Environment, không bắt buộc):**

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `SHIFT_TIMES` | `07:00-13:00,13:00-18:00,18:00-22:30` | giờ ca sáng, chiều, tối (dùng để nhắc ca) |
| `SCHEDULE_ASK_FROM_WEEKDAY` | `5` | ngày bắt đầu hỏi lịch bận (0 = thứ 2 … 5 = thứ 7) |
| `SCHEDULE_DEADLINE_HOUR` | `18` | giờ chốt Chủ nhật |
| `SCHEDULE_AUTO` | `1` | `0` để tắt tự xếp |

Nhắc nhở hiện trong app khi nhân viên mở app; chưa gửi Zalo / SMS / thông báo điện thoại.
