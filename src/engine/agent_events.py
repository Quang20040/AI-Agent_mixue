"""One row per agent turn, for the AI engineering dashboard.

Stores what the agent *did* (guardrail result, tools called and their status/latency, permission denials,
approval steps, model calls, tokens, latency) — never the question text or the answer, so the log holds no
business data or personal data. Lives in the private usage database next to ``llm_usage``.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from src.engine import llm_usage

logger = logging.getLogger(__name__)
_READY: set[str] = set()


def _connect():
    con = llm_usage._connect()
    key = str(llm_usage.db_path())
    if key not in _READY:
        con.execute('''CREATE TABLE IF NOT EXISTS agent_turns (
            ts TEXT NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL, role TEXT NOT NULL,
            mode TEXT NOT NULL, status TEXT NOT NULL, elapsed_ms INTEGER NOT NULL,
            guard TEXT NOT NULL, guard_category TEXT NOT NULL,
            model_calls INTEGER NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
            evidence INTEGER NOT NULL, pending_approval INTEGER NOT NULL, trace_json TEXT NOT NULL)''')
        con.execute('CREATE INDEX IF NOT EXISTS agent_turns_day ON agent_turns(day)')
        _READY.add(key)
    return con


def _slim(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the structure of the trace, drop free text (tool arguments, result summaries)."""
    keep = {'node', 'result', 'category', 'reason', 'tool', 'status', 'duration_ms', 'sources', 'tool_calls',
            'requested', 'model', 'input_tokens', 'output_tokens', 'role', 'forced_tool', 'calls'}
    out = []
    for event in trace or []:
        if not isinstance(event, dict):
            continue
        item = {k: v for k, v in event.items() if k in keep}
        if isinstance(item.get('calls'), list):
            item['calls'] = [{'name': c.get('name'), 'effect': c.get('effect')} for c in item['calls'] if isinstance(c, dict)]
        out.append(item)
    return out


def record_turn(kind: str, role: str, response: dict[str, Any], elapsed_ms: float) -> None:
    """kind: chat | approval. Never raises."""
    try:
        trace = _slim(response.get('trace') or [])
        guard = next((e for e in trace if e.get('node') == 'guard'), {})
        models = [e for e in trace if e.get('node') == 'model']
        now = datetime.now(llm_usage.TZ)
        status = str((response.get('raw_result') or {}).get('status') or response.get('status') or 'SUCCESS')
        with llm_usage._LOCK, _connect() as con:
            con.execute('INSERT INTO agent_turns VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                now.isoformat(timespec='seconds'), now.date().isoformat(), kind, str(role or '')[:20],
                str(response.get('execution_mode') or 'unknown')[:30], status[:40], int(elapsed_ms),
                str(guard.get('result') or ('router' if any(e.get('node') == 'router' for e in trace) else 'none'))[:20],
                str(guard.get('category') or '')[:60], len(models),
                sum(int(e.get('input_tokens') or 0) for e in models), sum(int(e.get('output_tokens') or 0) for e in models),
                len(response.get('evidence_refs') or []), int(bool(response.get('pending_approval'))),
                json.dumps(trace, ensure_ascii=False)[:20000]))
    except Exception as exc:  # noqa: BLE001 - logging must never break a chat turn
        logger.warning('agent turn not logged: %s', exc)


def turns(days: int = 14, today: date | None = None) -> list[dict[str, Any]]:
    today = today or datetime.now(llm_usage.TZ).date()
    start = (today - timedelta(days=days - 1)).isoformat()
    try:
        with llm_usage._LOCK, _connect() as con:
            con.row_factory = lambda cur, row: {d[0]: v for d, v in zip(cur.description, row)}
            rows = con.execute('SELECT * FROM agent_turns WHERE day >= ? ORDER BY ts', (start,)).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning('agent turns unreadable: %s', exc)
        return []
    for row in rows:
        row['trace'] = json.loads(row.pop('trace_json') or '[]')
    return rows
