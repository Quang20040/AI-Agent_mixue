"""Red-team set for the chat guardrail (experiments/guardrail_redteam.json): attacks are blocked with the
right category, everyday shop questions pass. The admin AI dashboard runs the same set."""
import json
from pathlib import Path

import pytest

from src.agent.config import AgentSettings
from src.agent.mixue_agent import MixueOperationsAgent

CASES = json.loads((Path(__file__).resolve().parents[1] / 'experiments' / 'guardrail_redteam.json').read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def agent():
    a = MixueOperationsAgent(settings=AgentSettings.from_env().model_copy(update={'llm_enabled': False}))
    yield a
    a.close()


@pytest.mark.parametrize('query,category', CASES['attacks'].items())
def test_attacks_are_blocked(agent, query, category):
    blocked = agent.tool_check_guardrail(query, 'x')
    assert blocked and blocked['raw_result']['category'] == category


@pytest.mark.parametrize('query', CASES['benign'])
def test_shop_questions_pass(agent, query):
    assert agent.tool_check_guardrail(query, 'x') is None
