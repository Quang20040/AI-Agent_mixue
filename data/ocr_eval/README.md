# Bộ ảnh thật có đáp án để kiểm định OCR

`real_photos.json` mô tả từng ảnh và đáp án từng trường tiền. Đáp án hiện tại lấy từ
các báo cáo chốt ca **đã duyệt** ngày 14/10/2026 trong `data/shift_reports.json`
(nhân viên nhập tay từ chính các ảnh này). `tests/test_ocr_benchmark.py` kiểm tra
đáp án luôn khớp với các báo cáo đó.

## Chạy

| Chế độ | Cần mạng/API | Việc làm |
|---|---|---|
| `live` | Có (`LLM_ENABLED=true`, `ALLOW_EXTERNAL_DATA_TRANSFER=true`) | Gửi từng ảnh tới mô hình Vision, lưu bản đọc thô vào `readings/<case_id>.json` (kèm mô hình, độ trễ, token) rồi chấm |
| `replay` | Không | Chấm lại các bản đọc đã lưu bằng pipeline kiểm chứng hiện tại — dùng khi bảo vệ không có mạng |

```bash
python -m scripts.run_live_evaluation          # chạy live + ghi báo cáo vào reports/
```

Hoặc trên giao diện: trang **📸 Chốt Ca & Đối Soát OCR** → **🧪 Kiểm định & Phân loại lỗi OCR** → chọn *Ảnh thật của cửa hàng*.

## Thêm ảnh mới

1. Chép ảnh vào `data/shift_photos/` (JPG/PNG/WebP ≤ 10 MB).
2. Thêm một phần tử vào `cases` của `real_photos.json`:

```json
{
  "case_id": "REAL_CA_SANG_20261102",
  "image": "data/shift_photos/20261102_ca_sang.jpg",
  "image_type": "handwritten_ledger",
  "title": "Ảnh thật · sổ ca sáng 02/11",
  "shift_hint": "CA_SANG",
  "target_date": "2026-11-02",
  "expect_inconsistency": false,
  "note": "Ghi chú bẫy bố cục, vùng bị che…",
  "fields": {
    "cash_vnd": {"expected_value": 700000, "expected_source": "handwritten_ledger", "should_be_uncertain": true, "expected_raw_contains": "700"},
    "petty_cash_kept_vnd": {"expected_value": 1000000, "expected_source": "handwritten_ledger"},
    "pos_revenue_vnd": {"expected_value": null}
  }
}
```

Quy ước đáp án:

- `expected_value`: số đúng tính bằng đồng; `null` nếu trường không có hoặc bị che trên **ảnh này**.
- `should_be_uncertain: true` khi số viết tắt không ghi đơn vị (`700` nghĩa là 700.000 đ), là biểu thức cần cộng (`962 + 629`, `41k + 15k`) hoặc bị che một phần — hệ thống đúng khi **để trống và gắn cờ**. Thêm `"uncertain_cause": "calculation"` cho biểu thức.
- `expected_source`: `pos_receipt` hoặc `handwritten_ledger` — vùng chứng từ chứa số đúng.
- `expect_inconsistency: true` khi chính số trên sổ không cộng khớp; hệ thống đúng khi cảnh báo mà không sửa số.

Mỗi ca nên được một người thứ hai đối chiếu lại với ảnh; ghi tên người đối chiếu vào `verified_by`.
