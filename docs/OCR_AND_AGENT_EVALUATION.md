# OCR, truy xuất SOP và đánh giá agent

## Đọc ảnh

`extract_shift_data_from_image` gọi mô hình vision với nội dung ảnh, không suy
ra số liệu từ tên file/ca. API dùng cấu hình và quyền gửi dữ liệu hiện có;
`OCR_MODEL` cho phép chọn riêng mô hình đọc ảnh. Không có cấu hình hoặc gọi lỗi
thì không tạo số liệu mẫu. Không tự chuyển sang mô hình trả phí.

Trên màn hình chốt ca: chọn đúng ca và ngày → chọn ảnh → bấm **Đọc ảnh bằng AI**.
Ảnh được gửi sang nhà cung cấp đã cấu hình. Xem phần văn bản và từng trường đọc
được, sửa ô sai hoặc điền ô trống. Trường không phát sinh phải do người dùng xác
nhận bằng cách nhập 0; ô trống không mặc định là 0. Xác nhận đã đối chiếu rồi
mới lưu. Có thể nhập tay khi không dùng API. Không có thao tác ghi kho từ OCR.

Các trạng thái trường: `read`, `uncertain`, `not_present`, `unreadable`. Đây là
nhận định của mô hình, không phải confidence đã được hiệu chuẩn. Ngày trên ảnh
khác ngày chọn sẽ cảnh báo. Đọc được chưa có nghĩa đã được phê duyệt. OCR chạy
cả trên màn hình chốt ca và trực tiếp trong chat LangGraph; cả hai chỉ ghi sổ sau
khi Quản lý phê duyệt tại `interrupt()`.

Kiểm định OCR theo 7 nhóm lỗi: `run_ocr_benchmark` (4 ảnh tổng hợp) và
`run_dataset_benchmark` (ảnh thật có đáp án trong `data/ocr_eval/`, chế độ `live`
lưu bản đọc thô, chế độ `replay` chấm lại offline). Chạy toàn bộ phần thực nghiệm:
`python -m scripts.run_live_evaluation` → `reports/evaluation_<thời điểm>.md`.

Ảnh JPG/PNG/WebP giới hạn 10 MB, 20 triệu pixel tại bộ đọc. Tải ảnh lên đặt tên
theo hash thay vì dùng tên file làm nội dung. Uploads không đưa vào Git. Việc
lưu trữ/xóa ảnh theo thời hạn vẫn cần chính sách triển khai chính thức.

Kiểm tra API với hai ảnh phiếu tổng hợp giả lập (không gửi ảnh cửa hàng):

```powershell
python -m scripts.check_ocr_api
```

Kết quả này chỉ chứng minh kết nối và đọc chữ in trên ảnh thử; không chứng minh
đọc tốt ảnh viết tay, ảnh mờ hoặc mọi loại phiếu của cửa hàng.

## SOP

Chia cửa sổ tối đa 1.500 ký tự, chồng lấn 200 ký tự và ưu tiên ngắt theo dòng.
Nội dung cuối tài liệu/bảng không còn bị cắt mất. Metadata giữ vị trí ký tự
để đối chiếu. Vẫn là BM25; chưa gọi đây là embedding/hybrid retrieval. Cần đo
trên câu hỏi vận hành trước khi chọn thêm embedding và reranker.

## Đánh giá

`experiments/agent_golden_v2.jsonl` có 50 trường hợp ứng viên: nhận diện, chat,
doanh số, SOP/công thức, thời tiết, bảo mật, hội thoại nhiều lượt và thiếu dữ
liệu. Bộ chấm kiểm tra riêng công cụ, trạng thái, nội dung bắt buộc/cấm, nguồn
và độ dài. Trả đúng từ khóa nhưng sai công cụ hoặc trạng thái phải trượt.

```powershell
python -m experiments.agent_scorecard
python -m experiments.agent_scorecard --live
```

Mặc định là `offline_rules`, không gọi API. `--live` dùng nhà cung cấp cấu hình
và có thể tốn hạn mức/chi phí. Lịch sử đánh giá tách khỏi tài khoản người dùng.
Báo cáo giữ hash bộ dữ liệu, chế độ chạy, mô hình thực sự dùng, token, thời
gian và kết quả từng tiêu chí. Không in khóa, ảnh hoặc toàn bộ dữ liệu công cụ.

50 trường hợp chưa qua hai người dùng cửa hàng review độc lập. Đây chưa phải
bằng chứng chất lượng nghiệp vụ được nghiệm thu. Không gộp kết quả chế độ cơ
bản và API thành một tỷ lệ; không đổi đáp án để che các lỗi đang tồn tại.

## Pilot

Tin nhắn assistant trong lịch sử có nút phản hồi hữu ích/không hữu ích, lưu
theo đúng tài khoản và tin nhắn. Báo cáo chốt ca mới lưu số ô sửa, ô nhập tay,
thời gian kiểm tra và provenance OCR. Không coi báo cáo cũ là OCR thành công.

```powershell
python -m scripts.pilot_scorecard
```

Báo cáo riêng tại `data/agent_private/pilot-scorecard.json`. Tỷ lệ hữu ích chỉ
tính trên câu đã được đánh giá; số ô sửa không đồng nghĩa OCR accuracy. Muốn
đo tiết kiệm thời gian cần ghi baseline thao tác tay cùng loại chứng từ. Muốn
chứng minh giảm hao hụt cần pilot thực tế, ghi sản lượng chuẩn bị/hủy/thiếu
hàng trước và sau và đối chiếu mức bán; hiện chưa có dữ liệu để kết luận.
