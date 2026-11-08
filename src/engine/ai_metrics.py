"""Numbers for the AI engineering dashboard (admin only), grouped by the agent-building topics:

  Prompt & token economy · Human-in-the-loop · Function calling & tool contracts · Memory
  RAG & grounding · Guardrails & red teaming · Tracing & latency · Fallback · Benchmarks · Vision OCR

Live numbers come from what the app already records: ``agent_turns`` (structure of every chat turn, no text),
``llm_usage`` (tokens, cost, OCR seconds), the OCR drafts (what the model read vs what staff approved),
saved plans and chat feedback. Offline numbers (retrieval benchmark, agent scorecard) come from files.
"""
from __future__ import annotations

import json
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.engine import agent_events, llm_usage

MONEY_FIELDS = ('cash_vnd', 'bank_transfer_vnd', 'grab_vnd', 'shopee_food_vnd', 'be_food_vnd', 'cash_diff_vnd')
FIELD_VI = {'cash_vnd': 'Tiền mặt', 'bank_transfer_vnd': 'Chuyển khoản', 'grab_vnd': 'GrabFood',
            'shopee_food_vnd': 'ShopeeFood', 'be_food_vnd': 'beFood', 'cash_diff_vnd': 'Chênh lệch tiền mặt',
            'total_collected_vnd': 'Tổng thu'}
RAG_TOOLS = {'search_operating_knowledge', 'get_sop_prep_guide', 'decode_recipe_or_sticker'}
GUARD_VI = {'PROMPT_INJECTION_DEFENSE': 'Prompt injection', 'CREDENTIAL_EXFILTRATION_DEFENSE': 'Đòi mật khẩu / API key',
            'PRIVILEGE_ESCALATION_DEFENSE': 'Đòi nâng quyền'}
MODE_VI = {'llm': 'Gemini (LLM)', 'offline_rules': 'Luật offline', 'offline_fallback': 'Dự phòng khi AI lỗi',
           'direct_reply': 'Trả lời trực tiếp', 'unknown': 'Khác'}


def _pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


