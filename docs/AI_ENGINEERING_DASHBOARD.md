# 🛠️ Kỹ thuật AI — dashboard cho người vận hành trợ lý

Trang chỉ Chủ quán / Quản lý (vai trò admin) thấy được. Mỗi tab ứng với một chủ đề xây dựng agent; số liệu chọn
theo 7 / 14 / 30 ngày. API: `GET /api/v1/stores/{store_id}/ai-metrics?days=14` (admin).

| Tab | Chủ đề | Số liệu |
|---|---|---|
| 🛡️ Guardrail | Ngày 11 – guardrail & red teaming | lượt kiểm tra / bị chặn theo loại; RBAC từ chối theo tool; **red team chạy trực tiếp** (`experiments/guardrail_redteam.json`: câu tấn công phải bị chặn đúng loại, câu hỏi thường của quán không bị chặn nhầm) |
| 🧰 Tool calling | Ngày 06 – function calling & tool contracts | lượt gọi, % thành công, độ trễ p50/p95 mỗi tool; được phép / từ chối quyền / sai tham số |
| ✋ Human-in-the-loop | Ngày 05 – maker–checker | lượt dừng chờ duyệt, duyệt / từ chối, số lần ghi qua bước duyệt; kế hoạch & đơn theo trạng thái, đơn Quản lý sửa số AI |
| 📚 RAG | Ngày 08–09 – grounding | % tra cứu có nguồn, % câu trả lời có dẫn chứng; **bảng so sánh BM25 / vector / RRF / learning-to-rank** |
| 📸 Vision OCR | đọc sổ giao ca, hóa đơn POS | **độ chính xác từng ô** (số OCR điền sẵn so với số được duyệt), % báo cáo không phải sửa, thời gian một lần gọi OCR |
| ⏱️ Tracing & chi phí | Ngày 12–13 – observability, fallback | độ trễ theo chế độ trả lời, lượt gọi mô hình & token mỗi lượt, lượt chạy dự phòng, chi phí theo chức năng |
| 🧪 Benchmark | Ngày 14 – golden suite | 50 tình huống có đáp án; nút chạy offline hoặc với Gemini |
| 🧠 Bộ nhớ hội thoại | Ngày 07 – multi-turn memory | cuộc trò chuyện, bản tóm tắt, 👍/👎 |

## Dữ liệu lấy từ đâu

- `agent_turns` (cùng file `llm_usage.db`, thư mục dữ liệu riêng): mỗi lượt chat một dòng — chế độ trả lời,
  trạng thái, độ trễ, kết quả guardrail, các bước trace (tool, quyền, duyệt, số token). **Không lưu câu hỏi,
  câu trả lời, tham số tool hay kết quả tool.** Lượt chạy benchmark (`user_id` bắt đầu bằng `evaluation-`) không ghi.
- `llm_usage`: token, chi phí, thời gian mỗi lần gọi OCR.
- `conversations.sqlite` → `ocr_shift_drafts`: `field_readings` (số OCR đọc) và `fields` (số nhân viên kiểm tra,
  Quản lý duyệt). Ô không có trên giấy và không ai điền thì không tính.
- `operation_plans`: trạng thái kế hoạch / đơn, người duyệt, lịch sử sửa số.
- Offline: `src/agent/multi_agent/sop_ranker.json` (đánh giá tra cứu, gồm baseline RRF —
  `python scripts/train_sop_ranker.py --baselines-only`), `scorecard.json` (benchmark agent).
