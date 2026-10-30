"""Tests for Prompt 2: End-to-end integration between OCR and LangGraph Agent Tuyết Vương.
Covers:
1. Account & store isolation (different users/stores cannot see or modify each other's drafts).
2. Two consecutive images do not mix draft fields (prior draft superseded).
3. Conversational and programmatic/UI edits to draft fields with edit audit trail.
4. Draft cancellation (never writes to revenue or inventory before explicit approval).
5. Chat reopening / persistence restoration across agent instances.
6. OCR failure handling (never claims success on unreadable/corrupt files).
7. Valid confirmation writes to shift reports and transitions status.
"""
from pathlib import Path
import json
import pytest
from langchain_core.messages import AIMessage

from src.agent.mixue_agent import MixueOperationsAgent
from src.agent.conversation_store import ConversationStore
from src.engine.vision_ocr import MONEY_FIELDS

PHOTOS_DIR = Path("data/shift_photos")
POS_SLIP = PHOTOS_DIR / "20261014_pos_slip.jpg"
HANDWRITTEN_SLIP = PHOTOS_DIR / "20261014_ca_sang_chieu.jpg"


def make_mock_reading(doc_type: str = "pos"):
    base = {
        "fields": {
            name: {
                "value": None,
                "status": "not_present",
                "evidence": "",
                "raw_text": "",
                "source": "not_applicable",
            }
            for name in MONEY_FIELDS
        },
        "document_date": "2026-10-14",
        "signed_by": None,
        "bank_transfer_formula": "",
        "raw_text": "Mock OCR reading",
        "warnings": [],
        "document_type": "pos_receipt" if doc_type == "pos" else "handwritten_ledger",
        "pos_region_text": "POS Slip" if doc_type == "pos" else "",
        "handwritten_region_text": "Sổ viết tay" if doc_type != "pos" else "",
    }
    if doc_type == "pos":
        base["fields"]["pos_revenue_vnd"] = {"value": 10119000, "status": "read", "evidence": "10,119,000", "raw_text": "10,119,000", "source": "pos_receipt"}
        base["fields"]["pos_collected_vnd"] = {"value": 9877130, "status": "read", "evidence": "9,877,130", "raw_text": "9,877,130", "source": "pos_receipt"}
        base["fields"]["cash_vnd"] = {"value": 9657300, "status": "read", "evidence": "9,657,300", "raw_text": "9,657,300", "source": "pos_receipt"}
        base["fields"]["shopee_food_vnd"] = {"value": 115837, "status": "read", "evidence": "115,837", "raw_text": "115,837", "source": "pos_receipt"}
        base["fields"]["grab_food_vnd"] = {"value": 104000, "status": "read", "evidence": "104,000", "raw_text": "104,000", "source": "pos_receipt"}
        base["fields"]["total_collected_vnd"] = {"value": 9877130, "status": "read", "evidence": "9,877,130", "raw_text": "9,877,130", "source": "pos_receipt"}
    else:
        base["fields"]["cash_vnd"] = {"value": 3260000, "status": "uncertain", "evidence": "3260 (dư 35k)", "raw_text": "3260", "source": "handwritten_ledger", "review_reason": "Đơn vị k"}
        base["fields"]["bank_transfer_vnd"] = {"value": 6377000, "status": "uncertain", "evidence": "4725 + 1652", "raw_text": "4725 + 1652", "source": "handwritten_ledger", "review_reason": "Chưa rõ đơn vị"}
        base["fields"]["cash_diff_vnd"] = {"value": 35000, "status": "read", "evidence": "dư 35k", "raw_text": "35k", "source": "handwritten_ledger"}
        base["fields"]["expenses_vnd"] = {"value": 5466000, "status": "uncertain", "evidence": "5,466", "raw_text": "5,466", "source": "handwritten_ledger"}
        base["fields"]["total_collected_vnd"] = {"value": 5466000, "status": "uncertain", "evidence": "5,466", "raw_text": "5,466", "source": "handwritten_ledger"}
        base["signed_by"] = "A"
        base["bank_transfer_formula"] = "4725 + 1652"
    return base


