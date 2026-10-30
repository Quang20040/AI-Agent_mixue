import io
import json

from langchain_core.messages import AIMessage
from PIL import Image

from src.agent.config import AgentSettings
from src.engine.ocr_evaluation import (
    evaluate_historical_ocr_review,
    evaluate_ocr_extraction_case,
    make_synthetic_test_images,
)
from src.engine.shift_service import (
    get_all_shift_reports,
    record_ocr_user_edits,
)
from src.engine.vision_ocr import MONEY_FIELDS, extract_image, extraction_schema


def image_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (40, 40), 'white').save(buffer, format='PNG')
    return buffer.getvalue()


def reading():
    return {
        'fields': {name: {'value': None, 'status': 'not_present', 'evidence': ''} for name in MONEY_FIELDS},
        'document_date': None,
        'raw_text': 'Tiền mặt: 653000 đ',
        'warnings': [],
    }


class Model:
    def __init__(self, data):
        self.data = data
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return AIMessage(content=json.dumps(self.data))


def test_reads_image_content_and_never_fills_missing_money():
    data = reading()
    data['fields']['cash_vnd'] = {'value': 653000, 'status': 'read', 'evidence': 'Tiền mặt: 653000 đ'}
    model = Model(data)
    result = extract_image(image_bytes=image_bytes(), model=model, shift_hint='CA_SANG')
    assert result['status'] == 'NEEDS_REVIEW'
    assert result['cash_vnd'] == 653000
    assert result['bank_transfer_vnd'] is None
    assert result['requires_human_confirmation'] is True
    assert 'confidence_score' not in result
    assert model.messages[-1].content[-1]['image_url']['url'].startswith('data:image/png;base64,')


def test_disabled_or_unapproved_api_does_not_read_image():
    assert extract_image(image_bytes=image_bytes(), settings=AgentSettings())['status'] == 'OCR_DISABLED'
    settings = AgentSettings(llm_enabled=True)
    assert extract_image(image_bytes=image_bytes(), settings=settings)['status'] == 'EXTERNAL_TRANSFER_DISABLED'


def test_invalid_image_never_returns_sample_data():
    for data in (b'', b'not an image'):
        result = extract_image(image_bytes=data)
        assert result['status'] == 'INVALID_IMAGE'
        assert 'cash_vnd' not in result


def test_invalid_model_reading_is_rejected():
    data = reading()
    data['fields']['cash_vnd'] = {'value': -100, 'status': 'read', 'evidence': '-100'}
    assert extract_image(image_bytes=image_bytes(), model=Model(data))['status'] == 'OCR_ERROR'
    data['fields']['cash_vnd'] = {'value': 100, 'status': 'not_present', 'evidence': ''}
    assert extract_image(image_bytes=image_bytes(), model=Model(data))['status'] == 'OCR_ERROR'


def test_date_mismatch_requires_review():
    data = reading()
    data['document_date'] = '2026-10-14'
    result = extract_image(image_bytes=image_bytes(), model=Model(data), target_date='2026-10-16')
    assert result['status'] == 'NEEDS_REVIEW'
    assert 'khác ngày' in result['warnings'][-1]


def test_provider_error_does_not_expose_secret():
    class Broken:
        def invoke(self, messages):
            raise RuntimeError('Authorization private-key')
    result = extract_image(image_bytes=image_bytes(), model=Broken())
    assert result['status'] == 'OCR_ERROR'
    assert 'private-key' not in json.dumps(result)


def test_structured_output_schema_requires_every_money_field():
    schema = extraction_schema()
    fields = schema['properties']['fields']
    assert set(fields['required']) == set(MONEY_FIELDS)
    assert fields['additionalProperties'] is False
    assert set(schema['required']) == set(schema['properties'])


def test_guessed_or_uncertain_values_do_not_autofill_money():
    data = reading()
    data['fields']['bank_transfer_vnd'] = {
        'value': 6492,
        'status': 'read',
        'evidence': 'Handwritten values summed, interpreted as VND.',
    }
    data['fields']['cash_vnd'] = {'value': 9057300, 'status': 'uncertain', 'evidence': 'Cash unclear.'}
    result = extract_image(image_bytes=image_bytes(), model=Model(data))
    assert result['status'] == 'NEEDS_REVIEW'
    assert result['bank_transfer_vnd'] is None
    assert result['cash_vnd'] is None
    assert result['field_readings']['bank_transfer_vnd']['value'] == 6492
    assert result['field_readings']['bank_transfer_vnd']['status'] == 'uncertain'


