"""Regressions from real feedback: greetings and task-focused preparation answers."""
import pytest

from src.agent.mixue_agent import MixueOperationsAgent
from src.agent.multi_agent.multi_agent_orchestrator import MultiAgentOrchestrator
from src.agent.multi_agent.nlp_synthesizer import NLPSynthesizer
from src.agent.response_policy import conversational_reply


@pytest.fixture
def agent():
    instance = MixueOperationsAgent()
    yield instance
    instance.close()


@pytest.mark.parametrize('query', ['hi', 'Hi!', 'hello 👋', 'xin chào', 'chào bạn', 'hi Tuyết Vương'])
@pytest.mark.parametrize('role', ['ADMIN', 'STAFF'])
def test_greeting_does_not_query_data_or_reset_context(agent, monkeypatch, query, role):
    def unexpected(*args, **kwargs):
        pytest.fail('A greeting must not look up business data')
    monkeypatch.setattr(agent, 'tool_get_daily_sales', unexpected)
    monkeypatch.setattr(agent.multi_agent, 'dispatch', unexpected)
    agent.memory['last_topic'] = 'sales'
    reply = agent.process_query(query, user_role=role, user_name='Bùi Văn Quang')
    assert reply['text'] == 'Xin chào! 👋'
    assert reply['evidence_refs'] == []
    assert agent.memory['last_topic'] == 'sales'


@pytest.mark.parametrize('query', ['hi, doanh thu 10/10 bao nhiêu?', 'xin chào, cách nấu trân châu', 'hi cho mình công thức TS1'])
def test_greeting_prefix_does_not_swallow_task(query):
    assert conversational_reply(query) is None


@pytest.mark.parametrize('query', ['cách nấu trân châu', 'công thức nấu trân châu', 'cách nấu chân trâu'])
def test_pearl_cooking_is_focused_and_keeps_instructions(agent, monkeypatch, query):
    monkeypatch.setattr(agent.multi_agent.docs_agent, 'search', lambda *a, **k: pytest.fail('Known SOP should not search project docs'))
    reply = agent.process_query(query, user_role='ADMIN')
    text = reply['text']
    assert reply['tool_called'] == 'get_sop_prep_guide'
    for required in ['1000 g', '4000 ml', '500 g', '35 phút', '30 phút', '10 phút', '4 giờ']:
        assert required in text
    for irrelevant in ['Định nghĩa', 'ME_TP02', 'lục tìm', 'Repo', 'docs/demo.md', 'FIFO', 'Maker-Checker', 'NL20', '~22 ly']:
        assert irrelevant not in text
    assert '**Định lượng 1 mẻ:**' in text
    assert '**Định lượng 0.5 mẻ:**' not in text
    assert any('09_Cong_thuc_so_che_theo_me' in ref for ref in reply['evidence_refs'])


def test_storage_question_does_not_repeat_recipe(agent):
    reply = agent.process_query('Trân châu đã nấu bảo quản và hạn dùng thế nào?', user_role='STAFF')
    assert '4 giờ' in reply['text']
    assert 'không bảo quản trong tủ lạnh' in reply['text']
    assert '35 phút' not in reply['text']
    assert 'Định lượng' not in reply['text']


def test_half_batch_uses_documented_quantities(agent):
    reply = agent.process_query('Cách nấu trân châu nửa mẻ', user_role='STAFF')
    assert '**Định lượng 0.5 mẻ:**' in reply['text']
    assert '**3000 ml**' in reply['text']
    assert '**500 g**' in reply['text']
    assert '**250 g**' in reply['text']


def test_unlisted_batch_does_not_invent_scaling(agent):
    reply = agent.process_query('Cách nấu trân châu 2 mẻ', user_role='STAFF')
    assert reply['status'] == 'NEEDS_CLARIFICATION'
    assert '**Cách làm:**' not in reply['text']


def test_detailed_sop_is_available_on_request(agent):
    reply = agent.process_query('Hướng dẫn chi tiết cách nấu trân châu, tất cả các mẻ', user_role='STAFF')
    assert '**Định lượng 0.5 mẻ:**' in reply['text']
    assert '**Định lượng 1 mẻ:**' in reply['text']


def test_plain_greeting_through_orchestrator():
    reply = MultiAgentOrchestrator().dispatch('hi', user_role='ADMIN')
    assert reply['text'] == 'Xin chào! 👋'
    assert not reply['evidence_refs']


def test_empty_search_admits_missing_information():
    reply = NLPSynthesizer().synthesize('thông tin không có')
    assert reply['status'] == 'NO_DATA'
    assert not reply['evidence_refs']


def test_known_answer_does_not_append_project_document():
    guide = {'status': 'SUCCESS', 'type': 'SOP_PREP_GUIDE', 'name': 'Trân châu',
             'storage': 'Nhiệt độ phòng', 'shelf_life': '4 giờ', 'batches': {},
             'steps': ['Nấu 35 phút.'], 'evidence_refs': ['sop:pearl']}
    docs = [{'file_path': 'docs/demo.md', 'title': 'Demo', 'content': 'IRRELEVANT PROJECT REPORT'}]
    reply = NLPSynthesizer().synthesize('cách nấu trân châu', bom_results=guide, docs_results=docs)
    assert 'IRRELEVANT' not in reply['text']
    assert reply['evidence_refs'] == ['sop:pearl']
