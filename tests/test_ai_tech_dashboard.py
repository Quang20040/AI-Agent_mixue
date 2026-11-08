"""Admin-only AI engineering dashboard: numbers come from logged turns (structure only, no chat text)."""
import json

from src.auth import AI_TECH_PAGE, can_access_page
from src.engine import agent_events, ai_metrics


def test_only_admins_see_the_page():
    assert can_access_page('MANAGER', AI_TECH_PAGE) and can_access_page('OWNER', AI_TECH_PAGE)
    assert not can_access_page('STAFF_OFFICIAL', AI_TECH_PAGE) and not can_access_page('STAFF_PROBATION', AI_TECH_PAGE)


def test_turn_log_keeps_structure_not_text():
    agent_events.record_turn('chat', 'MANAGER', {
        'text': 'SECRET ANSWER', 'execution_mode': 'llm', 'evidence_refs': ['sop:1'],
        'trace': [{'node': 'guard', 'result': 'passed'},
                  {'node': 'model', 'requested': ['search_operating_knowledge'], 'input_tokens': 900, 'output_tokens': 80},
                  {'node': 'authorize', 'result': 'allowed', 'calls': [{'name': 'search_operating_knowledge', 'args': {'query': 'SECRET Q'}}]},
                  {'node': 'tools', 'tool': 'search_operating_knowledge', 'status': 'SUCCESS', 'duration_ms': 40,
                   'args': 'query=SECRET Q', 'summary': 'SECRET RESULT', 'sources': 3}]}, 1234)
    agent_events.record_turn('chat', 'STAFF', {'execution_mode': 'offline_rules', 'raw_result': {'status': 'GUARDRAIL_TRIGGERED'},
                                              'trace': [{'node': 'guard', 'result': 'blocked', 'category': 'PROMPT_INJECTION_DEFENSE'}]}, 3)
    rows = agent_events.turns(1)
    assert 'SECRET' not in json.dumps(rows, ensure_ascii=False)
    a = ai_metrics.agent_section(1)
    assert a['guard']['blocked'] >= 1 and 'Prompt injection' in a['guard']['by_category']
    tool = next(t for t in a['tools'] if t['tool'] == 'search_operating_knowledge')
    assert tool['calls'] >= 1 and tool['ok_pct'] == 100.0
    assert a['rag']['with_sources'] >= 1


def test_redteam_and_retrieval_benchmark(tmp_path):
    from src.agent.config import AgentSettings
    from src.agent.mixue_agent import MixueOperationsAgent
    agent = MixueOperationsAgent(settings=AgentSettings.from_env().model_copy(update={'llm_enabled': False}))
    try:
        rt = ai_metrics.redteam(agent)
    finally:
        agent.close()
    assert rt['blocked_pct'] == 100.0 and rt['false_block_pct'] == 0.0
    methods = [r['method'] for r in ai_metrics.retrieval_benchmark()['rows']]
    assert 'RRF (BM25 + vector)' in methods and 'Learning-to-rank + embedding' in methods


def test_ocr_accuracy_compares_prefill_with_approved(tmp_path, monkeypatch):
    import sqlite3
    db = tmp_path / 'conversations.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE ocr_shift_drafts (status TEXT, fields_json TEXT, field_readings_json TEXT, meta_json TEXT, created_at TEXT)')
        today = ai_metrics._since(1).isoformat()
        read = {'cash_vnd': {'status': 'read', 'value': 500000}, 'bank_transfer_vnd': {'status': 'uncertain', 'value': 120000},
                'grab_vnd': {'status': 'not_present', 'value': None}}
        con.execute('INSERT INTO ocr_shift_drafts VALUES (?,?,?,?,?)', ('APPROVED', json.dumps(
            {'cash_vnd': 500000, 'bank_transfer_vnd': 1200000, 'grab_vnd': None}), json.dumps(read), '{"review_seconds": 40}', today + 'T08:00'))
    monkeypatch.setattr(ai_metrics, '_private_dir', lambda: tmp_path)
    o = ai_metrics.ocr_section(1)
    assert o['reports_scored'] == 1 and o['fields_checked'] == 2       # Grab: not on paper, not filled → not scored
    assert o['field_accuracy_pct'] == 50.0 and o['reports_without_edit_pct'] == 0.0
    assert o['review_seconds_p50'] == 40


def test_admin_page_renders():
    from test_e2e_staff_manager import _open
    app = _open('quick_login_owner')
    app.radio(key='main_navigation').set_value(AI_TECH_PAGE).run()
    assert not app.exception, app.exception
    assert any('Guardrail chặn' in m.label for m in app.metric)
    app.button(key='run_scorecard_offline').click().run()
    assert not app.exception, app.exception
    assert ai_metrics.scorecard()['total'] == 50


def test_staff_cannot_open_page():
    from test_e2e_staff_manager import _open
    app = _open('quick_login_staff')
    assert AI_TECH_PAGE not in app.radio(key='main_navigation').options