def test_separates_pos_and_handwritten_regions_and_sources():
    """Tách rõ vùng hóa đơn POS và sổ viết tay; giữ nguồn chứng từ cho từng trường."""
    imgs = make_synthetic_test_images()
    data = reading()
    data['document_type'] = 'composite'
    data['pos_region_text'] = 'Tổng doanh thu: 10,119,000 | Số tiền thu được: 9,877,137'
    data['handwritten_region_text'] = 'Ca tối: Tiền mặt 3260 (dư 35k), Cố định két 1.000.000đ'
    data['fields']['pos_revenue_vnd'] = {
        'value': 10119000,
        'status': 'read',
        'source': 'pos_receipt',
        'raw_text': '10,119,000',
        'evidence': 'POS receipt: Tổng doanh thu: 10,119,000',
    }
    data['fields']['pos_collected_vnd'] = {
        'value': 9877137,
        'status': 'read',
        'source': 'pos_receipt',
        'raw_text': '9,877,137',
        'evidence': 'POS receipt: Số tiền thu được: 9,877,137',
    }
    data['fields']['petty_cash_kept_vnd'] = {
        'value': 1000000,
        'status': 'read',
        'source': 'handwritten_ledger',
        'raw_text': '1.000.000đ',
        'evidence': 'Sổ viết tay: Cố định két 1.000.000đ',
    }
    # If POS cash is mistakenly put into shift cash_vnd on a composite image for CA_TOI, it must be blocked from auto-filling!
    data['fields']['cash_vnd'] = {
        'value': 9657300,
        'status': 'read',
        'source': 'pos_receipt',
        'raw_text': '9,657,300',
        'evidence': 'POS receipt: 1.Cash: 9,657,300',
    }
    result = extract_image(image_bytes=imgs['composite_multi_doc'], model=Model(data), shift_hint='CA_TOI')
    assert result['document_type'] == 'composite'
    assert result['regions']['pos_receipt']['present'] is True
    assert result['regions']['handwritten_ledger']['present'] is True
    assert result['pos_revenue_vnd'] == 10119000
    assert result['pos_collected_vnd'] == 9877137
    assert result['petty_cash_kept_vnd'] == 1000000
    assert result['field_readings']['pos_revenue_vnd']['source'] == 'pos_receipt'
    assert result['field_readings']['petty_cash_kept_vnd']['source'] == 'handwritten_ledger'
    # POS cash must not auto-populate handwritten shift cash_vnd in composite mode
    assert result['cash_vnd'] is None
    assert result['field_readings']['cash_vnd']['status'] == 'uncertain'


def test_distinguishes_literal_reading_from_calculation_and_ambiguous_unit():
    """Phân biệt đọc chữ/số với tính toán. Không tự cộng hoặc nhân 1.000 khi đơn vị chưa rõ."""
    imgs = make_synthetic_test_images()
    data = reading()
    data['document_type'] = 'handwritten_ledger'
    # Bare number '653' without unit -> must not auto-multiply by 1000 into confirmed field
    data['fields']['cash_vnd'] = {
        'value': 653000,
        'status': 'read',
        'source': 'handwritten_ledger',
        'raw_text': '653',
        'evidence': 'Sổ ca sáng: Tiền mặt: 653',
    }
    # Multi-term formula '962 + 629' -> must not auto-sum into confirmed field
    data['fields']['bank_transfer_vnd'] = {
        'value': 1591000,
        'status': 'read',
        'source': 'handwritten_ledger',
        'raw_text': '962 + 629',
        'evidence': 'Sổ ca sáng: Chuyển khoản: 962 + 629',
    }
    # Explicit unit '1.000.000đ' -> allowed as confirmed read
    data['fields']['petty_cash_kept_vnd'] = {
        'value': 1000000,
        'status': 'read',
        'source': 'handwritten_ledger',
        'raw_text': '1.000.000đ',
        'evidence': 'Sổ ca sáng: Cố định két: 1.000.000đ',
    }
    result = extract_image(image_bytes=imgs['handwritten_ledger'], model=Model(data), shift_hint='CA_SANG')
    assert result['cash_vnd'] is None
    assert result['field_readings']['cash_vnd']['raw_text'] == '653'
    assert result['field_readings']['cash_vnd']['unit_explicit'] is False
    assert result['field_readings']['cash_vnd']['normalized_value'] is None
    assert '1.000' in result['field_readings']['cash_vnd']['review_reason']

    assert result['bank_transfer_vnd'] is None
    assert result['field_readings']['bank_transfer_vnd']['raw_text'] == '962 + 629'
    assert result['field_readings']['bank_transfer_vnd']['is_calculated'] is True
    assert result['bank_transfer_formula'] == '962 + 629'

    assert result['petty_cash_kept_vnd'] == 1000000
    assert result['field_readings']['petty_cash_kept_vnd']['normalized_value'] == 1000000


