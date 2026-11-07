from datetime import date

from src.engine import llm_usage


def test_usage_is_logged_and_priced_per_day_feature_and_model():
    llm_usage.record('ocr', 'gemini-3.8-flash', 4000, 4500, 1000, seconds=6.2)
    llm_usage.record('ocr', 'gemini-3.8-flash', 4000, 3500)
    llm_usage.record('chat', 'gemini-3.5-flash', 10000, 800, ok=False)
    rows = {(r['feature'], r['model']): r for r in llm_usage.summary(1)}
    ocr = rows[('ocr', 'gemini-3.8-flash')]
    assert ocr['calls'] == 2 and ocr['input_tokens'] == 8000 and ocr['output_tokens'] == 8000
    assert abs(ocr['cost_usd'] - (8000 * 0.75 + 8000 * 3.75) / 1e6) < 1e-12
    assert rows[('chat', 'gemini-3.5-flash')]['failed'] == 1


def test_unlisted_model_has_no_price_and_promo_price_ends():
    assert llm_usage.cost_usd('gemini-3.6-flash', 1000, 1000) is None
    assert llm_usage.price('gemini-3.8-flash', date(2027, 1, 2)) == (1.50, 7.50)


def test_both_usage_formats_are_read():
    assert llm_usage.usage_from_metadata({'promptTokenCount': 10, 'candidatesTokenCount': 5, 'thoughtsTokenCount': 3}) == (10, 8, 3)
    assert llm_usage.usage_from_metadata({'input_tokens': 7, 'output_tokens': 9,
                                          'output_token_details': {'reasoning': 2}}) == (7, 9, 2)


def test_logging_never_raises(monkeypatch, tmp_path):
    blocker = tmp_path / 'file'
    blocker.write_text('x')
    monkeypatch.setenv('LLM_USAGE_DB', str(blocker / 'llm_usage.db'))  # parent is a file: cannot be created
    llm_usage.record('chat', 'x', 1, 1)
