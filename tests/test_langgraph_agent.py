"""Exercise the real compiled graph with deterministic chat-model responses."""
import json
import time
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.agent.config import AgentSettings
from src.agent.graph_runtime import Actor, AgentGraph
from src.agent.graph_tools import NoArguments, QueryArguments, ToolSpec


class ScriptedModel:
    def __init__(self, *answers):
        self.answers = iter(answers)
        self.inputs = []
        self.tool_names = []

    def bind_tools(self, tools, **kwargs):
        self.tool_names.append([tool.name for tool in tools])
        return self

    def invoke(self, messages):
        self.inputs.append(messages)
        answer = next(self.answers)
        if isinstance(answer, Exception):
            raise answer
        return answer


class Service:
    def __init__(self):
        self.db = SimpleNamespace(rollback=lambda: None)
        self.multi_agent = SimpleNamespace()
        self.approvals = []

    def __getattr__(self, name):
        return lambda **kwargs: {'status': 'SUCCESS'}

    def tool_check_guardrail(self, query, name):
        return None

    def tool_approve_plan(self, plan_id, role, name):
        self.approvals.append((plan_id, role, name))
        return {'status': 'SUCCESS', 'is_approved': True}


def call(name='lookup', args=None, id='call_1'):
    return AIMessage(content='', tool_calls=[{'name': name, 'args': args or {}, 'id': id}])


def actor(role='MANAGER', user='quang'):
    return Actor(user, 'Quang', role, deadline=time.monotonic() + 60)


@pytest.fixture
def factory(tmp_path):
    graphs = []

    def create(model, tools=None, memory=True, **settings):
        config = AgentSettings(checkpoint_path=str(tmp_path / 'state.sqlite'),
                               audit_path=str(tmp_path / 'audit.jsonl'), **settings)
        graph = AgentGraph(Service(), config, model, InMemorySaver() if memory else None)
        graph.tools = tools or {'lookup': ToolSpec('lookup', 'Lookup test data', NoArguments,
            lambda: {'status': 'SUCCESS', 'value': 42, 'source_refs': ['table:test']})}
        graphs.append(graph)
        return graph
    yield create
    for graph in graphs:
        graph.close()


def test_model_tool_model_and_sources(factory):
    model = ScriptedModel(call(), AIMessage(content='Kết quả là 42.'))
    graph = factory(model)
    result = graph.invoke('Tra dữ liệu', actor(), 'one')
    assert result['execution_mode'] == 'llm'
    assert result['text'] == 'Kết quả là 42.'
    assert result['evidence_refs'] == ['table:test']
    assert isinstance(model.inputs[1][-1], ToolMessage)
    assert json.loads(model.inputs[1][-1].content)['value'] == 42
    assert [event['node'] for event in result['trace']] == ['guard', 'model', 'authorize', 'tools', 'model']


def test_failed_tool_sources_are_not_supporting_evidence(factory):
    tool = ToolSpec('lookup', 'Lookup', NoArguments, lambda: {
        'status': 'TOOL_ERROR', 'source_refs': ['table:unavailable']})
    graph = factory(ScriptedModel(call(), AIMessage(content='Không tra được dữ liệu.')), {'lookup': tool})
    result = graph.invoke('Tra dữ liệu', actor(), 'failed-source')
    assert result['evidence_refs'] == []


def test_checkpoint_current_history_is_compacted_at_turn_boundaries(factory):
    model = ScriptedModel(*[AIMessage(content='Đã nhận yêu cầu.') for _ in range(12)])
    graph = factory(model, max_history_messages=6)
    identity = actor()
    for index in range(12):
        graph.invoke(f'Ghi nhận lượt thử nghiệm {index}', identity, 'bounded-history')
    snapshot = graph.graph.get_state(graph._config(identity, 'bounded-history'))
    assert len(snapshot.values['messages']) <= 8
    assert '11' in snapshot.values['messages'][-2].content


def test_casual_chat_does_not_need_tools(factory):
    graph = factory(ScriptedModel(AIMessage(content='Chào bạn!')))
    result = graph.invoke('Chào lại mình bằng một câu nhé', actor(), 'one')
    assert result['text'] == 'Chào bạn!'
    assert not result['evidence_refs']
    assert result['tool_called'] == 'conversation'


def test_invalid_arguments_recover_without_partial_execution(factory):
    executions = []
    tool = ToolSpec('lookup', 'Query', QueryArguments,
                    lambda query: executions.append(query) or {'status': 'SUCCESS'})
    model = ScriptedModel(call(args={'query': 'x', 'role': 'ADMIN'}),
                          call(args={'query': 'fixed'}, id='call_2'), AIMessage(content='Xong'))
    graph = factory(model, {'lookup': tool})
    assert graph.invoke('Tra', actor(), 'one')['raw_result']['status'] == 'SUCCESS'
    assert executions == ['fixed']
    assert 'INVALID_ARGUMENTS' in model.inputs[1][-1].content


