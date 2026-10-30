"""Opt-in live API check of forecasts and a preparation draft; never approves."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agent.config import AgentSettings
from src.agent.mixue_agent import MixueOperationsAgent

settings = AgentSettings.from_env()
assert settings.llm_enabled and settings.allow_external_transfer, 'API/data transfer must be explicitly enabled.'
agent = MixueOperationsAgent(settings=settings)
reports = []
try:
    for question in ['Dự báo số ly hôm nay', 'Lập kế hoạch sơ chế hôm nay, tạm lấy 1 kg trân châu khô cho 2 kg thành phẩm']:
        response = agent.process_query(question, 'MANAGER', 'Quang', user_id='weather-agent-check')
        state = agent._runtime().graph.get_state({'configurable': {'thread_id': response['thread_id']}}).values
        business = [row for row in state.get('results', []) if row['tool'] in {'forecast_demand', 'optimize_topping_prep'}]
        report = {'query': question, 'status': response.get('raw_result', {}).get('status'),
                  'tools': response['tool_called'], 'text': response['text'],
                  'weather_status': business[-1]['result'].get('forecast_context', {}).get('status') if business else None,
                  'trace': response.get('trace', [])}
        reports.append(report)
        print(json.dumps({**report, 'text': report['text'][:700]}, ensure_ascii=True), flush=True)
        assert report['status'] == 'SUCCESS', 'Live model did not complete the requested operation.'
        assert business, 'The answer has no forecast/preparation evidence.'
    assert all(plan.get('status') != 'APPROVED' for plan in agent.draft_plans.values())
finally:
    output = Path('data/weather_private/agent-check.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    agent.close()
