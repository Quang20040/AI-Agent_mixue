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

    return lambda cfg, mode='json_schema_strict', model_id=None: Reader(mode)


def test_falls_back_until_the_provider_accepts_the_format(monkeypatch):
    calls = []
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', _reader_factory({'json_object'}, calls))
    result = vision_ocr.extract_image(image_path=IMAGE, shift_hint='CA_TOI', target_date='2026-10-14', settings=SETTINGS)
    assert calls == ['json_schema_strict', 'json_schema_inline', 'json_object']
    assert result['status'] == 'NEEDS_REVIEW'
    assert len(result['output_fallbacks']) == 2


def test_reports_the_provider_reason_when_every_format_is_rejected(monkeypatch):
    calls = []
    monkeypatch.setenv('OCR_FALLBACK_MODELS', '')
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', _reader_factory(set(), calls))
    monkeypatch.setattr(vision_ocr.GeminiNativeReader, 'invoke',
                        lambda self, m: (_ for _ in ()).throw(vision_ocr.ProviderHTTPError(400, 'bad request')))
    result = vision_ocr.extract_image(image_path=IMAGE, shift_hint='CA_TOI', target_date='2026-10-14', settings=SETTINGS)
    assert result['status'] == 'OCR_ERROR' and result['error_code'] == 'PROVIDER_ERROR'
    assert len(calls) == 3 and len(result['attempts']) == 4
    assert 'HTTP 400' in result['provider_detail'] and 'gemini_native' in result['attempts'][-1]
    assert 'bad request' not in json.dumps(result)  # provider text stays in the server log only


class Overloaded(Exception):
    status_code = 503


class _Response:
    def __init__(self, status, payload):
        self.status_code, self._payload, self.text = status, payload, json.dumps(payload)

    def json(self):
        return self._payload


def test_server_errors_move_to_gemini_native_then_next_model(monkeypatch):
    """Compat layer overloaded → native API of the same model; that fails too → next model answers."""
    reading = json.dumps(benchmark_cases()[0]['reading'], ensure_ascii=False)
    compat_calls, native_calls = [], []

    class Reader:
        def __init__(self, mode, model_id):
            self.mode, self.model_id = mode, model_id

        def invoke(self, messages):
            compat_calls.append((self.model_id, self.mode))
            raise Overloaded('503 overloaded')

    def fake_post(url, json=None, timeout=None, headers=None):
        native_calls.append(url.rsplit('/', 1)[1])
        assert headers['x-goog-api-key'] == 'x' and 'key=' not in url
        assert any('inline_data' in part for part in json['contents'][0]['parts'])
        if 'gemini-3.5-flash:' in url:
            return _Response(404, {'error': {'message': 'model not found'}})
        return _Response(200, {'candidates': [{'content': {'parts': [{'text': reading}]}, 'finishReason': 'STOP'}]})

    import httpx
    monkeypatch.delenv('OCR_FALLBACK_MODELS', raising=False)
    monkeypatch.delenv('OCR_MODEL', raising=False)
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', lambda cfg, mode='json_schema_strict', model_id=None: Reader(mode, model_id))
    monkeypatch.setattr(httpx, 'post', fake_post)
    vision_ocr._DAY_SHEETS.clear()
    result = vision_ocr.extract_image(image_path=IMAGE, shift_hint='CA_TOI', target_date='2026-10-14', settings=SETTINGS)
    assert result['status'] == 'NEEDS_REVIEW'
    # one compat try per model (503 is not a format problem), then the native API
    assert compat_calls == [('gemini-3.5-flash', 'json_schema_strict'), ('gemini-3.8-flash', 'json_schema_strict')]
    assert native_calls == ['gemini-3.5-flash:generateContent', 'gemini-3.8-flash:generateContent']


def test_bad_key_stops_immediately(monkeypatch):
    class Unauthorized(Exception):
        status_code = 401
    calls = []

    class Reader:
        def invoke(self, messages):
            calls.append(1)
            raise Unauthorized('bad key')
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', lambda cfg, mode='json_schema_strict', model_id=None: Reader())
    vision_ocr._DAY_SHEETS.clear()
    result = vision_ocr.extract_image(image_path=IMAGE, shift_hint='CA_TOI', target_date='2026-10-14', settings=SETTINGS)
    assert result['error_code'] == 'AUTH_ERROR' and calls == [1]


def test_inline_schema_has_no_refs():
    assert '$ref' not in json.dumps(vision_ocr._inline_refs(vision_ocr.extraction_schema()))