def test_rbac_rechecks_even_unadvertised_tools(factory):
    executions = []
    tool = ToolSpec('lookup', 'Private data', NoArguments, lambda: executions.append(1), 'admin')
    model = ScriptedModel(call(), AIMessage(content='Chào bạn'))
    graph = factory(model, {'lookup': tool})
    result = graph.invoke('Xem', actor('STAFF_OFFICIAL'), 'one')
    assert result['raw_result']['status'] == 'UNAUTHORIZED'
    assert not executions
    assert 'lookup' not in model.tool_names[0]
    # A denied turn must not poison the next request with a dangling tool call.
    graph.invoke('Hãy chào mình', actor('STAFF_OFFICIAL'), 'one')
    assert not any(isinstance(m, AIMessage) and m.tool_calls for m in model.inputs[-1])


def test_unknown_tool_never_executes(factory):
    graph = factory(ScriptedModel(call('run_sql')))
    assert graph.invoke('Xem', actor(), 'one')['raw_result']['status'] == 'UNAUTHORIZED'


def test_tool_budget_stops_infinite_model_loop(factory):
    graph = factory(ScriptedModel(call(), call(id='call_2')), max_tool_calls=1)
    result = graph.invoke('Tra', actor(), 'one')
    assert result['raw_result']['status'] == 'TOOL_LIMIT'


def test_model_error_does_not_leak_provider_secret(factory):
    graph = factory(ScriptedModel(RuntimeError('Authorization: secret_test_key')))
    result = graph.invoke('Nói gì đó', actor(), 'one')
    assert result['raw_result']['status'] == 'MODEL_ERROR'
    assert 'secret_test_key' not in json.dumps(result)


def test_compound_request_needs_both_weather_and_cups(factory):
    tool = ToolSpec('forecast_demand', 'Forecast', NoArguments,
                   lambda: {'status': 'SUCCESS', 'target_date': '2026-10-17',
                            'total_forecasted_cups': 500, 'daily_forecasts': [{}]})
    graph = factory(ScriptedModel(call('forecast_demand'), AIMessage(content='Ngày mai mưa nên chỉ bán 300 ly.')),
                    {'forecast_demand': tool})
    result = graph.invoke('Dự báo số ly ngày mai và lời khuyên theo thời tiết', actor(), 'compound')
    assert result['raw_result']['status'] == 'MISSING_EVIDENCE'
    assert '300' not in result['text']


def test_followup_weather_requires_fresh_tool_result(factory):
    tool = ToolSpec('get_weather_forecast', 'Weather', NoArguments,
                   lambda: {'status': 'WEATHER_UNAVAILABLE', 'message': 'Chưa lấy được dự báo.'})
    model = ScriptedModel(call('get_weather_forecast'), AIMessage(content='Chưa có.'),
                          AIMessage(content='Ngày mai trời nắng 30 độ.'))
    graph = factory(model, {'get_weather_forecast': tool})
    graph.invoke('Thời tiết hôm nay?', actor(), 'weather')
    result = graph.invoke('Còn ngày mai?', actor(), 'weather')
    assert result['raw_result']['status'] == 'MISSING_EVIDENCE'
    assert '30' not in result['text']


def test_model_failure_after_sales_lookup_still_returns_verified_cups(factory):
    tool = ToolSpec('get_daily_sales', 'Sales', NoArguments,
                   lambda: {'status': 'SUCCESS', 'period': '16/10/2026', 'total_quantity_sold': 1574,
                            'source_refs': ['table:sales_daily'], 'all_items': []})
    graph = factory(ScriptedModel(call('get_daily_sales'), RuntimeError('private provider error')),
                    {'get_daily_sales': tool})
    result = graph.invoke('Hôm nay bán bao nhiêu ly?', actor(), 'recovery')
    assert result['raw_result']['status'] == 'SUCCESS'
    assert '1,574 ly' in result['text']
    assert result['evidence_refs'] == ['table:sales_daily']
    assert result['trace'][-1]['reason'] == 'model_unavailable_after_tools'


def test_read_errors_retry_but_writes_do_not(factory):
    attempts = []
    def fail():
        attempts.append(1)
        raise RuntimeError('database details')
    graph = factory(ScriptedModel(call(), AIMessage(content='Không truy xuất được.')),
                    {'lookup': ToolSpec('lookup', 'Read', NoArguments, fail)}, max_retries=2)
    graph.invoke('Tra', actor(), 'one')
    assert len(attempts) == 3
    attempts.clear()
    graph.tools['lookup'] = ToolSpec('lookup', 'Draft', NoArguments, fail, effect='draft')
    graph.model = ScriptedModel(call(), AIMessage(content='Chưa lập được.'))
    graph.invoke('Lập', actor(), 'two')
    assert len(attempts) == 1