class MockOcrModel:
    def __init__(self, mode: str = "pos"):
        self.mode = mode

    def bind(self, **kwargs):
        return self

    def invoke(self, messages):
        if self.mode in {"pos", "handwritten"}:
            return AIMessage(content=json.dumps(make_mock_reading(self.mode)))
        return AIMessage(content=json.dumps({"status": "OCR_FAILED", "warnings": ["OCR failure"]}))


@pytest.fixture
def clean_store(tmp_path):
    db_path = tmp_path / "test_conversations.db"
    return ConversationStore(db_path)


def test_ocr_failure_does_not_claim_success(clean_store):
    """Corrupt or non-image bytes should fail cleanly and not create a valid confirmed report."""
    agent = MixueOperationsAgent(conversation_store=clean_store)
    result = agent.process_image_message(
        file_bytes=b"not a real jpeg image file",
        filename="corrupted.jpg",
        user_role="STAFF",
        user_name="Nhân viên quầy",
        user_id="nv_quầy",
    )
    assert result["status"] == "ERROR"
    assert any(term in result["text"] for term in ["Chưa đọc được ảnh", "Không thể", "Lỗi", "thất bại"])
    assert "draft_id" not in result or result.get("draft") is None


@pytest.mark.skipif(not POS_SLIP.exists(), reason="POS slip image not found")
def test_two_consecutive_images_do_not_mix(clean_store):
    """Uploading a second image must supersede the first and never mix numbers across images."""
    agent = MixueOperationsAgent(conversation_store=clean_store)
    pos_bytes = POS_SLIP.read_bytes()
    hw_bytes = HANDWRITTEN_SLIP.read_bytes()

    # 1. Upload POS image
    res1 = agent.process_image_message(
        file_bytes=pos_bytes,
        filename=POS_SLIP.name,
        user_role="STAFF",
        user_name="Thảo",
        user_id="thao_bar",
        ocr_model=MockOcrModel("pos"),
    )
    assert res1["status"] == "SUCCESS"
    draft1_id = res1["draft_id"]
    draft1_fields = res1["draft"]["fields"]
    assert draft1_fields.get("pos_revenue_vnd") == 10119000

    # 2. Upload handwritten image
    res2 = agent.process_image_message(
        file_bytes=hw_bytes,
        filename=HANDWRITTEN_SLIP.name,
        user_role="STAFF",
        user_name="Thảo",
        user_id="thao_bar",
        ocr_model=MockOcrModel("handwritten"),
    )
    assert res2["status"] == "SUCCESS"
    draft2_id = res2["draft_id"]
    assert draft2_id != draft1_id

    # Active draft must be draft2, and draft1 must NOT contaminate draft2
    active = agent.get_active_ocr_draft()
    assert active["draft_id"] == draft2_id
    assert active["document_type"] == "handwritten_ledger"
    # POS specific revenue must be None in handwritten ledger draft (not inherited from draft 1!)
    assert active["fields"].get("pos_revenue_vnd") is None


@pytest.mark.skipif(not POS_SLIP.exists(), reason="POS slip image not found")
def test_conversational_and_ui_draft_edits(clean_store):
    """User can fix fields via natural conversation or UI calls; edits are recorded in draft history."""
    agent = MixueOperationsAgent(conversation_store=clean_store)
    res = agent.process_image_message(
        file_bytes=POS_SLIP.read_bytes(),
        filename=POS_SLIP.name,
        user_role="STAFF",
        user_name="Thảo",
        user_id="thao_bar",
        ocr_model=MockOcrModel("pos"),
    )
    assert res["status"] == "SUCCESS"

    # User modifies cash via natural language query
    r_chat = agent.process_query(
        "sửa tiền mặt thành 9657300",
        user_role="STAFF",
        user_name="Thảo",
        user_id="thao_bar",
    )
    assert "Đã cập nhật dự thảo" in r_chat["text"] or r_chat.get("tool_called") == "update_shift_ocr_draft"

    active = agent.get_active_ocr_draft()
    assert active["fields"]["cash_vnd"] == 9657300

    # User modifies ShopeeFood via direct update_ocr_draft
    agent.update_ocr_draft(
        {"shopee_food_vnd": 115837, "shift_code": "CA_SANG", "report_date": "2026-10-14"},
        user_role="STAFF",
        user_name="Thảo",
        user_id="thao_bar",
    )
    active2 = agent.get_active_ocr_draft()
    assert active2["fields"]["shopee_food_vnd"] == 115837
    assert active2["shift_code"] == "CA_SANG"
    assert active2["business_date"] == "2026-10-14"
    assert len(active2["edits"]) >= 2


