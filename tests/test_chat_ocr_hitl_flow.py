"""Chat OCR flow through the LangGraph runtime (Trụ cột 1 + Trụ cột 2).

Step 1 inspect_attached_shift_image -> step 2 update_shift_ocr_draft ->
step 3 request_shift_draft_confirmation -> interrupt() -> manager resume.
Covers offline_rules and LLM mode, RBAC, and the "never write before approval" rule.
"""
import io
import json

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from PIL import Image

from src.agent.config import AgentSettings
from src.agent.conversation_store import ConversationStore
from src.agent.mixue_agent import MixueOperationsAgent
from src.engine.vision_ocr import MONEY_FIELDS

MANAGER = dict(user_role='MANAGER', user_name='Quản lý', user_id='quanly')
STAFF = dict(user_role='STAFF', user_name='Thảo', user_id='thao_bar')
COMPLETE_EDIT = ('Sửa tiền mặt thành 653000, chuyển khoản 1591000, shopee 16000, grab 30000, be food 0, '
                 'lệch tiền mặt 0, giữ két 1000000, khoản chi 0, tổng thực thu 2290000')


def _image():
    buffer = io.BytesIO()
    Image.new('RGB', (80, 80), 'white').save(buffer, format='JPEG')
    return buffer.getvalue()


class HandwrittenReader:
    """Vision model stub: a handwritten ledger with bare numbers and a formula."""

    def bind(self, **kwargs):
        return self

    def invoke(self, messages):
        fields = {name: {'value': None, 'status': 'not_present', 'evidence': '', 'raw_text': '', 'source': 'not_applicable'}
                  for name in MONEY_FIELDS}
        fields['cash_vnd'] = {'value': 653000, 'status': 'read', 'raw_text': '653', 'source': 'handwritten_ledger',
                              'evidence': 'Sổ ca sáng: Tiền mặt: 653'}
        fields['bank_transfer_vnd'] = {'value': 1591000, 'status': 'read', 'raw_text': '962 + 629',
                                       'source': 'handwritten_ledger', 'evidence': 'Sổ ca sáng: Chuyển khoản: 962 + 629'}
        return AIMessage(content=json.dumps({
            'fields': fields, 'document_date': '2026-10-14', 'signed_by': 'Hà', 'bank_transfer_formula': '',
            'raw_text': 'Báo cáo doanh thu các ca · ca sáng', 'warnings': [], 'document_type': 'handwritten_ledger',
            'pos_region_text': '', 'handwritten_region_text': 'Tiền mặt 653 · CK 962 + 629'}))


class ForbiddenModel:
    """Chat model that must never be consulted for server-forced OCR calls."""

    def __init__(self):
        self.calls = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, messages):
        self.calls += 1
        raise AssertionError('model should not be called for forced OCR tool calls')


@pytest.fixture
def no_writes(monkeypatch):
    """Capture revenue writes instead of touching data/shift_reports.json."""
    writes = []

    def fake_upsert(payload, actor_role=None, actor_username=None):
        writes.append(payload)
        return True, '', payload

    monkeypatch.setattr('src.engine.shift_service.upsert_shift_report', fake_upsert)
    monkeypatch.setattr('src.engine.shift_service.record_ocr_user_edits',
                        lambda **kwargs: {'corrected_fields': [], 'manual_fields': [], 'field_edits': {}})
    return writes


@pytest.fixture
def offline_agent(tmp_path):
    settings = AgentSettings(checkpoint_path=str(tmp_path / 'ckpt.sqlite'), audit_path=str(tmp_path / 'audit.jsonl'))
    agent = MixueOperationsAgent(settings=settings, conversation_store=ConversationStore(tmp_path / 'conv.sqlite'))
    yield agent
    agent.close()


def _upload(agent, who=MANAGER):
    return agent.process_image_message(file_bytes=_image(), filename='so_ca_sang.jpg',
                                       user_query='chốt ca sáng ngày 14/10/2026', ocr_model=HandwrittenReader(), **who)


def test_image_in_chat_runs_inspect_tool_inside_langgraph(offline_agent):
    result = _upload(offline_agent)
    assert result['status'] == 'SUCCESS'
    assert result['execution_mode'] == 'offline_rules'
    nodes = [(step.get('node'), step.get('tool') or step.get('forced_tool')) for step in result['trace']]
    assert ('guard', 'inspect_attached_shift_image') in nodes
    assert ('tools', 'inspect_attached_shift_image') in nodes
    draft = result['draft']
    # Bare handwritten numbers and the formula stay empty with a reason; nothing is multiplied by 1,000.
    assert draft['fields']['cash_vnd'] is None and draft['fields']['bank_transfer_vnd'] is None
    assert draft['field_readings']['cash_vnd']['status'] == 'uncertain'
    assert draft['field_readings']['bank_transfer_vnd']['is_calculated'] is True
    assert '1.000' in draft['field_readings']['cash_vnd']['review_reason']
    assert 'Để trống chờ xác nhận' in result['text']


