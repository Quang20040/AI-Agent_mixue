# Kiểm tra RAG và LangGraph — 22/10/2026

## Kết quả đo

Benchmark SOP hiện có: 30 câu (24 positive, 6 negative). Sửa lỗi evaluator
chấp nhận đúng file HOẶC đúng entity thành yêu cầu đúng cả hai khi có khai báo.
Trước sửa ranking: Hit@1 58,33%, Hit@3 75%, MRR 0,6972.
Sau sửa ranking theo ý định công thức và quy tắc topping: Hit@1 91,67%,
Hit@3 95,83%, Hit@5 95,83%, MRR 0,9306, từ chối negative 100%.
Kết quả từng câu: `output/rag-audit-report.json`.
Đây là benchmark dùng trong quá trình sửa, chưa phải holdout độc lập hoặc tỷ lệ
trả lời đúng của LLM chạy production. Không suy rộng 100% từ 6 câu negative.

## Chunking, retrieval, reranker

- SOP Markdown: cửa sổ 1.500 ký tự, bước 1.200, giữ phần đuôi.
- Markdown kiến trúc/audit: theo heading, chia tiếp section dài thành cửa sổ
  tối đa 1.500 ký tự, overlap phần thân 200 ký tự, lặp heading.
- CSV: từng dòng có metadata; bảng <=60 dòng còn có chunk toàn bảng.
  Chunk toàn bảng chưa có giới hạn ký tự, có thể chiếm nhiều context.
- Retrieval: BM25 + character trigram + coverage + boost thực thể/ý định.
  Ranking tính trực tiếp trên corpus, chưa có dense vector index hay một
  cross-encoder reranker độc lập. Điểm không phải xác suất đúng.
- Negative rejection hiện có danh sách từ khóa; cần tập ngoài phạm vi độc lập,
  câu mơ hồ, nhiều thực thể và dữ liệu mâu thuẫn để đánh giá tổng quát.

## Citation

Search hit có chunk ID ổn định, SHA-256 nội dung, file, row/char offsets khi có,
trạng thái xác nhận nguồn (UNKNOWN nếu thiếu). Tool search_operating_knowledge
trả ref tới chunk. Nguồn từ tool lỗi không được gom vào evidence của graph.
Hash kiểm tra định danh nội dung, không xác thực tài liệu gốc hay độ đúng SOP.
Các tool khác vẫn có nguồn cấp bảng/file/policy; chưa có kiểm tra entailment
từng claim, freshness, hoặc bảo đảm mọi nguồn đều đã được con người xác nhận.

## State, node, edge

AgentState gồm messages (add_messages reducer), query, run_id, response,
tool_count, model_count, evidence, results, trace, prepared, draft_cache.
Các collection ngoài messages do node sao chép/cập nhật tuần tự, không chạy
các nhánh tool song song. Actor là context máy chủ, không lấy quyền từ model.

START → guard → model hoặc offline. Model → authorize → tools → model.
Authorize có thể kết thúc hoặc chuyển approval; approval dùng interrupt,
resume kiểm tra lại quyền và digest dự thảo; offline_result → END.
Đã khai báo tập đích cho từng conditional edge để graph xuất đúng topology.
Schema/Pydantic, quyền server, retry đọc, giới hạn gọi và audit đã có sẵn.
Trace ghi tên tool, trạng thái, thời lượng; không ghi đầy đủ tham số riêng tư.

## Memory

SQLite checkpointer lưu graph qua restart; namespace gồm store/user/role/chat.
ConversationStore lưu transcript, preferences allowlist và summary có refs.
History gửi model giới hạn số message và bỏ cặp tool-call/tool-result dở dang.
Checkpoint lưu toàn bộ lịch sử trên đĩa, chưa có compaction/TTL/token budget.
Summary có refs và lọc lỗi theo nội dung; refs không tương đương đã xác minh
ngữ nghĩa. Dữ liệu kho/doanh thu ở lượt trước vẫn cần tra mới khi trả lời.

## MCP và tools

Ứng dụng hiện dùng ToolSpec + StructuredTool trong graph_tools.py, chưa có
MCP client/server, transport, discovery hoặc cấu hình endpoint. Các connector
của môi trường Codex không tự trở thành MCP của ứng dụng này.
Không tự nối dịch vụ ngoài khi chưa có endpoint và nghiệp vụ cụ thể.
Registry gồm thời tiết, coverage, sales/analytics, ca, kho, hao hụt, forecast,
recipe, SOP, knowledge, nhân sự, thông tin cửa hàng, preview/tạo dự thảo,
lịch sử/phê duyệt kế hoạch, đọc/sửa/xác nhận dự thảo OCR.
Tool public/admin được lọc trước khi bind model và kiểm lại khi execute.

## Giới hạn nghiệm thu

Không gọi API LLM trả phí trong đợt kiểm tra này. Test dùng model kịch bản
nhưng chạy graph thật. Chưa thể tuyên bố AI không hallucinate hoặc MCP đã
hoàn thiện; cần endpoint MCP cụ thể và tập đánh giá câu trả lời có nhãn độc lập.
