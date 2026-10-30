import pytest

from scripts.pilot_scorecard import summarize
from src.agent.conversation_store import ConversationStore


def test_feedback_is_persistent_and_owned(tmp_path):
    store = ConversationStore(tmp_path / 'history.sqlite')
    ident = store.create('owner')
    store.append('owner', ident, 'assistant', 'Đã tra dữ liệu.')
    message = store.messages('owner', ident)[0]
    store.feedback('owner', ident, message['message_id'], 1)
    assert store.messages('owner', ident)[0]['rating'] == 1
    with pytest.raises(PermissionError):
        store.feedback('other', ident, message['message_id'], 0)
    second = store.create('owner')
    with pytest.raises(PermissionError):
        store.feedback('owner', second, message['message_id'], 0)


def test_pilot_does_not_claim_old_reports_are_ocr_success():
    report = summarize([{'cash_vnd': 100}], [])
    assert report['reviewed_shift_reports'] == 0
    assert report['helpful_rate_among_rated'] is None
    report = summarize([{'ocr_review': {'corrected_fields': ['cash_vnd'], 'manual_fields': ['be_food_vnd'],
                                        'review_seconds': 20}}], [1, 0])
    assert report['ocr_fields_corrected'] == 1
    assert report['fields_manually_completed'] == 1
    assert report['helpful_rate_among_rated'] == .5
