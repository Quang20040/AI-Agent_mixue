"""Gemini 3 rejects a follow-up request (HTTP 400) when a tool call comes back without its thought signature.

The chat must keep working across a tool call and on the next turns ("tại sao" after a weather answer)."""
import json

import httpx
from langgraph.checkpoint.memory import InMemorySaver

from src.agent import gemini_compat
from src.agent.config import AgentSettings


def _fake_gemini(calls):
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        for message in body['messages']:
            for call in message.get('tool_calls') or []:
                signature = (call.get('extra_content') or {}).get('google', {}).get('thought_signature')
                if signature not in {'SIG_REAL', gemini_compat.PLACEHOLDER}:
                    return httpx.Response(400, json={'error': {'message': 'Function call is missing a thought_signature'}})
        last = body['messages'][-1]
        if last['role'] == 'user' and 'thời tiết' in str(last['content']):
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': 'call_weather_1', 'type': 'function',
                'function': {'name': 'get_weather_forecast', 'arguments': json.dumps({'target_date': '2026-11-03'})},
                'extra_content': {'google': {'thought_signature': 'SIG_REAL'}}}]}
        elif last['role'] == 'tool':
            message = {'role': 'assistant', 'content': 'Tính năng thời tiết đang tắt nên mình chưa có dự báo.'}
        else:
            message = {'role': 'assistant', 'content': 'Vì cửa hàng chưa bật lấy dữ liệu thời tiết.'}
        return httpx.Response(200, json={'id': 'x', 'object': 'chat.completion', 'created': 0, 'model': 'gemini-3.5-flash',
                                         'choices': [{'index': 0, 'message': message, 'finish_reason': 'stop'}],
                                         'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})
    return handler


def test_tool_call_and_follow_up_turn_keep_signature(monkeypatch, tmp_path):
    from src.agent.mixue_agent import MixueOperationsAgent
    calls = []
    mock = httpx.MockTransport(_fake_gemini(calls))
    monkeypatch.setattr(gemini_compat.httpx, 'HTTPTransport', lambda *a, **k: mock)
    settings = AgentSettings(llm_enabled=True, provider='gemini', model='gemini-3.5-flash', api_key='test-key',
                             base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
                             allow_external_transfer=True, max_retries=0, audit_path=str(tmp_path / 'audit.jsonl'))
    service = MixueOperationsAgent(settings=settings, model=settings.build_model(), checkpointer=InMemorySaver())
    try:
        first = service.process_query('dự báo thời tiết', 'MANAGER', 'Test')
        assert first['raw_result']['status'] not in {'MODEL_ERROR'}, first
        second = service.process_query('tại sao', 'MANAGER', 'Test')
        assert second['text'] == 'Vì cửa hàng chưa bật lấy dữ liệu thời tiết.'
        follow_up = [c for c in calls if any(m.get('tool_calls') for m in c['messages'])]
        assert follow_up and all(
            call['extra_content']['google']['thought_signature'] == 'SIG_REAL'
            for c in follow_up for m in c['messages'] for call in (m.get('tool_calls') or []))
    finally:
        service.close()


def test_unknown_signature_gets_placeholder():
    payload = {'messages': [{'role': 'assistant', 'tool_calls': [{'id': 'old', 'function': {}}]}]}
    assert gemini_compat.add_signatures(payload, gemini_compat.SignatureMemory())
    assert payload['messages'][0]['tool_calls'][0]['extra_content'] == {
        'google': {'thought_signature': gemini_compat.PLACEHOLDER}}
