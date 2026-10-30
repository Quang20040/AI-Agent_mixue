"""Field-level OCR evaluation and error taxonomy for printed, handwritten, blurry, and multi-document images.

Never claims a calibrated accuracy percentage from a small sample of store photos.
Classifies field-level outcomes into:
- `correct_read`: Exact match on value, unit, and document source.
- `correctly_flagged_uncertain`: Ambiguous unit, multi-term calculation, blur, or conflict properly left blank (`None`) and flagged `uncertain` for human confirmation.
- `digit_error`: Wrong digits read on a clear field (e.g., `9,057,300` instead of `9,657,300`, or `5,837` instead of `115,837`).
- `unit_error`: Wrong unit scaling (e.g., raw thousands `6492` or `3260` accepted as VND or multiplied by 1,000 without explicit unit).
- `layout_error`: Value read from the wrong row/column/section (e.g., reading cup inventory `3.1 Chốt cốc` or printed rule examples as revenue/expenses).
- `wrong_document_source`: Mixing POS receipt fields into handwritten shift fields or vice versa.
- `unflagged_inconsistency`: Component sum differs from total without raising a consistency warning.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from src.engine.vision_ocr import MONEY_FIELDS


def make_synthetic_test_images() -> dict[str, bytes]:
    """Generate deterministic test images for 4 conditions: printed, handwritten, blurry, composite."""
    images: dict[str, bytes] = {}

    # 1. Printed POS receipt image (sharp, high contrast)
    img_pos = Image.new('RGB', (600, 500), 'white')
    draw_pos = ImageDraw.Draw(img_pos)
    draw_pos.rectangle([20, 20, 580, 480], outline='black', width=2)
    draw_pos.multiline_text(
        (40, 40),
        "MIXUE 39 TON QUANG PHIET\n"
        "Thong ke ban hang tai cua hang\n"
        "Ngay lam viec: 2026-10-14\n"
        "Tong doanh thu: 10,119,000 VND\n"
        "So tien thu duoc: 9,877,137 VND\n"
        "Chi tiet so tien thu duoc:\n"
        "1.Cash: 9,657,300 VND\n"
        "2.GrabFood: 104,000 VND\n"
        "3.Shopeefood: 115,837 VND",
        fill='black',
        spacing=12,
    )
    buf = io.BytesIO()
    img_pos.save(buf, format='PNG')
    images['printed_pos'] = buf.getvalue()

    # 2. Handwritten shift ledger simulation (lined paper with handwritten-style strokes)
    img_hw = Image.new('RGB', (650, 520), (248, 246, 238))
    draw_hw = ImageDraw.Draw(img_hw)
    for y in range(60, 480, 40):
        draw_hw.line([(30, y), (620, y)], fill=(180, 190, 210), width=1)
    draw_hw.multiline_text(
        (45, 30),
        "BAO CAO DOANH THU CAC CA TRONG NGAY\n"
        "Ngay 14/10/26 - 1. Ca sang ban giao (8h-13h)\n"
        "Tien mat: 653\n"
        "Chuyen khoan: 962 + 629\n"
        "Shopee food: 16\n"
        "Be food: 0\n"
        "Grab food: 30\n"
        "Co dinh ket: 1.000.000d\n"
        "Tong thu ve: 2328 | Ky: Ha",
        fill=(25, 45, 130),
        spacing=16,
    )
    buf_hw = io.BytesIO()
    img_hw.save(buf_hw, format='PNG')
    images['handwritten_ledger'] = buf_hw.getvalue()

    # 3. Blurry low-contrast image
    img_blur = img_pos.copy().convert('RGB')
    # Compress dynamic range to low contrast and apply heavy Gaussian blur
    img_blur = Image.blend(img_blur, Image.new('RGB', img_blur.size, (200, 200, 200)), alpha=0.78)
    img_blur = img_blur.filter(ImageFilter.GaussianBlur(radius=4.5))
    buf_blur = io.BytesIO()
    img_blur.save(buf_blur, format='JPEG', quality=55)
    images['blurry_image'] = buf_blur.getvalue()

    # 4. Multi-document composite image (POS receipt on left, handwritten ledger on right)
    img_comp = Image.new('RGB', (900, 520), (245, 242, 232))
    img_comp.paste(img_pos.resize((420, 500)), (10, 10))
    img_comp.paste(img_hw.resize((440, 500)), (450, 10))
    buf_comp = io.BytesIO()
    img_comp.save(buf_comp, format='PNG')
    images['composite_multi_doc'] = buf_comp.getvalue()

    return images


def classify_field_reading(
    field_name: str,
    extracted: dict[str, Any],
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    """Classify a single field reading against ground truth and error taxonomy."""
    readings = extracted.get('field_readings', {})
    r = readings.get(field_name, {})
    form_val = extracted.get(field_name)
    raw_val = r.get('value')
    status = r.get('status', 'not_present')
    explicit_source = r.get('source', 'unknown')
    source = explicit_source
    evidence = r.get('evidence', '')
    if source == 'unknown' and evidence:
        ev_low = evidence.lower()
        if 'pos receipt' in ev_low or 'pos:' in ev_low:
            source = 'pos_receipt'
        elif 'handwritten' in ev_low or 'sổ' in ev_low:
            source = 'handwritten_ledger'

    expected_val = ground_truth.get('expected_value')
    expected_source = ground_truth.get('expected_source')
    should_be_uncertain = ground_truth.get('should_be_uncertain', False)
    expected_raw_contains = ground_truth.get('expected_raw_contains')

    # 1. Check layout error (cup inventory 3.1 or printed footnote example confused as money)
    if re.search(r'\b(899|323|947|ốc quế|móc chìa khoá|chuyển khoản nhầm 100k|trả lại khách 81k)\b', evidence, re.IGNORECASE) or (
        'còn lại' in evidence.lower() and form_val in {899, 323, 947, 179, 439, 956, 325, 198, 2219}
    ):
        if status == 'read' and form_val is not None and form_val in {899, 323, 947, 179, 439, 956, 325, 198, 2219, 100000, 81000}:
            return {
                'field': field_name,
                'passed': False,
                'outcome': 'layout_error',
                'detail': 'Đọc nhầm bảng đếm cốc/quà tặng (3.1) hoặc ví dụ in sẵn thành số tiền đã xác nhận.',
            }

    # 2. Check wrong document source (e.g. POS receipt value auto-filled into handwritten shift field)
    if expected_source and explicit_source not in {'unknown', 'not_applicable', expected_source}:
        if status == 'read' and form_val is not None:
            return {
                'field': field_name,
                'passed': False,
                'outcome': 'wrong_document_source',
                'detail': f'Sai nguồn chứng từ: đọc từ {explicit_source} thay vì {expected_source}.',
            }

    # 3. If the field is ambiguous/calculated/conflicting on the image and MUST be left blank for human confirmation
    if should_be_uncertain:
        if form_val is None and status in {'uncertain', 'unreadable', 'not_present'}:
            raw_ok = True
            if expected_raw_contains:
                raw_text = f"{r.get('raw_text', '')} {evidence}"
                raw_ok = expected_raw_contains.lower() in raw_text.lower()
            return {
                'field': field_name,
                'passed': raw_ok,
                'outcome': 'correctly_flagged_uncertain' if raw_ok else 'missing_raw_text',
                'detail': r.get('review_reason') or 'Đã để trống trong biểu mẫu và yêu cầu người dùng xác nhận.',
            }
        # Why did it fail to be flagged uncertain?
        if form_val is not None and expected_val is not None and form_val != expected_val:
            if abs(form_val) < 10000 and expected_val >= 10000:
                return {
                    'field': field_name,
                    'passed': False,
                    'outcome': 'unit_error',
                    'detail': f'Hiểu sai đơn vị viết tay: trả {form_val} VND thay vì gắn cờ cần xác nhận ({expected_val:,} đ).',
                }
            return {
                'field': field_name,
                'passed': False,
                'outcome': 'digit_error',
                'detail': f'Sai chữ số ({form_val} vs {expected_val}) và tự điền vào biểu mẫu.',
            }
        return {
            'field': field_name,
            'passed': False,
            'outcome': 'unit_error',
            'detail': 'Trường có đơn vị mơ hồ hoặc phép cộng nhưng hệ thống tự điền thay vì để trống chờ xác nhận.',
        }

    # 4. Field is absent on the document
    if expected_val is None:
        if form_val is None and status in {'not_present', 'uncertain', 'unreadable'}:
            return {
                'field': field_name,
                'passed': True,
                'outcome': 'correct_not_present',
                'detail': 'Trường không có trên ảnh được giữ trống (null).',
            }
        return {
            'field': field_name,
            'passed': False,
            'outcome': 'layout_error',
            'detail': f'Trường không có trên ảnh nhưng lại điền {form_val}.',
        }

    # 5. Clear field that should be read accurately
    if form_val == expected_val and status == 'read':
        if expected_source and source not in {'unknown', expected_source}:
            return {
                'field': field_name,
                'passed': False,
                'outcome': 'wrong_document_source',
                'detail': f'Đúng số ({form_val}) nhưng sai nguồn ({source} vs {expected_source}).',
            }
        return {
            'field': field_name,
            'passed': True,
            'outcome': 'correct_read',
            'detail': f'Đọc đúng {form_val:,} đ từ nguồn {source}.',
        }

    # Diagnose failure on a clear field
    candidate = form_val if form_val is not None else raw_val
    if candidate is not None:
        if candidate * 1000 == expected_val or expected_val * 1000 == candidate:
            return {
                'field': field_name,
                'passed': False,
                'outcome': 'unit_error',
                'detail': f'Sai đơn vị: đọc {candidate} thay vì {expected_val}.',
            }
        if candidate != expected_val:
            return {
                'field': field_name,
                'passed': False,
                'outcome': 'digit_error',
                'detail': f'Sai chữ số: đọc {candidate:,} thay vì {expected_val:,}.',
            }

    return {
        'field': field_name,
        'passed': False,
        'outcome': 'missing_error',
        'detail': f'Không đọc được giá trị mong đợi ({expected_val:,} đ).',
    }


def evaluate_ocr_extraction_case(
    case_id: str,
    image_type: str,
    extracted: dict[str, Any],
    ground_truth_fields: dict[str, dict[str, Any]],
    expect_inconsistency: bool = False,
) -> dict[str, Any]:
    """Evaluate all monetary fields and consistency checks for one OCR extraction result."""
    field_results = {}
    error_counts: dict[str, int] = {
        'correct_read': 0,
        'correct_not_present': 0,
        'correctly_flagged_uncertain': 0,
        'digit_error': 0,
        'unit_error': 0,
        'layout_error': 0,
        'wrong_document_source': 0,
        'missing_error': 0,
    }
    for field in MONEY_FIELDS:
        gt = ground_truth_fields.get(field, {'expected_value': None})
        res = classify_field_reading(field, extracted, gt)
        field_results[field] = res
        outcome = res['outcome']
        error_counts[outcome] = error_counts.get(outcome, 0) + 1

    consistency = extracted.get('consistency', {})
    consistency_ok = (not consistency.get('is_consistent', True)) if expect_inconsistency else consistency.get('is_consistent', True)
    passed_fields = sum(1 for r in field_results.values() if r['passed'])

    return {
        'case_id': case_id,
        'image_type': image_type,
        'document_type_detected': extracted.get('document_type'),
        'passed_fields': passed_fields,
        'total_fields': len(MONEY_FIELDS),
        'consistency_check_passed': consistency_ok,
        'all_passed': passed_fields == len(MONEY_FIELDS) and consistency_ok,
        'error_taxonomy_counts': error_counts,
        'field_results': field_results,
        'discrepancies': consistency.get('discrepancies', []),
    }


def evaluate_historical_ocr_review(review_path: str | Path | None = None) -> dict[str, Any]:
    """Audit the historical store photo review (`ocr-store-photo-review.json`) field-by-field to document past failure modes."""
    path = Path(review_path or 'data/agent_private/ocr-store-photo-review.json')
    if not path.is_file():
        return {'status': 'NO_FILE'}
    raw = json.loads(path.read_text(encoding='utf-8'))
    # Ground truth on 20261014_pos_slip.jpg (POS + occluded CA_TOI notebook)
    gt = {
        'pos_revenue_vnd': {'expected_value': 10119000, 'expected_source': 'pos_receipt'},
        'pos_collected_vnd': {'expected_value': 9877137, 'expected_source': 'pos_receipt'},
        'cash_vnd': {'expected_value': 9657300, 'expected_source': 'pos_receipt'},
        'grab_food_vnd': {'expected_value': 104000, 'expected_source': 'pos_receipt'},
        'shopee_food_vnd': {'expected_value': 115837, 'expected_source': 'pos_receipt'},
        'bank_transfer_vnd': {'expected_value': 6377000, 'should_be_uncertain': True},
        'be_food_vnd': {'expected_value': None},
        'cash_diff_vnd': {'expected_value': 35000, 'should_be_uncertain': True},
        'petty_cash_kept_vnd': {'expected_value': 1000000, 'should_be_uncertain': True},
        'expenses_vnd': {'expected_value': None},
        'total_collected_vnd': {'expected_value': 9877000, 'should_be_uncertain': True},
    }
    report = evaluate_ocr_extraction_case('HISTORICAL_POS_SLIP_RAW', 'composite_multi_doc', raw, gt)
    report['note'] = (
        'Báo cáo phân tích lỗi trên kết quả OCR thô trước cải tiến: đúng pos_revenue_vnd (10,119,000) và pos_collected_vnd (9,877,137), '
        'nhưng sai chữ số cash_vnd (9,057,300 vs 9,657,300), sai chữ số shopee_food_vnd do đè watermark (5,837 vs 115,837), '
        'và hiểu sai đơn vị + tự cộng sai dòng viết tay bank_transfer_vnd (6,492 VND từ 4725+1652+115).'
    )
    return report