def test_consistency_check_surfaces_discrepancy_without_auto_fixing_numbers():
    """Kiểm tra tính nhất quán giữa các khoản và tổng tiền; chênh lệch phải được hiển thị, không tự sửa số để khớp."""
    imgs = make_synthetic_test_images()
    data = reading()
    data['document_type'] = 'pos_receipt'
    # Simulate the exact POS misread: Cash 9,057,300 + Grab 104,000 + Shopee 5,837 = 9,167,137 != 9,877,137 (diff -710,000)
    data['fields']['pos_revenue_vnd'] = {
        'value': 10119000, 'status': 'read', 'source': 'pos_receipt',
        'raw_text': '10,119,000', 'evidence': 'POS: Tổng doanh thu: 10,119,000',
    }
    data['fields']['pos_collected_vnd'] = {
        'value': 9877137, 'status': 'read', 'source': 'pos_receipt',
        'raw_text': '9,877,137', 'evidence': 'POS: Số tiền thu được: 9,877,137',
    }
    data['fields']['cash_vnd'] = {
        'value': 9057300, 'status': 'read', 'source': 'pos_receipt',
        'raw_text': '9,057,300', 'evidence': 'POS: 1.Cash: 9,057,300',
    }
    data['fields']['grab_food_vnd'] = {
        'value': 104000, 'status': 'read', 'source': 'pos_receipt',
        'raw_text': '104,000', 'evidence': 'POS: 2.GrabFood: 104,000',
    }
    data['fields']['shopee_food_vnd'] = {
        'value': 5837, 'status': 'read', 'source': 'pos_receipt',
        'raw_text': '5,837', 'evidence': 'POS: 3.Shopeefood: 5,837',
    }
    result = extract_image(image_bytes=imgs['printed_pos'], model=Model(data))
    assert result['consistency']['is_consistent'] is False
    pos_check = result['consistency']['pos_check']
    assert pos_check['pos_component_sum_vnd'] == 9167137
    assert pos_check['pos_collected_vnd'] == 9877137
    assert pos_check['difference_vnd'] == -710000
    # Raw read numbers are preserved in field_readings (never silently altered to match!)
    assert result['field_readings']['cash_vnd']['value'] == 9057300
    assert result['field_readings']['shopee_food_vnd']['value'] == 5837
    # Conflicting fields are left blank at top-level so user must confirm
    assert result['cash_vnd'] is None
    assert result['shopee_food_vnd'] is None


def test_blurry_image_flags_all_readings_for_manual_confirmation():
    """Kiểm thử trên ảnh mờ: phát hiện ảnh mờ và yêu cầu xác nhận thủ công."""
    imgs = make_synthetic_test_images()
    data = reading()
    data['document_type'] = 'pos_receipt'
    data['fields']['pos_revenue_vnd'] = {
        'value': 10119000, 'status': 'read', 'source': 'pos_receipt',
        'raw_text': '10,119,000', 'evidence': 'Tổng doanh thu: 10,119,000',
    }
    result = extract_image(image_bytes=imgs['blurry_image'], model=Model(data))
    assert result['image_quality']['is_blurry'] is True
    assert result['pos_revenue_vnd'] is None
    assert result['field_readings']['pos_revenue_vnd']['status'] == 'uncertain'
    assert any('ảnh mờ' in w.lower() for w in result['warnings'])


