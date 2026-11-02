"""Real day sheets of 01/11/2026 (3 photos): what the reader must fill and what it must flag."""
import base64
import hashlib
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from src.engine.day_sheet import parse_cell
from src.engine.vision_ocr import extract_image

DATA = Path(__file__).resolve().parents[1] / 'data'
SPEC = json.loads((DATA / 'ocr_eval/day_sheet_20261101.json').read_text(encoding='utf-8'))
PHOTOS = [DATA / 'shift_photos' / name for name in SPEC['clean']]
FIELDS = ['cash_vnd', 'cash_diff_vnd', 'bank_transfer_vnd', 'shopee_food_vnd', 'grab_food_vnd', 'be_food_vnd',
          'petty_cash_kept_vnd', 'expenses_vnd', 'total_collected_vnd', 'pos_revenue_vnd', 'pos_collected_vnd']


def _reader(variant):
    sheets = {hashlib.sha256(path.read_bytes()).hexdigest(): {**SPEC['clean'][path.name], **SPEC.get(variant, {}).get(path.name, {})}
              for path in PHOTOS}

    class Reader:
        def invoke(self, messages):
            data = base64.b64decode(messages[1].content[1]['image_url']['url'].split(',', 1)[1])
            return AIMessage(content=json.dumps(sheets[hashlib.sha256(data).hexdigest()], ensure_ascii=False))
    return Reader()


def _filled(result, field):
    if result.get(field) is not None:
        return result[field]
    return (result['suggestions'].get(field) or {}).get('value')


@pytest.mark.parametrize('variant', ['clean', 'hard'])
@pytest.mark.parametrize('shift', ['CA_SANG', 'CA_CHIEU', 'CA_TOI'])
def test_all_three_photos_fill_every_shift(variant, shift):
    result = extract_image(image_paths=PHOTOS, shift_hint=shift, target_date=SPEC['business_date'], model=_reader(variant))
    wrong = {f: _filled(result, f) for f in FIELDS if _filled(result, f) != SPEC['truth'][shift][f]}
    assert wrong == {}


def test_surplus_inside_cash_is_not_a_mismatch():
    result = extract_image(image_paths=PHOTOS, shift_hint='CA_SANG', target_date=SPEC['business_date'], model=_reader('clean'))
    assert not any('Chênh lệch cộng ngang' in w for w in result['warnings'])


def test_misaligned_rows_are_flagged_not_trusted():
    result = extract_image(image_paths=PHOTOS, shift_hint='CA_CHIEU', target_date=SPEC['business_date'], model=_reader('hard'))
    assert any('lệch hàng' in w for w in result['warnings'])
    assert result['field_readings']['grab_food_vnd']['status'] != 'read'
    assert result['grab_food_vnd'] is None


def test_crossed_out_value_keeps_last_number_and_asks():
    result = extract_image(image_paths=PHOTOS, shift_hint='CA_SANG', target_date=SPEC['business_date'], model=_reader('hard'))
    assert result['field_readings']['cash_vnd']['status'] != 'read'
    assert 'gạch' in result['field_readings']['cash_vnd']['review_reason']


def test_comma_total_is_thousands():
    assert parse_cell('10,662', handwritten=True)['value'] == 10_662_000
    assert parse_cell('1.000.000đ', handwritten=True)['value'] == 1_000_000
    assert parse_cell('2093 1193 (dư 15k)', handwritten=True)['value'] == 1_193_000
