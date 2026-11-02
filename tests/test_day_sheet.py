"""Day-sheet OCR: one reading per photo covers every shift; rules (not the model) turn text into money."""
import base64
import hashlib
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from src.agent.config import AgentSettings
from src.engine import vision_ocr
from src.engine.day_sheet import parse_cell
from src.engine.shift_service import get_all_shift_reports
from src.engine.vision_ocr import extract_image

DATA = Path(__file__).resolve().parents[1] / 'data'
PHOTOS = [DATA / 'shift_photos' / n for n in
          ('20261014_ca_sang_chieu.jpg', '20261014_ca_toi_tong_ket.jpg', '20261014_pos_slip.jpg')]
FIELDS = ['cash_vnd', 'cash_diff_vnd', 'bank_transfer_vnd', 'shopee_food_vnd', 'grab_food_vnd', 'be_food_vnd',
          'petty_cash_kept_vnd', 'expenses_vnd', 'total_collected_vnd', 'pos_revenue_vnd', 'pos_collected_vnd']


def transcripts_by_sha():
    data = json.loads((DATA / 'ocr_eval' / 'day_sheet_transcripts.json').read_text(encoding='utf-8'))
    return {hashlib.sha256((DATA / 'shift_photos' / name).read_bytes()).hexdigest(): sheet
            for name, sheet in data.items() if not name.startswith('_')}


class DayReader:
    """Stands in for the vision model: returns the transcription recorded for the photo it is shown."""

    def __init__(self, fixed=None):
        self.sheets, self.calls, self.fixed = transcripts_by_sha(), 0, fixed

    def invoke(self, messages):
        self.calls += 1
        url = self.last_url = messages[1].content[1]['image_url']['url']
        sha = hashlib.sha256(base64.b64decode(url.split(',', 1)[1])).hexdigest()
        sheet = self.sheets[sha] if self.fixed is None else self.sheets[self.fixed]
        return AIMessage(content=json.dumps(sheet, ensure_ascii=False))


def filled(result, field):
    value = result.get(field)
    return value if value is not None else (result['suggestions'].get(field) or {}).get('value')


@pytest.mark.parametrize('text,handwritten,expected', [
    ('653', True, (653000, False, None)),
    ('962 + 629', True, (1591000, True, None)),
    ('1630+1221+1010', True, (3861000, True, None)),
    ('2014 (dư20k)', True, (2014000, False, 20000)),
    ('3260 (dư 35k)', True, (3260000, False, 35000)),
    ('1.000.000đ', True, (1000000, False, None)),
    ('9,657,300', False, (9657300, False, None)),
    ('16k', True, (16000, False, None)),
    ('', True, (None, False, None)),
])
def test_parse_cell(text, handwritten, expected):
    out = parse_cell(text, handwritten=handwritten)
    assert (out['value'], out['is_expression'], out['diff']) == expected


def test_expenses_only_count_amounts_with_a_unit():
    out = parse_cell('41k tiền ship sạc đt hotline; 15k ship đơn', handwritten=True, expenses=True)
    assert out['value'] == 56000 and out['is_expression']


def test_full_day_photos_fill_every_shift_like_the_approved_reports():
    truth = {r['shift_code']: r for r in get_all_shift_reports('2026-10-14')}
    for shift in ('CA_SANG', 'CA_CHIEU', 'CA_TOI'):
        result = extract_image(image_paths=PHOTOS, shift_hint=shift, target_date='2026-10-14', model=DayReader())
        assert result['status'] == 'NEEDS_REVIEW' and result['day_sheet']['shift_present']
        assert result['day_sheet']['detected_shifts'] == ['CA_SANG', 'CA_CHIEU', 'CA_TOI']
        mismatches = {f: (filled(result, f), truth[shift].get(f)) for f in FIELDS
                      if filled(result, f) != truth[shift].get(f) and not (filled(result, f) is None and not truth[shift].get(f))}
        assert not mismatches, (shift, mismatches)
        # Shorthand stays a flagged suggestion: the verified value is still empty.
        assert result['cash_vnd'] is None and result['field_readings']['cash_vnd']['status'] == 'uncertain'


def test_one_photo_with_two_shifts_and_a_missing_shift_is_reported():
    morning = extract_image(image_path=PHOTOS[0], shift_hint='CA_SANG', target_date='2026-10-14', model=DayReader())
    afternoon = extract_image(image_path=PHOTOS[0], shift_hint='CA_CHIEU', target_date='2026-10-14', model=DayReader())
    night = extract_image(image_path=PHOTOS[0], shift_hint='CA_TOI', target_date='2026-10-14', model=DayReader())
    assert filled(morning, 'cash_vnd') == 653000 and filled(afternoon, 'cash_vnd') == 2014000
    assert morning['signed_by'] == 'Hà' and afternoon['signed_by'] == 'Nhi'
    assert not night['day_sheet']['shift_present']
    assert all(filled(night, f) in (None,) for f in ('cash_vnd', 'total_collected_vnd'))
    assert any('không có mục' in w for w in night['warnings'])


def test_live_reading_is_cached_so_switching_shift_costs_no_model_call(monkeypatch):
    # Live calls see a re-encoded image (upright, upscaled), so answer for the morning/afternoon page.
    reader = DayReader(fixed=hashlib.sha256(PHOTOS[0].read_bytes()).hexdigest())
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', lambda cfg, mode='json_schema_strict', model_id=None: reader)
    monkeypatch.setattr(vision_ocr, '_DAY_SHEETS', {})
    cfg = AgentSettings(llm_enabled=True, provider='gemini', model='gemini-3.5-flash', api_key='x', allow_external_transfer=True)
    first = extract_image(image_path=PHOTOS[0], shift_hint='CA_SANG', target_date='2026-10-14', settings=cfg)
    second = extract_image(image_path=PHOTOS[0], shift_hint='CA_CHIEU', target_date='2026-10-14', settings=cfg)
    assert reader.calls == 1
    sent = base64.b64decode(reader.last_url.split(',', 1)[1])
    from PIL import Image
    import io
    assert max(Image.open(io.BytesIO(sent)).size) >= 1600  # small phone photo upscaled for the model
    assert filled(first, 'total_collected_vnd') == 2328000 and filled(second, 'total_collected_vnd') == 6090000


def test_without_a_shift_the_first_shift_on_the_page_is_used_and_said():
    result = extract_image(image_path=PHOTOS[0], target_date='2026-10-14', model=DayReader())
    assert result['shift_code'] == 'CA_SANG'
    assert any('Ca chiều' in w for w in result['warnings'])