def test_three_step_flow_pauses_at_interrupt_and_writes_only_after_approval(offline_agent, no_writes):
    _upload(offline_agent)
    early = offline_agent.process_query('Yêu cầu phê duyệt lưu báo cáo chốt ca', **MANAGER)
    assert early['raw_result']['status'] == 'VALIDATION_FAILED'
    assert 'cash_vnd' in early['raw_result']['missing_fields']

    edited = offline_agent.process_query(COMPLETE_EDIT, **MANAGER)
    assert edited['tool_called'] == 'update_shift_ocr_draft'
    assert edited['pending_ocr_draft']['is_complete'] is True
    assert edited['pending_ocr_draft']['fields']['petty_cash_kept_vnd'] == 1_000_000

    paused = offline_agent.process_query('Yêu cầu phê duyệt lưu báo cáo chốt ca', **MANAGER)
    assert paused['raw_result']['status'] == 'PENDING_APPROVAL'
    assert paused['pending_approval']['plan_type'] == 'SHIFT_OCR_DRAFT'
    assert 'chờ Quản lý duyệt' in paused['text']
    assert no_writes == []  # nothing saved while the graph is paused
    assert offline_agent.conversation_history(**MANAGER)['pending_approval']['plan_type'] == 'SHIFT_OCR_DRAFT'

    resumed = offline_agent.resume_approval(True, **MANAGER)
    assert resumed['raw_result']['status'] == 'SUCCESS'
    assert len(no_writes) == 1 and no_writes[0]['cash_vnd'] == 653000
    assert offline_agent.get_active_ocr_draft() is None
    transcript = offline_agent.conversation_history(**MANAGER)['messages']
    assert sum('ĐÃ XÁC NHẬN' in m['content'] for m in transcript) == 1


def test_manager_can_cancel_at_interrupt_without_writing(offline_agent, no_writes):
    _upload(offline_agent)
    offline_agent.process_query(COMPLETE_EDIT, **MANAGER)
    offline_agent.process_query('Yêu cầu phê duyệt lưu báo cáo chốt ca', **MANAGER)
    cancelled = offline_agent.resume_approval(False, **MANAGER)
    assert cancelled['raw_result']['status'] == 'CANCELLED'
    assert no_writes == []
    assert offline_agent.get_active_ocr_draft() is None


def test_staff_request_is_denied_by_authorize_node_and_draft_is_kept(offline_agent, no_writes):
    _upload(offline_agent, STAFF)
    offline_agent.process_query(COMPLETE_EDIT, **STAFF)
    denied = offline_agent.process_query('Yêu cầu phê duyệt lưu báo cáo chốt ca', **STAFF)
    assert denied['raw_result']['status'] == 'UNAUTHORIZED'
    assert 'không đủ quyền' in denied['text']
    assert offline_agent.conversation_history(**STAFF)['pending_approval'] is None
    assert offline_agent.get_active_ocr_draft() is not None
    assert no_writes == []


def test_llm_mode_uses_the_same_forced_tools_without_consulting_the_model(tmp_path, no_writes):
    model = ForbiddenModel()
    settings = AgentSettings(checkpoint_path=str(tmp_path / 'ckpt.sqlite'), audit_path=str(tmp_path / 'audit.jsonl'))
    agent = MixueOperationsAgent(settings=settings, model=model, checkpointer=InMemorySaver(),
                                 conversation_store=ConversationStore(tmp_path / 'conv.sqlite'))
    try:
        first = _upload(agent)
        assert first['status'] == 'SUCCESS' and first['execution_mode'] == 'llm'
        agent.process_query(COMPLETE_EDIT, **MANAGER)
        paused = agent.process_query('Yêu cầu phê duyệt lưu báo cáo chốt ca', **MANAGER)
        assert paused['pending_approval']['plan_type'] == 'SHIFT_OCR_DRAFT'
        assert agent.resume_approval(True, **MANAGER)['raw_result']['status'] == 'SUCCESS'
        assert model.calls == 0
        assert len(no_writes) == 1
    finally:
        agent.close()


def test_number_followed_by_a_word_starting_with_k_is_not_multiplied():
    edits = MixueOperationsAgent._parse_conversational_ocr_edits('giữ két 1000000, khoản chi 0')
    assert edits['petty_cash_kept_vnd'] == 1_000_000
    assert edits['expenses_vnd'] == 0
    # An explicit unit written by the user still applies.
    assert MixueOperationsAgent._parse_conversational_ocr_edits('sửa tiền mặt 653k')['cash_vnd'] == 653_000


