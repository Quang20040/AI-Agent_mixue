"""Reading a photo should take tens of seconds, not minutes: thinking is held low, the same photo is never
sent twice at once, photos are read side by side, and a just-uploaded photo starts reading in the background."""
import hashlib
import threading
import time

from src.agent.config import AgentSettings
from src.engine import vision_ocr
from src.engine.vision_ocr import extract_image, prefetch_reading
from test_day_sheet import PHOTOS, DayReader, filled


def gemini(**kw):
    return AgentSettings(llm_enabled=True, provider='gemini', model='gemini-3.8-flash', api_key='x',
                         allow_external_transfer=True, **kw)


def test_gemini_chat_and_photo_reads_think_low_by_default(monkeypatch):
    monkeypatch.delenv('LLM_REASONING_EFFORT', raising=False)
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.setenv('LLM_MODEL', 'gemini-3.8-flash')
    assert AgentSettings.from_env(env_file='/nonexistent').reasoning_effort == 'low'
    monkeypatch.setenv('LLM_REASONING_EFFORT', 'medium')
    assert AgentSettings.from_env(env_file='/nonexistent').reasoning_effort == 'medium'
    model = gemini(reasoning_effort='low').build_model()
    assert model.reasoning_effort == 'low'
    monkeypatch.delenv('OCR_REASONING_EFFORT', raising=False)
    reader = vision_ocr.build_ocr_reader(gemini(reasoning_effort='high'), 'json_object')
    assert reader.bound.reasoning_effort == 'low'  # photo reads keep their own (low) setting


def test_native_gemini_call_asks_for_low_thinking(monkeypatch):
    sent = {}

    class Resp:
        status_code = 200

        def json(self):
            return {'candidates': [{'content': {'parts': [{'text': '{}'}]}, 'finishReason': 'STOP'}]}

    import httpx
    monkeypatch.setattr(httpx, 'post', lambda url, json, timeout, headers: sent.update(json) or Resp())
    from langchain_core.messages import HumanMessage, SystemMessage
    vision_ocr.GeminiNativeReader(gemini(), 'gemini-3.8-flash').invoke(
        [SystemMessage(content='p'), HumanMessage(content=[{'type': 'text', 'text': 'x'}])])
    assert sent['generationConfig']['thinkingConfig'] == {'thinkingLevel': 'low'}
    sent.clear()
    vision_ocr.GeminiNativeReader(gemini(), 'gemini-2.5-flash').invoke(
        [SystemMessage(content='p'), HumanMessage(content=[{'type': 'text', 'text': 'x'}])])
    assert 'thinkingConfig' not in sent['generationConfig']  # older models use a different knob


class SlowReader(DayReader):
    def invoke(self, messages):
        time.sleep(0.4)
        return super().invoke(messages)


def test_the_same_photo_is_sent_to_the_model_once_even_when_two_reads_overlap(monkeypatch):
    reader = SlowReader(fixed=hashlib.sha256(PHOTOS[0].read_bytes()).hexdigest())
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', lambda cfg, mode='json_schema_strict', model_id=None: reader)
    monkeypatch.setattr(vision_ocr, '_DAY_SHEETS', {})
    out = []
    threads = [threading.Thread(target=lambda s=s: out.append(extract_image(
        image_path=PHOTOS[0], shift_hint=s, target_date='2026-10-14', settings=gemini()))) for s in ('CA_SANG', 'CA_CHIEU')]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert reader.calls == 1
    assert sorted(filled(r, 'total_collected_vnd') for r in out) == [2328000, 6090000]


def test_upload_starts_the_read_and_the_button_finds_it_done(monkeypatch):
    reader = DayReader(fixed=hashlib.sha256(PHOTOS[0].read_bytes()).hexdigest())
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', lambda cfg, mode='json_schema_strict', model_id=None: reader)
    monkeypatch.setattr(vision_ocr, '_DAY_SHEETS', {})
    monkeypatch.delenv('OCR_PREFETCH', raising=False)
    assert prefetch_reading(PHOTOS[0], '2026-10-14', settings=gemini())
    deadline = time.time() + 5
    while not vision_ocr._DAY_SHEETS and time.time() < deadline:
        time.sleep(0.05)
    result = extract_image(image_path=PHOTOS[0], shift_hint='CA_SANG', target_date='2026-10-14', settings=gemini())
    assert reader.calls == 1  # the button re-used the background reading
    assert filled(result, 'cash_vnd') == 653000


def test_no_background_read_when_ai_reading_is_off(monkeypatch):
    assert not prefetch_reading(PHOTOS[0], settings=AgentSettings(llm_enabled=False))
    assert not prefetch_reading(PHOTOS[0], settings=AgentSettings(llm_enabled=True, provider='gemini', model='m',
                                                                  api_key='x', allow_external_transfer=False))
    monkeypatch.setenv('OCR_PREFETCH', '0')
    assert not prefetch_reading(PHOTOS[0], settings=gemini())


def _native_answer(reading):
    class Resp:
        status_code = 200
        text = ''

        def json(self):
            return {'candidates': [{'content': {'parts': [{'text': reading}]}, 'finishReason': 'STOP'}]}
    return Resp()