def test_repeated_draft_calls_in_one_run_are_deduplicated(factory):
    drafts = []
    tool = ToolSpec('lookup', 'Draft', NoArguments,
        lambda: drafts.append(1) or {'status': 'SUCCESS', 'draft_plan_id': 'one'}, effect='draft')
    graph = factory(ScriptedModel(call(), call(id='call_2'), AIMessage(content='Đã lập dự thảo.')), {'lookup': tool})
    graph.invoke('Lập kế hoạch', actor(), 'one')
    assert len(drafts) == 1


def test_identity_role_and_conversation_are_isolated(factory):
    model = ScriptedModel(*(AIMessage(content='OK') for _ in range(4)))
    graph = factory(model)
    graph.invoke('bí mật phiên một', actor(), 'one')
    graph.invoke('tiếp tục', actor(), 'one')
    assert any(isinstance(m, HumanMessage) and m.content == 'bí mật phiên một' for m in model.inputs[-1])
    for person, conversation in [(actor(user='other'), 'one'), (actor('STAFF_OFFICIAL'), 'one')]:
        graph.invoke('Nói gì đó', person, conversation)
        assert not any(m.content == 'bí mật phiên một' for m in model.inputs[-1])


@pytest.mark.parametrize('approve', [True, False])
def test_approval_pauses_and_requires_trusted_resume(factory, monkeypatch, approve):
    plan = {'plan_id': 'PLAN_PO_1234ABCD', 'plan_type': 'REPLENISHMENT_PO', 'verification': {'is_valid': True}}
    monkeypatch.setattr('src.agent.graph_runtime.get_plan', lambda _: plan)
    model = ScriptedModel(call('request_plan_approval', {'draft_plan_id': plan['plan_id']}), AIMessage(content='Đã xử lý xác nhận.'))
    graph = factory(model)
    from src.agent.graph_tools import ApprovalArguments
    graph.tools = {'request_plan_approval': ToolSpec('request_plan_approval', 'Approve', ApprovalArguments,
                                                    lambda **kwargs: plan, 'admin', 'approval')}
    result = graph.invoke('Duyệt kế hoạch', actor(), 'one')
    assert result['raw_result']['status'] == 'PENDING_APPROVAL'
    assert not graph.service.approvals
    assert graph.resume(True, actor(user='other'), 'one')['raw_result']['status'] == 'NO_PENDING_APPROVAL'
    assert graph.resume(True, actor('STAFF_OFFICIAL'), 'one')['raw_result']['status'] == 'NO_PENDING_APPROVAL'
    graph.resume(approve, actor(), 'one')
    assert len(graph.service.approvals) == int(approve)
    assert graph.resume(True, actor(), 'one')['raw_result']['status'] == 'NO_PENDING_APPROVAL'


def test_sqlite_checkpoint_survives_runtime_recreation(factory):
    first = factory(ScriptedModel(AIMessage(content='OK')), memory=False)
    first.invoke('Tôi hỏi về trân châu', actor(), 'persisted')
    first.close()
    model = ScriptedModel(AIMessage(content='OK'))
    second = factory(model, memory=False)
    second.invoke('Tiếp tục nhé', actor(), 'persisted')
    assert any(m.content == 'Tôi hỏi về trân châu' for m in model.inputs[0])


def test_expired_run_never_calls_model(factory):
    model = ScriptedModel()
    graph = factory(model)
    person = Actor('quang', 'Quang', 'MANAGER', deadline=time.monotonic() - 1)
    assert graph.invoke('Nói gì đó', person, 'one')['raw_result']['status'] == 'RUN_LIMIT'
    assert not model.inputs


def test_openrouter_configuration_uses_compatible_adapter(tmp_path, monkeypatch):
    config = tmp_path / '.env'
    config.write_text('LLM_PROVIDER=openrouter\nLLM_MODEL=openrouter/free\nOPENROUTER_API_KEY=test-key\n', encoding='utf-8')
    settings = AgentSettings.from_env(config)
    assert settings.base_url == 'https://openrouter.ai/api/v1'
    assert settings.api_key.get_secret_value() == 'test-key'
    assert 'test-key' not in repr(settings)
    captured = {}
    monkeypatch.setattr('langchain.chat_models.init_chat_model', lambda model, **kwargs: captured.update(model=model, **kwargs))
    settings.model_copy(update={'llm_enabled': True, 'allow_external_transfer': True}).build_model()
    assert captured['model_provider'] == 'openai'
    assert captured['base_url'] == settings.base_url