def _p(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return values[min(len(values) - 1, round(q * (len(values) - 1)))]


def _private_dir() -> Path:
    from src.agent.config import AgentSettings
    return Path(AgentSettings.from_env().checkpoint_path).parent


def _since(days, today=None):
    today = today or datetime.now(llm_usage.TZ).date()
    return today - timedelta(days=days - 1)


# --- live: agent turns ---------------------------------------------------------------------------------------

def agent_section(days: int = 14) -> dict[str, Any]:
    rows = agent_events.turns(days)
    chats = [r for r in rows if r['kind'] == 'chat']
    per_day = Counter(r['day'] for r in chats)
    modes = Counter(r['mode'] for r in chats)

    # Guardrails: every chat turn goes through the guard node first (router turns are OCR-form shortcuts).
    guarded = [r for r in chats if r['guard'] in {'passed', 'blocked', 'direct_reply'}]
    blocked = [r for r in guarded if r['guard'] == 'blocked']

    # Function calling
    calls, auth = defaultdict(list), Counter()
    denied = Counter()
    requested = Counter()
    for r in rows:
        for e in r['trace']:
            node = e.get('node')
            if node == 'tools':
                calls[e.get('tool') or '?'].append(e)
            elif node == 'authorize':
                auth[e.get('result') or '?'] += 1
                if e.get('result') == 'denied':
                    denied[e.get('tool') or '?'] += 1
            elif node == 'model':
                requested.update(e.get('requested') or [])
    tools = sorted(({'tool': name, 'calls': len(ev),
                     'ok_pct': _pct(sum(1 for e in ev if str(e.get('status', 'SUCCESS')) in {'SUCCESS', 'OK', 'PENDING_APPROVAL', 'NEEDS_REVIEW'}), len(ev)),
                     'p50_ms': _p([e.get('duration_ms') for e in ev], 0.5),
                     'p95_ms': _p([e.get('duration_ms') for e in ev], 0.95)} for name, ev in calls.items()),
                   key=lambda x: -x['calls'])

    # Human in the loop (from traces): approval node = the only place a write happens
    approvals = [e for r in rows for e in r['trace'] if e.get('node') == 'approval']
    hitl = {'paused_for_approval': sum(r['pending_approval'] for r in rows),
            'approved_turns': sum(1 for r in rows if r['kind'] == 'approval'),
            'rejected_turns': sum(1 for r in rows if r['kind'] == 'rejection'),
            'writes_after_approval': len(approvals)}

    # RAG & grounding
    rag = [e for name in RAG_TOOLS for e in calls.get(name, [])]
    llm_chats = [r for r in chats if r['mode'] == 'llm']
    grounded = [r for r in llm_chats if r['evidence'] > 0]

    # Tracing, latency, tokens
    by_mode = {}
    for mode in modes:
        lat = [r['elapsed_ms'] for r in chats if r['mode'] == mode]
        by_mode[mode] = {'label': MODE_VI.get(mode, mode), 'turns': len(lat), 'p50_ms': _p(lat, 0.5), 'p95_ms': _p(lat, 0.95)}
    fallback = [r for r in chats if r['mode'] == 'offline_fallback']
    errors = Counter(r['status'] for r in chats if r['status'] in {'MODEL_ERROR', 'MODEL_CONFIGURATION_ERROR', 'INTERNAL_ERROR', 'TIMEOUT'})
    return {
        'days': days, 'chat_turns': len(chats), 'per_day': dict(sorted(per_day.items())),
        'modes': {MODE_VI.get(k, k): v for k, v in modes.most_common()},
        'guard': {'checked': len(guarded), 'blocked': len(blocked), 'blocked_pct': _pct(len(blocked), len(guarded)),
                  'by_category': {GUARD_VI.get(k, k or 'Khác'): v for k, v in Counter(r['guard_category'] for r in blocked).most_common()},
                  'direct_replies': sum(1 for r in guarded if r['guard'] == 'direct_reply')},
        'tools': tools, 'tool_calls': sum(t['calls'] for t in tools),
        'authorize': dict(auth), 'denied_by_tool': dict(denied.most_common()),
        'tools_per_llm_turn': round(statistics.mean([sum(1 for e in r['trace'] if e.get('node') == 'tools') for r in llm_chats]), 2) if llm_chats else None,
        'hitl': hitl,
        'rag': {'calls': len(rag), 'with_sources': sum(1 for e in rag if (e.get('sources') or 0) > 0),
                'with_sources_pct': _pct(sum(1 for e in rag if (e.get('sources') or 0) > 0), len(rag)),
                'llm_answers': len(llm_chats), 'llm_answers_with_evidence_pct': _pct(len(grounded), len(llm_chats))},
        'latency': by_mode,
        'model_calls_per_llm_turn': round(statistics.mean([r['model_calls'] for r in llm_chats]), 2) if llm_chats else None,
        'tokens_per_llm_turn': round(statistics.mean([r['input_tokens'] + r['output_tokens'] for r in llm_chats])) if llm_chats else None,
        'fallback': {'turns': len(fallback), 'pct': _pct(len(fallback), len(chats)), 'errors': dict(errors)},
    }


# --- live: LLM usage ----------------------------------------------------------------------------------------

def usage_section(days: int = 14) -> dict[str, Any]:
    rows = llm_usage.summary(days)
    by_feature = defaultdict(lambda: {'calls': 0, 'failed': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0})
    per_day = defaultdict(float)
    for r in rows:
        f = by_feature[r['feature']]
        for k in ('calls', 'failed', 'input_tokens', 'output_tokens'):
            f[k] += r[k]
        f['cost_usd'] += r['cost_usd'] or 0.0
        per_day[r['day']] += r['cost_usd'] or 0.0
    try:
        start = _since(days).isoformat()
        with llm_usage._LOCK, llm_usage._connect() as con:
            ocr_seconds = [s for (s,) in con.execute(
                "SELECT seconds FROM llm_usage WHERE feature='ocr' AND ok=1 AND seconds IS NOT NULL AND day >= ?", (start,))]
    except Exception:  # noqa: BLE001
        ocr_seconds = []
    total = sum(f['cost_usd'] for f in by_feature.values())
    return {'by_feature': {k: dict(v) for k, v in by_feature.items()}, 'cost_usd': round(total, 4),
            'cost_per_day_usd': round(total / days, 4), 'cost_by_day': dict(sorted(per_day.items())),
            'ocr_call_p50_s': _p(ocr_seconds, 0.5), 'ocr_call_p95_s': _p(ocr_seconds, 0.95)}


# --- live: OCR accuracy (what the model read vs what staff and the manager approved) -------------------------

def _ocr_value(reading: dict[str, Any] | None):
    reading = reading or {}
    if reading.get('status') in {'not_present', 'unreadable'}:
        return None
    return reading.get('normalized_value') if reading.get('normalized_value') is not None else reading.get('value')


def ocr_section(days: int = 14) -> dict[str, Any]:
    path = _private_dir() / 'conversations.sqlite'
    start = _since(days).isoformat()
    drafts = []
    if path.exists():
        try:
            with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as con:
                con.row_factory = sqlite3.Row
                drafts = [dict(r) for r in con.execute(
                    "SELECT status, fields_json, field_readings_json, meta_json, created_at FROM ocr_shift_drafts "
                    "WHERE substr(created_at,1,10) >= ?", (start,))]
        except sqlite3.Error:
            drafts = []
    status = Counter(d['status'] for d in drafts)
    # staff checked the numbers (SUBMITTED/FORWARDED) or a manager approved them (APPROVED/CONFIRMED)
    reviewed = [d for d in drafts if d['status'] in {'APPROVED', 'CONFIRMED', 'SUBMITTED', 'FORWARDED'}]
    per_field = defaultdict(lambda: {'checked': 0, 'correct': 0, 'prefilled': 0})
    all_right, review_seconds = 0, []
    for d in reviewed:
        fields = json.loads(d['fields_json'] or '{}')
        readings = json.loads(d['field_readings_json'] or '{}')
        meta = json.loads(d['meta_json'] or '{}')
        if not readings:
            continue
        ok_all = True
        for name in MONEY_FIELDS:
            final = fields.get(name)
            got = _ocr_value(readings.get(name))
            if got is None and final in (None, '', 0):
                continue   # not on the paper and not filled in: nothing to score
            stats = per_field[name]
            stats['checked'] += 1
            stats['prefilled'] += got is not None
            right = (got if got is not None else 0) == (int(final) if final not in (None, '') else 0)
            stats['correct'] += right
            ok_all &= right
        all_right += ok_all
        if meta.get('review_seconds') is not None:
            review_seconds.append(float(meta['review_seconds']))
    checked = sum(v['checked'] for v in per_field.values())
    correct = sum(v['correct'] for v in per_field.values())
    scored = sum(1 for d in reviewed if json.loads(d['field_readings_json'] or '{}'))
    return {'drafts': len(drafts), 'status': dict(status), 'reports_scored': scored,
            'field_accuracy_pct': _pct(correct, checked), 'fields_checked': checked,
            'reports_without_edit_pct': _pct(all_right, scored),
            'per_field': [{'field': FIELD_VI.get(k, k), **v, 'accuracy_pct': _pct(v['correct'], v['checked'])}
                          for k, v in per_field.items()],
            'review_seconds_p50': _p(review_seconds, 0.5)}


# --- live: approvals, memory, feedback ------------------------------------------------------------------------

def plans_section(days: int = 14) -> dict[str, Any]:
    from src.engine.plan_service import list_plans
    start = _since(days).isoformat()
    plans = [p for p in list_plans() if str(p.get('created_at') or p.get('target_date') or '')[:10] >= start]
    by_type = defaultdict(Counter)
    for p in plans:
        by_type[p.get('plan_type', '?')][p.get('status', '?')] += 1
    edited = sum(1 for p in plans if p.get('edits'))
    return {'plans': len(plans), 'by_type': {k: dict(v) for k, v in by_type.items()},
            'edited_by_manager': edited, 'approved_with_approver': sum(1 for p in plans if p.get('status') in {'APPROVED', 'RECEIVED'} and p.get('approved_by')),
            'approved_total': sum(1 for p in plans if p.get('status') in {'APPROVED', 'RECEIVED'})}


def conversation_section(days: int = 14) -> dict[str, Any]:
    path = _private_dir() / 'conversations.sqlite'
    out = {'conversations': 0, 'messages': 0, 'summaries': 0, 'thumbs_up': 0, 'thumbs_down': 0}
    if not path.exists():
        return out
    start = _since(days).isoformat()
    try:
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as con:
            out['conversations'] = con.execute('SELECT COUNT(*) FROM conversations WHERE substr(updated_at,1,10) >= ?', (start,)).fetchone()[0]
            out['messages'] = con.execute('SELECT COUNT(*) FROM chat_messages WHERE substr(created_at,1,10) >= ?', (start,)).fetchone()[0]
            out['summaries'] = con.execute('SELECT COUNT(*) FROM conversation_summaries WHERE substr(updated_at,1,10) >= ?', (start,)).fetchone()[0]
            for rating, n in con.execute('SELECT rating, COUNT(*) FROM chat_feedback WHERE substr(updated_at,1,10) >= ? GROUP BY rating', (start,)):
                out['thumbs_up' if rating > 0 else 'thumbs_down'] += n
    except sqlite3.Error:
        pass
    out['satisfaction_pct'] = _pct(out['thumbs_up'], out['thumbs_up'] + out['thumbs_down'])
    return out


# --- offline benchmarks ---------------------------------------------------------------------------------------

def retrieval_benchmark() -> dict[str, Any] | None:
    from src.agent.multi_agent.repo_docs_agent import SOP_RANKER_PATH
    try:
        ev = json.loads(Path(SOP_RANKER_PATH).read_text(encoding='utf-8'))['evaluation']
    except (OSError, KeyError, ValueError):
        return None

    def row(name, m, note):
        mean = {k: (v[0] if isinstance(v, list) else v) for k, v in m.items()}
        return {'method': name, 'Hit@1': mean.get('Hit@1'), 'Hit@3': mean.get('Hit@3'), 'MRR': mean.get('MRR'),
                'Từ chối đúng': mean.get('Rejection'), 'Ghi chú': note}
    rows = []
    base = ev.get('baselines_all_100') or {}
    if base:
        rows += [row('BM25', base['bm25'], 'từ khóa, không ngưỡng từ chối'),
                 row('Vector (Gemini embedding)', base['vector'], 'ngữ nghĩa, không ngưỡng'),
                 row('RRF (BM25 + vector)', base['rrf'], 'hybrid chuẩn, không ngưỡng')]
    rows.append(row('Chấm tay (heuristic)', ev['heuristic']['heldout'], '70 câu mới'))
    for key, name in (('learned_cv5x10', 'Learning-to-rank (từ vựng)'), ('learned_semantic_cv5x10', 'Learning-to-rank + embedding')):
        if key in ev:
            rows.append(row(name, ev[key], '5-fold CV ×10, có ngưỡng từ chối'))
    return {'questions': sum(ev.get('questions', {}).values()), 'rows': rows}


def scorecard_path() -> Path:
    return _private_dir() / 'scorecard.json'


def scorecard() -> dict[str, Any] | None:
    try:
        report = json.loads(scorecard_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    report.pop('cases', None)
    report['ran_at'] = datetime.fromtimestamp(scorecard_path().stat().st_mtime, llm_usage.TZ).isoformat(timespec='minutes')
    return report


def run_scorecard(live: bool = False) -> dict[str, Any]:
    """Run the 50-case behavioural regression suite (offline rules by default; live uses the API)."""
    import sys
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from experiments.agent_scorecard import run_scorecard as run
    private = _private_dir()
    report = run(dataset=str(root / 'experiments' / 'agent_golden_v2.jsonl'), live=live,
                 output=str(scorecard_path()), verbose=False, eval_dir=str(private / 'evaluation'))
    return report


def dashboard(days: int = 14) -> dict[str, Any]:
    return {'generated_at': datetime.now(llm_usage.TZ).isoformat(timespec='seconds'), 'days': days,
            'agent': agent_section(days), 'usage': usage_section(days), 'ocr': ocr_section(days),
            'plans': plans_section(days), 'conversations': conversation_section(days),
            'retrieval': retrieval_benchmark(), 'scorecard': scorecard()}



def redteam(agent) -> dict[str, Any]:
    """Run the guardrail red-team set (no model call, a few ms): attacks blocked, shop questions let through."""
    root = Path(__file__).resolve().parents[2]
    cases = json.loads((root / 'experiments' / 'guardrail_redteam.json').read_text(encoding='utf-8'))
    rows = []
    for query, category in cases['attacks'].items():
        hit = agent.tool_check_guardrail(query, 'redteam')
        got = (hit or {}).get('raw_result', {}).get('category')
        rows.append({'Câu thử': query, 'Loại': 'Tấn công', 'Kỳ vọng': GUARD_VI.get(category, category),
                     'Kết quả': GUARD_VI.get(got, got) if got else 'Lọt qua', 'Đạt': got == category})
    for query in cases['benign']:
        hit = agent.tool_check_guardrail(query, 'redteam')
        rows.append({'Câu thử': query, 'Loại': 'Câu hỏi thường', 'Kỳ vọng': 'Cho qua',
                     'Kết quả': 'Cho qua' if not hit else 'Chặn nhầm', 'Đạt': not hit})
    attacks = [r for r in rows if r['Loại'] == 'Tấn công']
    benign = [r for r in rows if r['Loại'] != 'Tấn công']
    return {'blocked_pct': _pct(sum(r['Đạt'] for r in attacks), len(attacks)),
            'false_block_pct': _pct(sum(not r['Đạt'] for r in benign), len(benign)),
            'attacks': len(attacks), 'benign': len(benign), 'rows': rows}
