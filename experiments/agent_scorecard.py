"""Repeatable behavioral evaluation; live API use is explicit, never a silent default."""
import argparse
import hashlib
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from src.agent.config import AgentSettings
from src.agent.mixue_agent import MixueOperationsAgent


def score_response(case, response):
    tools = set(response.get('tool_called', '').split(','))
    status = response.get('raw_result', {}).get('status', response.get('status', 'SUCCESS'))
    text = response.get('text', '').casefold()
    checks = {
        'status': status in case.get('statuses', ['SUCCESS']),
        'tools': all(bool(tools & set(group)) for group in case.get('tool_groups', [])),
        'required_text': all(word.casefold() in text for word in case.get('required_text', [])),
        'forbidden_text': all(word.casefold() not in text for word in case.get('forbidden_text', [])),
        'evidence': not case.get('evidence_required') or bool(response.get('evidence_refs')),
        'length': not case.get('max_chars') or len(response.get('text', '')) <= case['max_chars'],
    }
    return {'passed': all(checks.values()), 'checks': checks, 'status': status}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--dataset', default='experiments/agent_golden_v2.jsonl')
    parser.add_argument('--output', default='data/agent_private/scorecard.json')
    args = parser.parse_args()
    source = Path(args.dataset).read_bytes()
    cases = [json.loads(line) for line in source.decode('utf-8').splitlines() if line.strip()]
    settings = AgentSettings.from_env()
    if not args.live:
        settings = settings.model_copy(update={'llm_enabled': False})
    elif not settings.llm_enabled or not settings.allow_external_transfer:
        raise SystemExit('Live evaluation requires enabled API and existing external-transfer permission.')
    # Keep evaluation conversations separate from human account histories.
    settings = settings.model_copy(update={'checkpoint_path': 'data/agent_private/evaluation/checkpoints.sqlite',
                                           'audit_path': 'data/agent_private/evaluation/audit.jsonl'})
    agent = MixueOperationsAgent(settings=settings)
    rows, categories = [], defaultdict(list)
    try:
        for case in cases[:args.limit]:
            started = time.monotonic()
            agent.new_conversation(case.get('role', 'MANAGER'), 'Người kiểm thử', user_id='evaluation-' + case['id'])
            responses = []
            turn_results = []
            turn_queries = case.get('turns', [case['query']])
            for turn_idx, query in enumerate(turn_queries):
                resp = agent.process_query(
                    query, case.get('role', 'MANAGER'), 'Người kiểm thử',
                    user_id='evaluation-' + case['id']
                )
                responses.append(resp)
                if turn_idx < len(turn_queries) - 1:
                    t_status = resp.get('raw_result', {}).get('status', resp.get('status', 'SUCCESS'))
                    turn_ok = t_status not in ('MODEL_ERROR', 'INTERNAL_ERROR', 'UNHANDLED_EXCEPTION')
                    turn_results.append({'turn': turn_idx + 1, 'query': query, 'passed': turn_ok, 'status': t_status})
                else:
                    final_score = score_response(case, resp)
                    turn_results.append({'turn': turn_idx + 1, 'query': query, 'passed': final_score['passed'], 'status': final_score['status']})

            all_turns_passed = all(t['passed'] for t in turn_results)
            result = final_score
            result['passed'] = bool(result['passed'] and all_turns_passed)
            result['turn_results'] = turn_results

            traces = [event for response in responses for event in response.get('trace', [])]
            row = {'id': case['id'], 'category': case['category'], **result,
                   'turns_count': len(turn_queries),
                   'latency_seconds': round(time.monotonic() - started, 3),
                   'input_tokens': sum(event.get('input_tokens', 0) for event in traces),
                   'output_tokens': sum(event.get('output_tokens', 0) for event in traces),
                   'models': sorted({event['model'] for event in traces if event.get('model')}),
                   'tools': responses[-1].get('tool_called'), 'execution_mode': responses[-1].get('execution_mode')}
            rows.append(row)
            categories[case['category']].append(result['passed'])
            print(f"{case['id']}: {'PASS' if result['passed'] else 'FAIL'}", flush=True)
    finally:
        agent.close()
    ds_name = Path(args.dataset).stem
    report = {'mode': 'live_api' if args.live else 'offline_rules',
              'model_name': settings.model_name if args.live else 'offline_rule_engine',
              'prompt_version': 'v2.0_pilot_phase3',
              'dataset_name': ds_name,
              'dataset_sha256': hashlib.sha256(source).hexdigest(),
              'dataset_review': 'Authored regression cases; pending independent review by store users.',
              'total': len(rows), 'passed': sum(row['passed'] for row in rows),
              'pass_rate_pct': round((sum(row['passed'] for row in rows) / len(rows) * 100), 2) if rows else 0.0,
              'median_latency_seconds': statistics.median(row['latency_seconds'] for row in rows) if rows else None,
              'total_input_tokens': sum(r.get('input_tokens', 0) for r in rows),
              'total_output_tokens': sum(r.get('output_tokens', 0) for r in rows),
              'categories': {name: {'passed': sum(values), 'total': len(values)} for name, values in categories.items()},
              'cases': rows}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{report['passed']}/{report['total']} passed ({report['mode']}). Report: {path}")


if __name__ == '__main__':
    main()