def test_hi_is_exactly_one_greeting_without_api_or_data_access(factory):
    model = ScriptedModel()
    graph = factory(model)
    result = graph.invoke('hi', actor(), 'one')
    assert result['text'] == 'Xin chào! 👋'
    assert result['execution_mode'] == 'direct_reply'
    assert not model.inputs


def test_approval_changed_during_pause_is_not_approved(factory, monkeypatch):
    plan = {'plan_id': 'PLAN_PO_1234ABCD', 'plan_type': 'REPLENISHMENT_PO', 'verification': {'is_valid': True}}
    monkeypatch.setattr('src.agent.graph_runtime.get_plan', lambda _: plan)
    from src.agent.graph_tools import ApprovalArguments
    graph = factory(ScriptedModel(call('request_plan_approval', {'draft_plan_id': plan['plan_id']}), AIMessage(content='Kế hoạch đã đổi.')))
    graph.tools = {'request_plan_approval': ToolSpec('request_plan_approval', 'Approve', ApprovalArguments,
                                                    lambda **kwargs: plan, 'admin', 'approval')}
    graph.invoke('Duyệt kế hoạch', actor(), 'one')
    plan['lines'] = [{'quantity': 999}]
    graph.resume(True, actor(), 'one')
    assert not graph.service.approvals


def test_numpy_scalars_are_preserved_as_numbers(factory):
    import numpy as np
    graph = factory(ScriptedModel(call(), AIMessage(content='42')),
        {'lookup': ToolSpec('lookup', 'Number', NoArguments, lambda: {'status': 'SUCCESS', 'value': np.int64(42)})})
    graph.invoke('Tra số', actor(), 'one')
    assert json.loads(graph.model.inputs[1][-1].content)['value'] == 42


def test_real_service_tools_run_inside_model_loop(tmp_path):
    from src.agent.mixue_agent import MixueOperationsAgent
    from src.agent.conversation_store import ConversationStore
    from src.database import Base
    from src.models import MenuItem, SalesDaily
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from datetime import date
    database = create_engine('sqlite:///' + (tmp_path/'sales.sqlite').as_posix())
    Base.metadata.create_all(database)
    session = Session(database)
    session.add(MenuItem(sku_id='SYNTHETIC', sku_name='Synthetic Drink', selling_price_vnd=10000, effective_from=date(2026,1,1)))
    session.flush()
    session.add(SalesDaily(business_date=date(2026,10,12), store_id='2132', sku_id='SYNTHETIC', quantity_sold=12, revenue_vnd=120000))
    session.commit()
    model = ScriptedModel(call('get_data_coverage'),
                          call('get_daily_sales', {'start_date': '2026-10-12'}, id='sales'),
                          AIMessage(content='Đã tra đúng ngày 12/10/2026.'))
    settings = AgentSettings(checkpoint_path=str(tmp_path / 'real-tools.sqlite'),
                             audit_path=str(tmp_path / 'audit.jsonl'))
    service = MixueOperationsAgent(db_session=session, settings=settings, model=model, checkpointer=InMemorySaver(),
                                   conversation_store=ConversationStore(tmp_path/'conversations.sqlite'))
    try:
        result = service.process_query('Tra số ly ngày 12/10/2026', 'MANAGER', 'Test', user_id='test')
        assert result['execution_mode'] == 'llm'
        # 23 operations tools + get_shift_ocr_draft + get_governance_overview (OCR/HITL pillar).
        assert len(model.tool_names[0]) == 25
        assert {'get_shift_ocr_draft', 'get_governance_overview'} <= set(model.tool_names[0])
        assert result['evidence_refs']
        sales_result = json.loads(model.inputs[-1][-1].content)
        assert sales_result['status'] == 'SUCCESS'
        assert sales_result['total_quantity_sold'] > 0
        assert sales_result['target_date'] == '12/10/2026'
        previous_thread = result['thread_id']
        service.reset_conversation()
        assert service.process_query('hi', 'MANAGER', 'Test', user_id='test')['thread_id'] != previous_thread
    finally:
        service.close()
        database.dispose()


def test_stale_conversation_id_is_repaired_instead_of_crashing(tmp_path):
    """A half-finished earlier call must not leave the agent pointing at a conversation the account does not own."""
    from src.agent.mixue_agent import MixueOperationsAgent
    agent = MixueOperationsAgent()
    agent.conversation_history('ADMIN', 'Quản lý', user_id='quanly')
    agent._conversation_id = 'not-a-conversation-of-this-account'
    history = agent.conversation_history('ADMIN', 'Quản lý', user_id='quanly')
    assert history['conversation_id'] != 'not-a-conversation-of-this-account'
    assert agent._ensure_store().owns(agent._conversation_owner(agent._current_actor), history['conversation_id'])