def test_user_edits_are_recorded_and_ocr_never_writes_revenue_before_confirmation(tmp_path):
    """Lưu lại chỉnh sửa của người dùng để phục vụ đánh giá; không ghi doanh thu trước khi xác nhận."""
    before_reports = get_all_shift_reports('2026-10-16')
    imgs = make_synthetic_test_images()
    data = reading()
    data['document_type'] = 'handwritten_ledger'
    data['fields']['petty_cash_kept_vnd'] = {
        'value': 1000000, 'status': 'read', 'source': 'handwritten_ledger',
        'raw_text': '1.000.000đ', 'evidence': 'Cố định két: 1.000.000đ',
    }
    data['fields']['cash_vnd'] = {
        'value': 653, 'status': 'read', 'source': 'handwritten_ledger',
        'raw_text': '653', 'evidence': 'Tiền mặt: 653',
    }
    extracted = extract_image(image_bytes=imgs['handwritten_ledger'], model=Model(data), shift_hint='CA_SANG', target_date='2026-10-16')
    # Running OCR must never write a shift report
    assert get_all_shift_reports('2026-10-16') == before_reports

    confirmed_values = {
        'cash_vnd': 653000,
        'cash_diff_vnd': 0,
        'bank_transfer_vnd': 1591000,
        'shopee_food_vnd': 16000,
        'grab_food_vnd': 30000,
        'be_food_vnd': 0,
        'petty_cash_kept_vnd': 1000000,
        'expenses_vnd': 0,
        'total_collected_vnd': 2328000,
    }
    log_file = tmp_path / 'ocr_edits.jsonl'
    record = record_ocr_user_edits(
        report_id='SHIFT_20261016_CA_SANG',
        business_date='2026-10-16',
        shift_code='CA_SANG',
        confirmed_by='quanly',
        extracted=extracted,
        confirmed_values=confirmed_values,
        review_seconds=14.2,
        log_path=log_file,
    )
    assert log_file.is_file()
    assert record['field_edits']['petty_cash_kept_vnd']['action'] == 'confirmed_as_is'
    assert record['field_edits']['cash_vnd']['action'] == 'edited_uncertain'
    assert record['field_edits']['cash_vnd']['raw_text'] == '653'
    assert record['field_edits']['cash_vnd']['user_final_value'] == 653000
    assert 'cash_vnd' in record['corrected_fields']


def test_field_level_ocr_evaluation_across_four_image_types():
    """Báo cáo đúng/sai theo từng trường trên 4 loại ảnh: chữ in, viết tay, ảnh mờ, nhiều chứng từ."""
    imgs = make_synthetic_test_images()

    # 1. Accurate printed POS extraction
    pos_data = reading()
    pos_data['document_type'] = 'pos_receipt'
    for k, v, raw in [
        ('pos_revenue_vnd', 10119000, '10,119,000'),
        ('pos_collected_vnd', 9877137, '9,877,137'),
        ('cash_vnd', 9657300, '9,657,300'),
        ('grab_food_vnd', 104000, '104,000'),
        ('shopee_food_vnd', 115837, '115,837'),
    ]:
        pos_data['fields'][k] = {
            'value': v, 'status': 'read', 'source': 'pos_receipt',
            'raw_text': raw, 'evidence': f'POS receipt: {k}={raw} VND',
        }
    pos_extracted = extract_image(image_bytes=imgs['printed_pos'], model=Model(pos_data))
    pos_eval = evaluate_ocr_extraction_case(
        'PRINTED_POS_01',
        'printed_pos',
        pos_extracted,
        {
            'pos_revenue_vnd': {'expected_value': 10119000, 'expected_source': 'pos_receipt'},
            'pos_collected_vnd': {'expected_value': 9877137, 'expected_source': 'pos_receipt'},
            'cash_vnd': {'expected_value': 9657300, 'expected_source': 'pos_receipt'},
            'grab_food_vnd': {'expected_value': 104000, 'expected_source': 'pos_receipt'},
            'shopee_food_vnd': {'expected_value': 115837, 'expected_source': 'pos_receipt'},
        },
    )
    assert pos_eval['all_passed'] is True
    assert pos_eval['error_taxonomy_counts']['correct_read'] == 5

    # 2. Historical store photo audit classifies exact digit and unit errors
    hist_eval = evaluate_historical_ocr_review()
    if hist_eval.get('status') != 'NO_FILE':
        assert hist_eval['field_results']['pos_revenue_vnd']['outcome'] == 'correct_read'
        assert hist_eval['field_results']['pos_collected_vnd']['outcome'] == 'correct_read'
        assert hist_eval['field_results']['cash_vnd']['outcome'] == 'digit_error'
        assert hist_eval['field_results']['shopee_food_vnd']['outcome'] == 'digit_error'
        assert hist_eval['field_results']['bank_transfer_vnd']['outcome'] == 'unit_error'