def test_gemini_reads_go_to_the_native_endpoint_first(monkeypatch):
    """Measured live: native 3-6 s per page, the compat endpoint's strict schema hung for the full 60 s."""
    import json
    import httpx
    from src.engine.ocr_evaluation import benchmark_cases
    reading = json.dumps(benchmark_cases()[0]['reading'], ensure_ascii=False)
    monkeypatch.setenv('OCR_NATIVE_FIRST', '1')
    monkeypatch.delenv('OCR_MODEL', raising=False)
    compat = []
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', lambda *a, **k: compat.append(1))
    monkeypatch.setattr(httpx, 'post', lambda url, json=None, timeout=None, headers=None: _native_answer(reading))
    monkeypatch.setattr(vision_ocr, '_DAY_SHEETS', {})
    image = PHOTOS[0].parent / '20261014_pos_slip.jpg'
    result = extract_image(image_path=image, shift_hint='CA_TOI', target_date='2026-10-14', settings=gemini())
    assert result['status'] == 'NEEDS_REVIEW' and compat == []
    assert [e['mode'] for e in result['read_log']] == ['gemini_native']


def test_a_model_out_of_quota_is_skipped_for_the_next_photos(monkeypatch):
    import json
    import httpx
    from src.engine.ocr_evaluation import benchmark_cases
    reading = json.dumps(benchmark_cases()[0]['reading'], ensure_ascii=False)
    monkeypatch.setenv('OCR_NATIVE_FIRST', '1')
    monkeypatch.setenv('OCR_FALLBACK_MODELS', 'gemini-3.5-flash-lite')
    monkeypatch.delenv('OCR_MODEL', raising=False)
    urls = []

    class Quota:
        status_code = 429
        text = '{"error": {"status": "RESOURCE_EXHAUSTED"}}'

        def json(self):
            return {'error': {'status': 'RESOURCE_EXHAUSTED', 'message': 'quota'}}

    def post(url, json=None, timeout=None, headers=None):
        urls.append(url.rsplit('/', 1)[1])
        return Quota() if 'gemini-3.8-flash:' in url else _native_answer(reading)

    monkeypatch.setattr(httpx, 'post', post)
    monkeypatch.setattr(vision_ocr, 'build_ocr_reader', lambda *a, **k: (_ for _ in ()).throw(AssertionError('compat')))
    monkeypatch.setattr(vision_ocr, '_DAY_SHEETS', {})
    folder = PHOTOS[0].parent
    extract_image(image_path=folder / '20261014_pos_slip.jpg', shift_hint='CA_TOI', target_date='2026-10-14', settings=gemini())
    assert urls == ['gemini-3.8-flash:generateContent', 'gemini-3.5-flash-lite:generateContent']
    urls.clear()
    extract_image(image_path=PHOTOS[0], shift_hint='CA_SANG', target_date='2026-10-14', settings=gemini())
    assert urls == ['gemini-3.5-flash-lite:generateContent']  # no second call to the model that just said 429


def test_a_hanging_model_does_not_hold_the_photo_the_next_model_is_asked_too(monkeypatch):
    """Measured live: an overloaded model hangs 25-60 s. After OCR_HEDGE_SECONDS the next model is asked in parallel
    and the first good answer wins, so one photo no longer takes a minute."""
    import json
    import time as _t
    import httpx
    from src.engine.ocr_evaluation import benchmark_cases
    reading = json.dumps(benchmark_cases()[0]['reading'], ensure_ascii=False)
    monkeypatch.setenv('OCR_NATIVE_FIRST', '1')
    monkeypatch.setenv('OCR_FALLBACK_MODELS', 'gemini-3.5-flash-lite')
    monkeypatch.delenv('OCR_MODEL', raising=False)
    monkeypatch.setattr(vision_ocr, 'OCR_HEDGE_SECONDS', 0.3)
    monkeypatch.setattr(vision_ocr, '_DAY_SHEETS', {})
    vision_ocr._COOLDOWN.clear()

    def post(url, json=None, timeout=None, headers=None):
        if 'gemini-3.8-flash:' in url:
            _t.sleep(3)  # hangs
            raise httpx.ReadTimeout('slow')
        return _native_answer(reading)

    monkeypatch.setattr(httpx, 'post', post)
    t0 = _t.monotonic()
    result = extract_image(image_path=PHOTOS[0].parent / '20261014_pos_slip.jpg', shift_hint='CA_TOI',
                           target_date='2026-10-14', settings=gemini())
    assert result['status'] == 'NEEDS_REVIEW'
    assert _t.monotonic() - t0 < 2.5
    assert [e['model'] for e in result['read_log']] == ['gemini-3.8-flash', 'gemini-3.5-flash-lite']
    assert result['read_log'][1]['ok'] is True
    vision_ocr._COOLDOWN.clear()


def test_every_model_resting_is_still_tried_rather_than_failing_at_once(monkeypatch):
    import json
    import httpx
    from src.engine.ocr_evaluation import benchmark_cases
    reading = json.dumps(benchmark_cases()[0]['reading'], ensure_ascii=False)
    monkeypatch.setenv('OCR_NATIVE_FIRST', '1')
    monkeypatch.setenv('OCR_FALLBACK_MODELS', 'gemini-3.5-flash-lite')
    monkeypatch.delenv('OCR_MODEL', raising=False)
    monkeypatch.setattr(vision_ocr, '_DAY_SHEETS', {})
    vision_ocr._COOLDOWN.clear()
    vision_ocr._cool_down('gemini-3.8-flash')
    vision_ocr._cool_down('gemini-3.5-flash-lite')
    monkeypatch.setattr(httpx, 'post', lambda url, json=None, timeout=None, headers=None: _native_answer(reading))
    result = extract_image(image_path=PHOTOS[0].parent / '20261014_pos_slip.jpg', shift_hint='CA_TOI',
                           target_date='2026-10-14', settings=gemini())
    assert result['status'] == 'NEEDS_REVIEW'
    vision_ocr._COOLDOWN.clear()