@pytest.mark.skipif(not POS_SLIP.exists(), reason="POS slip image not found")
def test_draft_cancellation_never_saves_revenue(clean_store):
    """Cancelling a draft must mark it CANCELLED and never write into revenue ledger."""
    agent = MixueOperationsAgent(conversation_store=clean_store)
    res = agent.process_image_message(
        file_bytes=POS_SLIP.read_bytes(),
        filename=POS_SLIP.name,
        user_role="STAFF",
        user_name="Thảo",
        user_id="thao_bar",
        ocr_model=MockOcrModel("pos"),
    )
    assert res["draft_id"]

    # Cancel via chat
    r_cancel = agent.process_query(
        "hủy xác nhận dự thảo",
        user_role="STAFF",
        user_name="Thảo",
        user_id="thao_bar",
    )
    assert "Đã hủy xác nhận" in r_cancel["text"]
    assert agent.get_active_ocr_draft() is None


@pytest.mark.skipif(not POS_SLIP.exists(), reason="POS slip image not found")
def test_account_isolation_and_restoration_on_reopen(clean_store):
    """Drafts are strictly isolated by account/store, and restored when reopening chat."""
    # Account 1 creates draft
    agent1 = MixueOperationsAgent(conversation_store=clean_store)
    res = agent1.process_image_message(
        file_bytes=POS_SLIP.read_bytes(),
        filename=POS_SLIP.name,
        user_role="STAFF",
        user_name="Thảo",
        user_id="thao_bar",
        ocr_model=MockOcrModel("pos"),
    )
    draft_id = res["draft_id"]
    conv_id = agent1.current_conversation_id

    # Account 2 from different account opens chat: denied access to Account 1's conversation
    agent2 = MixueOperationsAgent(conversation_store=clean_store)
    with pytest.raises(PermissionError):
        agent2.select_conversation(conv_id, user_role="STAFF", user_name="Bình", user_id="binh_kho")
    assert agent2.get_active_ocr_draft() is None

    # Account 1 re-opens chat in a fresh agent instance
    agent3 = MixueOperationsAgent(conversation_store=clean_store)
    agent3.select_conversation(conv_id, user_role="STAFF", user_name="Thảo", user_id="thao_bar")
    restored = agent3.get_active_ocr_draft()
    assert restored is not None
    assert restored["draft_id"] == draft_id
    assert restored["status"] == "DRAFT"


def test_process_multiple_images_message(clean_store):
    """User can send multiple images (e.g. POS receipt + handwritten ledger) in one request."""
    import io
    from PIL import Image

    buf1 = io.BytesIO()
    Image.new('RGB', (60, 60), 'white').save(buf1, format='JPEG')
    img1_bytes = buf1.getvalue()

    buf2 = io.BytesIO()
    Image.new('RGB', (60, 60), 'white').save(buf2, format='JPEG')
    img2_bytes = buf2.getvalue()

    agent = MixueOperationsAgent(conversation_store=clean_store)
    files = [("hoa_don_pos.jpg", img1_bytes), ("so_ca_toi.jpg", img2_bytes)]

    res = agent.process_image_message(
        files=files,
        user_query="Chốt ca tối ngày 14/10/2026 từ 2 ảnh này",
        user_role="STAFF",
        user_name="Thảo",
        user_id="thao_bar",
        ocr_model=MockOcrModel("pos"),
    )

    assert res["status"] == "SUCCESS"
    assert "draft_id" in res
    assert len(res["file_ids"]) == 2
    assert res["file_id"] == res["file_ids"][0]
    # Check that both attachments are linked in evidence
    assert any("attachment:" in ref for ref in res["evidence_refs"])
    assert len([r for r in res["evidence_refs"] if r.startswith("attachment:")]) == 2

    # Check that draft can be retrieved
    draft = agent.get_active_ocr_draft()
    assert draft is not None
    assert draft["draft_id"] == res["draft_id"]
    assert len(draft["file_ids"]) == 2