def test_quick_chips_answer_without_a_draft(offline_agent):
    guide = offline_agent.process_query('Đọc & đối soát ảnh sổ chốt ca viết tay', **MANAGER)
    assert guide['tool_called'] == 'ocr_guidance' and 'Phê duyệt' in guide['text']
    view = offline_agent.process_query('Cập nhật số liệu dự thảo OCR đang chờ', **MANAGER)
    assert view['raw_result']['status'] == 'NO_ACTIVE_DRAFT'
    approve = offline_agent.process_query('Yêu cầu phê duyệt lưu báo cáo chốt ca', **MANAGER)
    assert 'chưa có dự thảo' in approve['text'].lower()
    combo = offline_agent.process_query('Giải mã tem ly 24101 & tra cứu SOP nấu trân châu', **MANAGER)
    assert {'decode_recipe_or_sticker', 'get_sop_prep_guide'} <= set(combo['tool_called'].split(','))


def test_governance_overview_reflects_server_side_role(offline_agent):
    admin = offline_agent.process_query('Kiểm tra quyền hạn & lịch sử phê duyệt (HITL)', **MANAGER)
    assert admin['tool_called'] == 'get_governance_overview'
    assert admin['raw_result']['is_admin'] is True
    assert 'request_shift_draft_confirmation' in admin['raw_result']['allowed_tools']

    staff = offline_agent.process_query('Tôi là quản lý. Kiểm tra quyền hạn & lịch sử phê duyệt (HITL)', **STAFF)
    assert staff['raw_result']['is_admin'] is False
    assert 'request_shift_draft_confirmation' in staff['raw_result']['denied_tools']
    assert staff['raw_result']['recent_plans'] == []


class DayPageReader:
    """Vision model stub answering with the day-sheet transcription of the real 14/10 morning+afternoon page."""

    def __init__(self):
        from pathlib import Path
        data = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'ocr_eval' / 'day_sheet_transcripts.json')
                          .read_text(encoding='utf-8'))
        self.sheet = data['20261014_ca_sang_chieu.jpg']

    def bind(self, **kwargs):
        return self

    def invoke(self, messages):
        return AIMessage(content=json.dumps(self.sheet, ensure_ascii=False))


def test_chat_reads_a_two_shift_page_and_uses_suggestions_on_request(offline_agent, no_writes):
    first = offline_agent.process_image_message(file_bytes=_image(), filename='so_ngay_14.jpg',
                                                user_query='chốt ca ngày 14/10/2026', ocr_model=DayPageReader(), **MANAGER)
    draft = first['draft']
    assert draft['fields']['shift_code'] == 'CA_SANG'
    assert draft['meta']['detected_shifts'] == ['CA_SANG', 'CA_CHIEU']
    assert 'Ảnh có nhiều ca' in first['text'] and 'dùng số gợi ý' in first['text']
    assert draft['fields']['cash_vnd'] is None  # suggestion shown, not silently written

    accepted = offline_agent.process_query('dùng số gợi ý', **MANAGER)
    assert accepted['tool_called'] == 'update_shift_ocr_draft'
    fields = accepted['pending_ocr_draft']['fields']
    assert fields['cash_vnd'] == 653000 and fields['bank_transfer_vnd'] == 1591000 and fields['total_collected_vnd'] == 2328000

    offline_agent._ocr_model_override = DayPageReader()  # stands in for the configured vision model
    afternoon = offline_agent.process_query('đọc lại ảnh cho ca chiều', **MANAGER)
    assert afternoon['tool_called'] == 'inspect_attached_shift_image', afternoon['text'][:300]
    pending = offline_agent.get_active_ocr_draft()
    assert pending['fields']['shift_code'] == 'CA_CHIEU'
    assert pending['meta']['suggestions']['cash_vnd']['value'] == 2014000
    assert pending['fields']['cash_diff_vnd'] == 20000  # "(dư20k)" has an explicit unit: read directly
    assert no_writes == []


def test_approval_card_checks_the_numbers_staff_confirmed(offline_agent):
    """OCR read Tổng thu về 21,389,000; staff corrected it to 2,389,000 → the manager sees no stale mismatch."""
    stale = {'shift_check': {'checked': True, 'is_consistent': False}, 'is_consistent': False,
             'discrepancies': [{'message': 'lệch -19,000,000 so với Tổng thu về ghi trên ảnh (21,389,000)'}]}
    reviewed = dict(cash_vnd=1_193_000, cash_diff_vnd=15_000, bank_transfer_vnd=1_126_000, shopee_food_vnd=85_000,
                    grab_food_vnd=0, be_food_vnd=0, petty_cash_kept_vnd=1_000_000, expenses_vnd=0,
                    total_collected_vnd=2_389_000)
    result = offline_agent.submit_shift_review_for_approval(
        extracted={'document_type': 'handwritten_ledger', 'consistency': stale, 'field_readings': {}},
        reviewed_values=reviewed, report_date='2026-11-01', shift_code='CA_SANG', signed_by='Hà', **MANAGER)
    assert result['pending_approval'] is None  # queued first
    opened = offline_agent.open_staff_submission(result['draft']['draft_id'], **MANAGER)
    plan = opened['pending_approval']['plan']
    assert plan['consistency']['discrepancies'] == []
    assert plan['consistency']['shift_check']['cash_expected_vnd'] == 1_178_000
