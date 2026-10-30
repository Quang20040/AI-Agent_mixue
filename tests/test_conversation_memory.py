import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.config import AgentSettings
from src.agent.conversation_store import ConversationStore
from src.agent.mixue_agent import MixueOperationsAgent


class Model:
    def __init__(self):
        self.inputs = []

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, messages):
        self.inputs.append(messages)
        return AIMessage(content='Mình đã hiểu nhé.')


def service(tmp_path, model=None):
    return MixueOperationsAgent(settings=AgentSettings(checkpoint_path=str(tmp_path / 'checkpoints.sqlite'),
                                                       audit_path=str(tmp_path / 'audit.jsonl')),
                                model=model or Model())


def test_store_ownership_and_reopen(tmp_path):
    path = tmp_path / 'history.sqlite'
    store = ConversationStore(path)
    ident = store.create('quang')
    store.append('quang', ident, 'user', 'Chào Tuyết Vương')
    reopened = ConversationStore(path)
    assert reopened.list('quang')[0]['title'] == 'Chào Tuyết Vương'
    assert reopened.messages('quang', ident)[0]['content'] == 'Chào Tuyết Vương'
    assert reopened.list('other') == []
    with pytest.raises(PermissionError):
        reopened.messages('other', ident)
    with pytest.raises(PermissionError):
        reopened.append('other', ident, 'user', 'Thử ghi nhầm')


def test_identity_comes_from_account_without_model_call(tmp_path):
    model = Model()
    agent = service(tmp_path, model)
    try:
        result = agent.process_query('Tôi là ai?', 'MANAGER', 'Bùi Văn Quang', user_id='quanly')
        assert 'Bùi Văn Quang' in result['text']
        assert 'quanly' in result['text']
        assert not model.inputs
        introduction = agent.process_query('Bạn là ai?', 'MANAGER', 'Bùi Văn Quang', user_id='quanly')
        assert 'Tuyết Vương AI' in introduction['text']
        assert introduction['execution_mode'] == 'direct_reply'
        assert not model.inputs
    finally:
        agent.close()


def test_transcript_and_model_memory_survive_service_restart(tmp_path):
    agent = service(tmp_path)
    try:
        agent.process_query('Mình thích câu trả lời ngắn gọn.', 'MANAGER', 'Quang', user_id='quanly')
        first = agent.conversation_history('MANAGER', 'Quang', user_id='quanly')
        assert len(first['messages']) == 2
    finally:
        agent.close()
    model = Model()
    reopened = service(tmp_path, model)
    try:
        restored = reopened.conversation_history('MANAGER', 'Quang', user_id='quanly')
        assert restored['conversation_id'] == first['conversation_id']
        assert restored['messages'] == first['messages']
        reopened.process_query('Mình thích kiểu trả lời nào?', 'MANAGER', 'Quang', user_id='quanly')
        assert any(isinstance(message, HumanMessage) and 'ngắn gọn' in message.content for message in model.inputs[-1])
    finally:
        reopened.close()


def test_new_chat_preserves_old_and_accounts_are_isolated(tmp_path):
    agent = service(tmp_path)
    try:
        agent.process_query('Chuyện riêng của Quang.', 'MANAGER', 'Quang', user_id='quanly')
        first = agent.conversation_history('MANAGER', 'Quang', user_id='quanly')
        new_id = agent.new_conversation('MANAGER', 'Quang', user_id='quanly')
        assert new_id != first['conversation_id']
        assert agent.conversation_history('MANAGER', 'Quang', user_id='quanly')['messages'] == []
        agent.select_conversation(first['conversation_id'], 'MANAGER', 'Quang', user_id='quanly')
        assert agent.conversation_history('MANAGER', 'Quang', user_id='quanly')['messages'] == first['messages']
        agent.reset_conversation(start_new=False)
        assert agent.conversation_history('MANAGER', 'Quang', user_id='quanly')['conversation_id'] == first['conversation_id']
        other = agent.conversation_history('STAFF', 'Thảo', user_id='nhanvien')
        assert other['messages'] == []
        assert all(row['id'] != first['conversation_id'] for row in other['conversations'])
        with pytest.raises(PermissionError):
            agent.select_conversation(first['conversation_id'], 'STAFF', 'Thảo', user_id='nhanvien')
    finally:
        agent.close()