def test_extract_multiple_images_combined():
    """Support uploading multiple invoice/slip images together into a single extraction."""
    b1 = image_bytes()
    b2 = image_bytes()

    data = reading()
    data['document_type'] = 'composite'
    data['fields']['pos_revenue_vnd'] = {'value': 10119000, 'status': 'read', 'evidence': 'POS 10119000'}
    data['fields']['cash_vnd'] = {'value': 9657300, 'status': 'read', 'evidence': 'Tiền mặt 9657300'}
    model = Model(data)

    result = extract_image(images=[b1, b2], model=model, shift_hint='CA_TOI')
    assert result['status'] == 'NEEDS_REVIEW'
    assert result['image_count'] == 2
    assert len(result['image_names']) == 2
    assert result['pos_revenue_vnd'] == 10119000
    assert result['cash_vnd'] == 9657300
    # Each model request now receives one image, preventing cross-page row mixing.
    human_msg = model.messages[-1]
    image_parts = [p for p in human_msg.content if isinstance(p, dict) and p.get('type') == 'image_url']
    assert len(image_parts) == 1


def independent_cash(value, source='handwritten_ledger'):
    data = reading()
    data['document_type'] = source
    data['fields']['cash_vnd'] = {'value': value, 'status': 'read', 'source': source,
                                 'raw_text': f'{value} VND', 'evidence': f'Tiền mặt {value} VND'}
    return extract_image(image_bytes=image_bytes(), model=Model(data))


def merge(results):
    from src.engine.vision_ocr import merge_image_extractions
    return merge_image_extractions(results, names=[f'image_{i}' for i in range(len(results))],
                                   shas=[str(i) for i in range(len(results))], shift_hint='CA_TOI', target_date='2026-10-20')


def test_duplicate_photos_are_not_added_together():
    result = merge([independent_cash(100000), independent_cash(100000)])
    assert result['cash_vnd'] == 100000
    assert len(result['field_candidates']['cash_vnd']) == 2


def test_conflicting_photos_require_confirmation_and_preserve_each_source():
    result = merge([independent_cash(100000), independent_cash(200000)])
    assert result['cash_vnd'] is None
    assert result['field_readings']['cash_vnd']['status'] == 'uncertain'
    assert {item['value'] for item in result['field_candidates']['cash_vnd']} == {100000, 200000}


def test_pos_cash_does_not_replace_cash_written_in_ledger():
    result = merge([independent_cash(900000, 'pos_receipt'), independent_cash(100000)])
    assert result['cash_vnd'] == 100000
    assert result['field_readings']['cash_vnd']['source'] == 'handwritten_ledger'


def test_one_failed_photo_does_not_erase_successful_readings():
    result = merge([independent_cash(100000), {'status': 'OCR_ERROR', 'error_code': 'TIMEOUT'}])
    assert result['status'] == 'NEEDS_REVIEW'
    assert result['cash_vnd'] == 100000
    assert any('Ảnh 2' in warning for warning in result['warnings'])


def test_truncated_model_response_has_specific_error():
    class Truncated:
        def invoke(self, messages):
            return AIMessage(content='{"fields":', response_metadata={'finish_reason': 'length'})
    result = extract_image(image_bytes=image_bytes(), model=Truncated())
    assert result['error_code'] == 'OUTPUT_TRUNCATED'


def test_rate_limit_has_specific_error_without_provider_secret():
    class Limited:
        def invoke(self, messages):
            error = RuntimeError('private-provider-secret')
            error.status_code = 429
            raise error
    result = extract_image(image_bytes=image_bytes(), model=Limited())
    assert result['error_code'] == 'RATE_LIMITED'
    assert 'private-provider-secret' not in json.dumps(result)


def test_same_vietnamese_and_iso_dates_do_not_create_false_conflict():
    first, second = independent_cash(100000), independent_cash(100000)
    first['document_date'] = '2026-10-20'
    data = reading()
    data['document_date'] = '20/10/26'
    second = extract_image(image_bytes=image_bytes(), model=Model(data))
    assert second['document_date'] == '2026-10-20'
    result = merge([first, second])
    assert result['document_date'] == '2026-10-20'
    assert result['cash_vnd'] == 100000


def test_other_shift_reading_is_kept_as_text_but_never_fills_selected_shift():
    data = reading()
    data['requested_shift_present'] = 'no'
    data['fields']['cash_vnd'] = {'value': 100000, 'status': 'read', 'raw_text': '100000 VND', 'evidence': 'Ca chiều 100000 VND'}
    result = extract_image(image_bytes=image_bytes(), model=Model(data), shift_hint='CA_TOI')
    assert result['cash_vnd'] is None
    assert result['field_readings']['cash_vnd']['raw_text'] == '100000 VND'

