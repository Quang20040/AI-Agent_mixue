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


def test_everyday_messages_get_human_replies():
    from datetime import datetime, timedelta, timezone

    from src.agent.response_policy import everyday_reply
    now = datetime(2026, 11, 3, 8, 56, tzinfo=timezone(timedelta(hours=7)))
    assert 'đi ăn' in everyday_reply('đói quá', now=now)['text']
    assert 'không vui' in everyday_reply('hôm nay toii buồn', now=now)['text']
    assert everyday_reply('nay ngày mấy', now=now)['text'] == 'Hôm nay là Thứ Ba, ngày 03/11/2026.'
    assert everyday_reply('b làm đc j', now=now)['tool_called'] == 'everyday_capabilities'
    assert 'Xin lỗi' in everyday_reply('wtf', now=now)['text']
    assert 'dự báo' in everyday_reply('tại sao', 'Chưa có dự báo thời tiết vì đang tắt.', now=now)['text']
    for shop_question in ('cách nấu chân trâu', 'doanh thu hôm qua', 'tồn kho đường quả', 'chán quá, kho còn bao nhiêu trân châu'):
        assert everyday_reply(shop_question, now=now) is None, shop_question


def test_chat_switches_to_fallback_model_when_primary_fails(monkeypatch, tmp_path):
    from src.agent.graph_runtime import AgentGraph

    class Broken:
        def bind_tools(self, *a, **k):
            return self

        def invoke(self, messages):
            raise RuntimeError('quota')

    from langchain_core.messages import AIMessage

    class Working(Broken):
        def invoke(self, messages):
            return AIMessage(content='ok')

    settings = AgentSettings(provider='gemini', model='gemini-3.5-flash', audit_path=str(tmp_path / 'a.jsonl'))
    graph = AgentGraph.__new__(AgentGraph)
    graph.settings, graph.model, graph._injected_model = settings, Broken(), False
    monkeypatch.setattr(AgentSettings, 'build_model', lambda self: Working() if self.model == 'gemini-3.8-flash' else Broken())
    monkeypatch.delenv('LLM_FALLBACK_MODELS', raising=False)
    assert graph._invoke_with_fallback([], {}, []).content == 'ok'
    assert graph.settings.model == 'gemini-3.8-flash'


def test_small_talk_goes_to_model_without_tools(tmp_path):
    from langchain_core.messages import AIMessage

    from src.agent.mixue_agent import MixueOperationsAgent

    class ChatModel:
        def __init__(self):
            self.bound, self.seen = False, []

        def bind_tools(self, tools, **kwargs):
            self.bound = True
            return self

        def invoke(self, messages):
            self.seen.append(messages[0].content)
            return AIMessage(content='Đói thì đi ăn gì đó trước đã nhé! Mình là trợ lý quán Mixue, không đặt đồ ăn giúp được.')

    model = ChatModel()
    service = MixueOperationsAgent(settings=AgentSettings(audit_path=str(tmp_path / 'audit.jsonl')), model=model,
                                   checkpointer=InMemorySaver())
    try:
        result = service.process_query('đói quá', 'MANAGER', 'Test')
        assert result['text'].startswith('Đói thì đi ăn')
        assert not model.bound and 'chuyện đời thường' in model.seen[0]
    finally:
        service.close()


def test_new_session_starts_on_the_model_that_worked(monkeypatch, tmp_path):
    """Every browser session builds its own graph; the second one must not wait on the failing model again."""
    from src.agent import graph_runtime
    from src.agent.mixue_agent import MixueOperationsAgent
    asked = []

    def handler(request):
        body = json.loads(request.content)
        asked.append(body['model'])
        if body['model'] == 'gemini-broken':
            return httpx.Response(404, json={'error': {'message': 'model not found'}})
        return httpx.Response(200, json={'id': 'x', 'object': 'chat.completion', 'created': 0, 'model': body['model'],
                                         'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'Chào bạn!'},
                                                      'finish_reason': 'stop'}],
                                         'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})
    mock = httpx.MockTransport(handler)
    monkeypatch.setattr(gemini_compat.httpx, 'HTTPTransport', lambda *a, **k: mock)
    monkeypatch.setenv('LLM_FALLBACK_MODELS', 'gemini-ok')
    monkeypatch.setattr(graph_runtime, '_WORKING_MODEL', {})
    settings = AgentSettings(llm_enabled=True, provider='gemini', model='gemini-broken', api_key='test-key',
                             base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
                             allow_external_transfer=True, audit_path=str(tmp_path / 'audit.jsonl'))
    for _ in range(2):
        service = MixueOperationsAgent(settings=settings, checkpointer=InMemorySaver())
        try:
            assert service.process_query('kể chuyện vui đi', 'MANAGER', 'Test')['text'] == 'Chào bạn!'
        finally:
            service.close()
    assert asked == ['gemini-broken', 'gemini-ok', 'gemini-ok']
