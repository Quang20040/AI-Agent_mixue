"""Providers that reject strict JSON schemas (HTTP 400) fall back to looser output modes."""
import json
from pathlib import Path

from langchain_core.messages import AIMessage

from src.agent.config import AgentSettings
from src.engine import vision_ocr
from src.engine.ocr_evaluation import benchmark_cases

IMAGE = Path(__file__).resolve().parents[1] / 'data' / 'shift_photos' / '20261014_pos_slip.jpg'
SETTINGS = AgentSettings(llm_enabled=True, provider='gemini', model='gemini-3.5-flash', api_key='x',
                         allow_external_transfer=True)


class BadRequest(Exception):
    status_code = 400


def _reader_factory(accepts, calls):
    reading = json.dumps(benchmark_cases()[0]['reading'], ensure_ascii=False)

    class Reader:
        def __init__(self, mode):
            self.mode = mode

        def invoke(self, messages):
            calls.append(self.mode)
            if self.mode not in accepts:
                raise BadRequest('Invalid JSON payload received. Unknown name "$ref"')
            return AIMessage(content=reading)

    return lambda cfg, mode='json_schema_strict': Reader(mode)


def test_falls_back_until_the_provider_accepts_the_format(monkeypatch):
    calls = []
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', _reader_factory({'json_object'}, calls))
    result = vision_ocr.extract_image(image_path=IMAGE, shift_hint='CA_TOI', target_date='2026-10-14', settings=SETTINGS)
    assert calls == ['json_schema_strict', 'json_schema_inline', 'json_object']
    assert result['status'] == 'NEEDS_REVIEW'
    assert len(result['output_fallbacks']) == 2


def test_reports_the_provider_reason_when_every_format_is_rejected(monkeypatch):
    calls = []
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', _reader_factory(set(), calls))
    result = vision_ocr.extract_image(image_path=IMAGE, shift_hint='CA_TOI', target_date='2026-10-14', settings=SETTINGS)
    assert result['status'] == 'OCR_ERROR' and result['error_code'] == 'PROVIDER_ERROR'
    assert len(calls) == 3 and 'HTTP 400' in result['provider_detail']
    assert '$ref' not in json.dumps(result)  # provider text stays in the server log only


def test_inline_schema_has_no_refs():
    assert '$ref' not in json.dumps(vision_ocr._inline_refs(vision_ocr.extraction_schema()))
