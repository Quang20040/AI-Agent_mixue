"""Opt-in live smoke check. Never prints keys or provider error bodies."""
import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from langgraph.checkpoint.memory import InMemorySaver

from src.agent.config import AgentSettings
from src.agent.graph_runtime import Actor, AgentGraph
from src.agent.graph_tools import Arguments, ToolSpec
from src.agent.mixue_agent import MixueOperationsAgent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--with-store-data', action='store_true', help='Requires explicit permission to send store data to the provider.')
    args = parser.parse_args()
    settings = AgentSettings.from_env()
    if not settings.llm_enabled:
        raise SystemExit('LLM is disabled; no API request sent.')
    if args.with_store_data:
        if not settings.allow_external_transfer:
            raise SystemExit('Store data transfer is disabled. No request sent.')
        agent = MixueOperationsAgent(settings=settings)
        invoke = lambda query: agent.process_query(query, 'MANAGER', 'Quang', user_id='api-smoke-check')
        queries = ['hi', 'Cách nấu trân châu nguyên vị?', 'Ngày gần nhất có dữ liệu bán được bao nhiêu ly?']
    else:
        # No service connects to business data. This exercises the real graph/API
        # with a single synthetic arithmetic tool, regardless of the local data flag.
        class SyntheticService:
            db = SimpleNamespace(rollback=lambda: None)
            multi_agent = SimpleNamespace()
            def __getattr__(self, name):
                return lambda **kwargs: {'status': 'NO_DATA'}
            def tool_check_guardrail(self, query, name):
                return None
        class Operands(Arguments):
            a: int
            b: int
        agent = AgentGraph(SyntheticService(), settings.model_copy(update={'allow_external_transfer': True}),
                           checkpointer=InMemorySaver())
        agent.tools = {'add_numbers': ToolSpec('add_numbers', 'Cộng hai số nguyên. Dữ liệu giả kiểm thử.', Operands,
                                               lambda a, b: {'status': 'SUCCESS', 'sum': a + b})}
        invoke = lambda query: agent.invoke(query, Actor('synthetic', 'Bạn', 'MANAGER', deadline=time.monotonic()+120), 'synthetic')
        queries = ['hi', 'Tính tổng 2 + 3 bằng công cụ add_numbers rồi trả lời ngắn.']
    reports = []
    try:
        for query in queries:
            result = invoke(query)
            report = {'query': query, 'status': result.get('raw_result', {}).get('status'),
                      'mode': result.get('execution_mode'), 'tools': result.get('tool_called'),
                      'text': result['text'], 'evidence': result.get('evidence_refs', []),
                      'trace': result.get('trace', [])}
            reports.append(report)
            print(json.dumps(report, ensure_ascii=True), flush=True)
            if report['status'] in {'MODEL_ERROR', 'MODEL_CONFIGURATION_ERROR'}:
                break
        path = Path('output/agent-review/live-store-smoke.json' if args.with_store_data else 'output/agent-review/live-synthetic-smoke.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        agent.close()


if __name__ == '__main__':
    main()
