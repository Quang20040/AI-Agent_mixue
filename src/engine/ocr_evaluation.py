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
        cause = ground_truth.get('uncertain_cause', 'unit')
        if cause == 'quality':
            return {
                'field': field_name,
                'passed': False,
                'outcome': 'unflagged_low_quality',
                'detail': 'Ảnh mờ/tương phản thấp nhưng hệ thống vẫn tự điền số thay vì yêu cầu xác nhận.',
            }
        if cause == 'layout':
            return {
                'field': field_name,
                'passed': False,
                'outcome': 'layout_error',
                'detail': 'Số nằm ngoài vùng tiền (bảng đếm cốc/ví dụ in sẵn) nhưng vẫn được điền vào biểu mẫu.',
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
        'unflagged_inconsistency': 0,
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
    if expect_inconsistency and consistency.get('is_consistent', True):
        # The arithmetic on the document does not add up, yet no warning was raised.
        error_counts['unflagged_inconsistency'] += 1
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


# ---------------------------------------------------------------------------
# Error-taxonomy benchmark: raw vision reading vs. verifiable OCR pipeline
# ---------------------------------------------------------------------------

#: The seven outcome groups reported in the thesis benchmark table (in display order).
TAXONOMY_7: tuple[str, ...] = (
    'correct_read',
    'correctly_flagged_uncertain',
    'digit_error',
    'unit_error',
    'layout_error',
    'wrong_document_source',
    'unflagged_inconsistency',
)

TAXONOMY_LABELS_VI: dict[str, str] = {
    'correct_read': 'Đọc đúng',
    'correctly_flagged_uncertain': 'Gắn cờ đúng (chờ xác nhận)',
    'digit_error': 'Sai chữ số',
    'unit_error': 'Sai đơn vị / tự nhân 1.000 / tự cộng',
    'layout_error': 'Sai bố cục (bảng cốc, ví dụ in sẵn)',
    'wrong_document_source': 'Sai nguồn chứng từ (POS ↔ sổ tay)',
    'unflagged_inconsistency': 'Lệch số học không cảnh báo',
}

#: Outcomes that mean a wrong number would have reached the form without a warning.
ERROR_OUTCOMES: frozenset[str] = frozenset({
    'digit_error', 'unit_error', 'layout_error', 'wrong_document_source',
    'unflagged_inconsistency', 'unflagged_low_quality', 'missing_error', 'missing_raw_text',
})


def _scripted_field(value, raw_text, source, evidence=None, status='read'):
    return {'value': value, 'status': status, 'source': source, 'raw_text': raw_text,
            'evidence': evidence or f'{source}: {raw_text}'}


def _empty_reading(document_type: str) -> dict[str, Any]:
    return {
        'fields': {name: {'value': None, 'status': 'not_present', 'evidence': '', 'raw_text': '',
                          'source': 'not_applicable'} for name in MONEY_FIELDS},
        'document_date': '2026-10-14',
        'signed_by': None,
        'bank_transfer_formula': '',
        'raw_text': '',
        'warnings': [],
        'document_type': document_type,
        'pos_region_text': '',
        'handwritten_region_text': '',
    }


def benchmark_cases() -> list[dict[str, Any]]:
    """Four benchmark cases with ground truth and a scripted raw vision reading.

    The scripted readings deliberately reproduce failure modes observed on the real
    store photos (see ``evaluate_historical_ocr_review``): auto-multiplying bare
    handwritten numbers by 1,000, auto-summing ``962 + 629``, reading the cup-count
    table (mục 3.1) as money, copying POS cash into a ledger field, the watermark
    digit error ``5,837`` instead of ``115,837``, and trusting a blurry photo.
    """
    pos = 'pos_receipt'
    hw = 'handwritten_ledger'

    # 1. Printed POS receipt: a clean reading must pass through untouched.
    printed = _empty_reading(pos)
    printed['raw_text'] = 'Thống kê bán hàng · Tổng doanh thu 10,119,000 · Số tiền thu được 9,877,137'
    printed['pos_region_text'] = printed['raw_text']
    for name, value, raw in [('pos_revenue_vnd', 10119000, '10,119,000'), ('pos_collected_vnd', 9877137, '9,877,137'),
                             ('cash_vnd', 9657300, '9,657,300'), ('grab_food_vnd', 104000, '104,000'),
                             ('shopee_food_vnd', 115837, '115,837')]:
        printed['fields'][name] = _scripted_field(value, raw, pos, f'POS receipt: {raw} VND')
    printed_gt = {name: {'expected_value': value, 'expected_source': pos} for name, value in [
        ('pos_revenue_vnd', 10119000), ('pos_collected_vnd', 9877137), ('cash_vnd', 9657300),
        ('grab_food_vnd', 104000), ('shopee_food_vnd', 115837)]}

    # 2. Handwritten ledger (ca sáng): bare numbers, a formula and a layout trap.
    ledger = _empty_reading(hw)
    ledger['raw_text'] = 'Báo cáo doanh thu các ca · Ca sáng · Tiền mặt 653 · CK 962 + 629 · Tổng thu về 2328'
    ledger['handwritten_region_text'] = ledger['raw_text']
    ledger['signed_by'] = 'Hà'
    ledger['fields'].update({
        'cash_vnd': _scripted_field(653000, '653', hw, 'Sổ ca sáng: Tiền mặt: 653'),
        'bank_transfer_vnd': _scripted_field(1591000, '962 + 629', hw, 'Sổ ca sáng: Chuyển khoản: 962 + 629'),
        'shopee_food_vnd': _scripted_field(16000, '16', hw, 'Sổ ca sáng: Shopee food: 16'),
        'grab_food_vnd': _scripted_field(30000, '30', hw, 'Sổ ca sáng: Grab food: 30'),
        'be_food_vnd': _scripted_field(0, '0', hw, 'Sổ ca sáng: Be food: 0'),
        'petty_cash_kept_vnd': _scripted_field(1000000, '1.000.000đ', hw, 'Sổ ca sáng: Cố định két: 1.000.000đ'),
        'total_collected_vnd': _scripted_field(2328000, '2328', hw, 'Sổ ca sáng: Tổng thu về: 2328'),
        # Layout trap: a cup count from table 3.1 read as an expense.
        'expenses_vnd': _scripted_field(899, '899', hw, 'Sổ ca sáng 3.1 Chốt cốc: còn lại 899'),
    })
    ledger_gt = {
        'cash_vnd': {'expected_value': 653000, 'should_be_uncertain': True, 'expected_raw_contains': '653'},
        'bank_transfer_vnd': {'expected_value': 1591000, 'should_be_uncertain': True, 'expected_raw_contains': '962 + 629'},
        'shopee_food_vnd': {'expected_value': 16000, 'should_be_uncertain': True, 'expected_raw_contains': '16'},
        'grab_food_vnd': {'expected_value': 30000, 'should_be_uncertain': True, 'expected_raw_contains': '30'},
        'be_food_vnd': {'expected_value': 0, 'expected_source': hw},
        'petty_cash_kept_vnd': {'expected_value': 1000000, 'expected_source': hw},
        'total_collected_vnd': {'expected_value': 2328000, 'should_be_uncertain': True, 'expected_raw_contains': '2328'},
        'expenses_vnd': {'expected_value': None, 'should_be_uncertain': True, 'uncertain_cause': 'layout'},
    }

    # 3. Blurry, low-contrast POS photo: one digit misread, nothing may be trusted blindly.
    blurry = _empty_reading(pos)
    blurry['raw_text'] = 'Tổng doanh thu 10,119,000 · Số tiền thu được 9,877,137 · Cash 9,057,300'
    blurry['fields'].update({
        'pos_revenue_vnd': _scripted_field(10119000, '10,119,000', pos, 'POS receipt: Tổng doanh thu: 10,119,000'),
        'pos_collected_vnd': _scripted_field(9877137, '9,877,137', pos, 'POS receipt: Số tiền thu được: 9,877,137'),
        'cash_vnd': _scripted_field(9057300, '9,057,300', pos, 'POS receipt: 1.Cash: 9,057,300'),
    })
    blurry_gt = {
        'pos_revenue_vnd': {'expected_value': 10119000, 'should_be_uncertain': True, 'uncertain_cause': 'quality'},
        'pos_collected_vnd': {'expected_value': 9877137, 'should_be_uncertain': True, 'uncertain_cause': 'quality'},
        'cash_vnd': {'expected_value': 9657300, 'should_be_uncertain': True, 'uncertain_cause': 'quality'},
    }

    # 4. Composite photo: POS receipt + ca sáng ledger side by side.
    composite = _empty_reading('composite')
    composite['raw_text'] = 'Thống kê bán hàng POS + Báo cáo doanh thu các ca (ca sáng)'
    composite['pos_region_text'] = 'Tổng doanh thu 10,119,000 · Số tiền thu được 9,877,137 · 1.Cash 9,657,300 · 3.Shopeefood 5,837'
    composite['handwritten_region_text'] = 'Ca sáng · Tiền mặt 653 · CK 962 + 629 · Cố định két 1.000.000đ · Tổng thu về 2328'
    composite['fields'].update({
        'pos_revenue_vnd': _scripted_field(10119000, '10,119,000', pos, 'POS receipt: Tổng doanh thu: 10,119,000'),
        'pos_collected_vnd': _scripted_field(9877137, '9,877,137', pos, 'POS receipt: Số tiền thu được: 9,877,137'),
        # Source leak: POS cash copied into the ledger's cash field.
        'cash_vnd': _scripted_field(9657300, '9,657,300', pos, 'POS receipt: 1.Cash: 9,657,300'),
        # Watermark digit error on the POS line, also landing in the ledger field.
        'shopee_food_vnd': _scripted_field(5837, '5,837', pos, 'POS receipt: 3.Shopeefood: 5,837'),
        'grab_food_vnd': _scripted_field(104000, '104,000', pos, 'POS receipt: 2.GrabFood: 104,000'),
        'bank_transfer_vnd': _scripted_field(1591000, '962 + 629', hw, 'Sổ ca sáng: Chuyển khoản: 962 + 629'),
        'petty_cash_kept_vnd': _scripted_field(1000000, '1.000.000đ', hw, 'Sổ ca sáng: Cố định két: 1.000.000đ'),
        'total_collected_vnd': _scripted_field(2328000, '2328', hw, 'Sổ ca sáng: Tổng thu về: 2328'),
    })
    composite_gt = {
        'pos_revenue_vnd': {'expected_value': 10119000, 'expected_source': pos},
        'pos_collected_vnd': {'expected_value': 9877137, 'expected_source': pos},
        'cash_vnd': {'expected_value': 653000, 'expected_source': hw, 'should_be_uncertain': True},
        'shopee_food_vnd': {'expected_value': 16000, 'expected_source': hw, 'should_be_uncertain': True},
        'grab_food_vnd': {'expected_value': 30000, 'expected_source': hw, 'should_be_uncertain': True},
        'bank_transfer_vnd': {'expected_value': 1591000, 'should_be_uncertain': True, 'expected_raw_contains': '962 + 629'},
        'petty_cash_kept_vnd': {'expected_value': 1000000, 'expected_source': hw},
        'total_collected_vnd': {'expected_value': 2328000, 'should_be_uncertain': True},
    }

    return [
        {'case_id': 'PRINTED_POS', 'image_key': 'printed_pos', 'title': 'Hóa đơn POS in nhiệt (rõ nét)',
         'shift_hint': None, 'reading': printed, 'ground_truth': printed_gt, 'expect_inconsistency': False},
        {'case_id': 'HANDWRITTEN_LEDGER', 'image_key': 'handwritten_ledger', 'title': 'Sổ chốt ca viết tay (ca sáng)',
         'shift_hint': 'CA_SANG', 'reading': ledger, 'ground_truth': ledger_gt, 'expect_inconsistency': True},
        {'case_id': 'BLURRY_IMAGE', 'image_key': 'blurry_image', 'title': 'Ảnh POS mờ, tương phản thấp',
         'shift_hint': None, 'reading': blurry, 'ground_truth': blurry_gt, 'expect_inconsistency': False},
        {'case_id': 'COMPOSITE_MULTI_DOC', 'image_key': 'composite_multi_doc', 'title': 'Ảnh ghép: POS + sổ viết tay',
         'shift_hint': 'CA_SANG', 'reading': composite, 'ground_truth': composite_gt, 'expect_inconsistency': True},
    ]


class _ScriptedReader:
    """Stands in for the vision model: returns a fixed JSON reading for one image."""

    def __init__(self, reading: dict[str, Any]):
        self.reading = reading

    def invoke(self, messages):  # noqa: ARG002 - interface matches a LangChain chat model
        from langchain_core.messages import AIMessage
        return AIMessage(content=json.dumps(self.reading, ensure_ascii=False))


def raw_baseline_extraction(extracted: dict[str, Any]) -> dict[str, Any]:
    """What a system without the verification layer would write into the form.

    Every number the vision model returned is trusted as-is (field_readings[*].value),
    and no arithmetic cross-check is run.
    """
    readings = {}
    form: dict[str, Any] = {}
    for name in MONEY_FIELDS:
        r = dict(extracted.get('field_readings', {}).get(name, {}))
        value = r.get('value')
        r['status'] = 'read' if value is not None else 'not_present'
        readings[name] = r
        form[name] = value
    return {**form, 'field_readings': readings, 'document_type': extracted.get('document_type'),
            'consistency': {'is_consistent': True, 'discrepancies': []}}


def _summarize(case_reports: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, int] = {}
    for report in case_reports:
        for outcome, count in report['error_taxonomy_counts'].items():
            totals[outcome] = totals.get(outcome, 0) + count
    errors = sum(count for outcome, count in totals.items() if outcome in ERROR_OUTCOMES)
    return {
        'taxonomy_counts': totals,
        'taxonomy_7': {key: totals.get(key, 0) for key in TAXONOMY_7},
        'other_counts': {key: value for key, value in totals.items() if key not in TAXONOMY_7 and value},
        'errors_reaching_form': errors,
        'fields_evaluated': sum(report['total_fields'] for report in case_reports),
    }


def run_ocr_benchmark(mode: str = 'scripted', settings=None) -> dict[str, Any]:
    """Run the four-image error-taxonomy benchmark.

    ``mode='scripted'`` (default, offline, deterministic) feeds the scripted raw
    readings through the real verification pipeline (``extract_image``): quality
    check, unit/calculation/source rules and arithmetic cross-checks.

    ``mode='live'`` sends the same synthetic images to the configured vision
    provider instead. Cases the provider cannot read are reported as skipped.

    Both modes also score a *raw baseline* (model numbers trusted as-is) so the
    contribution of the verification layer is visible. Results describe these four
    synthetic images only; they are not a calibrated accuracy figure.
    """
    from src.engine.vision_ocr import extract_image

    if mode not in {'scripted', 'live'}:
        raise ValueError("mode must be 'scripted' or 'live'")
    images = make_synthetic_test_images()
    verified_reports, raw_reports, cases = [], [], []
    for case in benchmark_cases():
        model = _ScriptedReader(case['reading']) if mode == 'scripted' else None
        extracted = extract_image(image_bytes=images[case['image_key']], model=model,
                                  shift_hint=case['shift_hint'], target_date='2026-10-14', settings=settings)
        entry = {'case_id': case['case_id'], 'image_key': case['image_key'], 'title': case['title'],
                 'shift_hint': case['shift_hint'], 'status': extracted.get('status')}
        if extracted.get('status') != 'NEEDS_REVIEW':
            entry['skipped_reason'] = extracted.get('message') or extracted.get('status')
            cases.append(entry)
            continue
        verified = evaluate_ocr_extraction_case(case['case_id'], case['image_key'], extracted,
                                                case['ground_truth'], case['expect_inconsistency'])
        raw = evaluate_ocr_extraction_case(case['case_id'], case['image_key'], raw_baseline_extraction(extracted),
                                           case['ground_truth'], case['expect_inconsistency'])
        verified_reports.append(verified)
        raw_reports.append(raw)
        entry.update(
            document_type=extracted.get('document_type'),
            image_quality=extracted.get('image_quality', {}),
            verified=verified,
            raw=raw,
            field_readings=extracted.get('field_readings', {}),
            discrepancies=extracted.get('consistency', {}).get('discrepancies', []),
        )
        cases.append(entry)
    return {
        'mode': mode,
        'cases': cases,
        'verified_summary': _summarize(verified_reports),
        'raw_summary': _summarize(raw_reports),
        'taxonomy_order': list(TAXONOMY_7),
        'taxonomy_labels': TAXONOMY_LABELS_VI,
        'note': ('Kiểm thử trên 4 ảnh tổng hợp có đáp án; bản đọc thô mô phỏng các lỗi đã gặp trên ảnh thật của cửa hàng. '
                 'Đây là phép đo tầng kiểm chứng, không phải độ chính xác đã hiệu chuẩn của mô hình.'),
    }


# ---------------------------------------------------------------------------
# Labelled real-photo dataset: live run (records raw readings) and offline replay
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_DATASET_PATH = REPO_ROOT / 'data' / 'ocr_eval' / 'real_photos.json'


def dataset_image_path(image: str | Path) -> Path:
    path = Path(image)
    return path if path.is_absolute() else REPO_ROOT / path


class _RecordingReader:
    """Wraps the configured vision model and keeps its raw answer, latency and token usage."""

    def __init__(self, reader):
        self.reader = reader
        self.raw_content: str | None = None
        self.latency_s: float | None = None
        self.usage: dict[str, Any] = {}
        self.model_name: str = ''

    def invoke(self, messages):
        import time
        started = time.monotonic()
        answer = self.reader.invoke(messages)
        self.latency_s = round(time.monotonic() - started, 2)
        content = answer.content
        if isinstance(content, list):
            content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
        self.raw_content = str(content)
        self.usage = dict(getattr(answer, 'usage_metadata', None) or {})
        self.model_name = str((getattr(answer, 'response_metadata', None) or {}).get('model_name', ''))
        return answer


def load_ocr_dataset(path: str | Path = REAL_DATASET_PATH) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    unknown = {f for case in data['cases'] for f in case['fields']} - set(MONEY_FIELDS)
    if unknown:
        raise ValueError(f'Unknown fields in dataset: {sorted(unknown)}')
    return data


def run_dataset_benchmark(
    path: str | Path = REAL_DATASET_PATH,
    mode: str = 'replay',
    settings=None,
    readings_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Score a labelled photo dataset with the same 7-group taxonomy as ``run_ocr_benchmark``.

    ``live``: send each photo to the configured vision model, save its raw JSON reading
    (plus model, latency, tokens) under ``readings_dir``, then verify and score it.
    ``replay``: re-run today's verification pipeline on the saved readings, offline and
    deterministic, so results can be shown without network access.
    """
    from datetime import datetime

    from src.agent.config import AgentSettings
    from src.engine.vision_ocr import build_ocr_reader, extract_image

    if mode not in {'live', 'replay'}:
        raise ValueError("mode must be 'live' or 'replay'")
    dataset = load_ocr_dataset(path)
    folder = Path(readings_dir) if readings_dir else Path(path).parent / 'readings'
    cfg = settings or AgentSettings.from_env()
    verified_reports, raw_reports, cases, runtime = [], [], [], []
    for case in dataset['cases']:
        image_path = dataset_image_path(case['image'])
        entry = {'case_id': case['case_id'], 'image_key': case['case_id'], 'image_path': str(image_path),
                 'title': case['title'], 'shift_hint': case.get('shift_hint'), 'note': case.get('note', '')}
        if not image_path.is_file():
            cases.append({**entry, 'status': 'MISSING_IMAGE', 'skipped_reason': f'Không thấy ảnh {image_path}'})
            continue
        reading_file = folder / f"{case['case_id']}.json"
        recorder = None
        if mode == 'live':
            if not cfg.llm_enabled or not cfg.allow_external_transfer:
                cases.append({**entry, 'status': 'OCR_DISABLED',
                              'skipped_reason': 'Chưa bật LLM_ENABLED và ALLOW_EXTERNAL_DATA_TRANSFER cho mô hình Vision.'})
                continue
            recorder = _RecordingReader(build_ocr_reader(cfg))
            model = recorder
        else:
            if not reading_file.is_file():
                cases.append({**entry, 'status': 'NO_SAVED_READING',
                              'skipped_reason': 'Chưa có bản đọc đã lưu; chạy chế độ live một lần để ghi lại.'})
                continue
            saved = json.loads(reading_file.read_text(encoding='utf-8'))
            model = _ScriptedReader(json.loads(saved['raw_content']))
            entry['reading_meta'] = {k: saved.get(k) for k in ('model', 'recorded_at', 'latency_s', 'usage')}
        extracted = extract_image(image_bytes=image_path.read_bytes(), model=model,
                                  shift_hint=case.get('shift_hint'), target_date=case.get('target_date'), settings=cfg)
        if recorder is not None and recorder.raw_content is not None:
            folder.mkdir(parents=True, exist_ok=True)
            meta = {'case_id': case['case_id'], 'model': recorder.model_name, 'recorded_at': datetime.now().isoformat(timespec='seconds'),
                    'latency_s': recorder.latency_s, 'usage': recorder.usage, 'raw_content': recorder.raw_content}
            reading_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
            entry['reading_meta'] = {k: meta[k] for k in ('model', 'recorded_at', 'latency_s', 'usage')}
            runtime.append(meta)
        entry['status'] = extracted.get('status')
        if extracted.get('status') != 'NEEDS_REVIEW':
            entry['skipped_reason'] = extracted.get('message') or extracted.get('error_code') or extracted.get('status')
            cases.append(entry)
            continue
        gt = case['fields']
        verified = evaluate_ocr_extraction_case(case['case_id'], case['image_type'], extracted, gt, case.get('expect_inconsistency', False))
        raw = evaluate_ocr_extraction_case(case['case_id'], case['image_type'], raw_baseline_extraction(extracted), gt,
                                           case.get('expect_inconsistency', False))
        verified_reports.append(verified)
        raw_reports.append(raw)
        entry.update(document_type=extracted.get('document_type'), image_quality=extracted.get('image_quality', {}),
                     verified=verified, raw=raw, field_readings=extracted.get('field_readings', {}),
                     discrepancies=extracted.get('consistency', {}).get('discrepancies', []))
        cases.append(entry)
    latencies = [m['latency_s'] for m in runtime if m.get('latency_s') is not None]
    return {
        'mode': f'real_{mode}',
        'dataset': dataset.get('dataset'),
        'label_source': dataset.get('label_source'),
        'cases': cases,
        'verified_summary': _summarize(verified_reports),
        'raw_summary': _summarize(raw_reports),
        'taxonomy_order': list(TAXONOMY_7),
        'taxonomy_labels': TAXONOMY_LABELS_VI,
        'runtime': {'calls': len(runtime), 'avg_latency_s': round(sum(latencies) / len(latencies), 2) if latencies else None,
                    'input_tokens': sum(int(m['usage'].get('input_tokens', 0)) for m in runtime),
                    'output_tokens': sum(int(m['usage'].get('output_tokens', 0)) for m in runtime)},
        'note': (f"{len(verified_reports)}/{len(dataset['cases'])} ảnh thật được chấm; đáp án lấy từ báo cáo đã duyệt. "
                 'Mẫu rất nhỏ: dùng để phân tích lỗi, chưa đủ để công bố độ chính xác tổng quát.'),
    }
