"""Token and cost log for every AI call (chat, photo reading, SOP embeddings).

One row per call in a small SQLite file (data/agent_private/llm_usage.db, or LLM_USAGE_DB). Prices are
list prices in USD per 1M tokens, as published by Google for the paid tier; on the free tier nothing is
billed, the cost column then shows what the same usage would cost once billing is on. Logging never raises.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
TZ = ZoneInfo('Asia/Ho_Chi_Minh')

# USD per 1M tokens (input, output). Thinking tokens are billed as output. Checked 2026-11-07.
PRICES: dict[str, tuple[float, float]] = {
    'gemini-3.5-flash': (1.50, 9.00),
    'gemini-3.8-flash': (0.75, 3.75),        # promotional until 2026-12-31, then 1.50 / 7.50
    'gemini-3.5-flash-lite': (0.30, 2.50),
    'gemini-embedding-001': (0.15, 0.0),
}
PRICES_FROM_2027 = {'gemini-3.8-flash': (1.50, 7.50)}

_LOCK = threading.Lock()
_READY: set[str] = set()


def db_path() -> Path:
    return Path(os.environ.get('LLM_USAGE_DB') or ROOT / 'data' / 'agent_private' / 'llm_usage.db')


def price(model: str, on: date | None = None) -> tuple[float, float] | None:
    key = next((k for k in sorted(PRICES, key=len, reverse=True) if (model or '').startswith(k)), None)
    if key is None:
        return None
    if (on or date.today()) >= date(2027, 1, 1) and key in PRICES_FROM_2027:
        return PRICES_FROM_2027[key]
    return PRICES[key]


def cost_usd(model: str, input_tokens: int, output_tokens: int, on: date | None = None) -> float | None:
    p = price(model, on)
    if p is None:
        return None
    return input_tokens / 1e6 * p[0] + output_tokens / 1e6 * p[1]


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    if str(path) not in _READY:
        con.execute('''CREATE TABLE IF NOT EXISTS llm_usage (
            ts TEXT NOT NULL, day TEXT NOT NULL, feature TEXT NOT NULL, model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, thinking_tokens INTEGER NOT NULL,
            ok INTEGER NOT NULL, seconds REAL, estimated INTEGER NOT NULL DEFAULT 0)''')
        con.execute('CREATE INDEX IF NOT EXISTS llm_usage_day ON llm_usage(day)')
        _READY.add(str(path))
    return con


def record(feature: str, model: str, input_tokens: int = 0, output_tokens: int = 0, thinking_tokens: int = 0,
           ok: bool = True, seconds: float | None = None, estimated: bool = False) -> None:
    """Log one AI call. feature: chat | ocr | embedding. output_tokens includes thinking tokens."""
    if str(os.environ.get('LLM_USAGE_LOG', '1')).strip().lower() in {'0', 'false', 'off', 'no'}:
        return
    try:
        now = datetime.now(TZ)
        with _LOCK, _connect() as con:
            con.execute('INSERT INTO llm_usage VALUES (?,?,?,?,?,?,?,?,?,?)', (
                now.isoformat(timespec='seconds'), now.date().isoformat(), feature, (model or 'unknown')[:80],
                int(input_tokens or 0), int(output_tokens or 0), int(thinking_tokens or 0), int(bool(ok)),
                None if seconds is None else round(float(seconds), 2), int(bool(estimated))))
    except Exception as exc:  # noqa: BLE001 - usage logging must never break a request
        logger.warning('LLM usage not logged: %s', exc)


def usage_from_metadata(meta: Any) -> tuple[int, int, int]:
    """(input, output incl. thinking, thinking) from a LangChain usage_metadata dict or a Gemini usageMetadata."""
    meta = meta or {}
    if 'promptTokenCount' in meta or 'candidatesTokenCount' in meta:
        thinking = int(meta.get('thoughtsTokenCount') or 0)
        return int(meta.get('promptTokenCount') or 0), int(meta.get('candidatesTokenCount') or 0) + thinking, thinking
    details = meta.get('output_token_details') or {}
    return int(meta.get('input_tokens') or 0), int(meta.get('output_tokens') or 0), int(details.get('reasoning') or 0)


def summary(days: int = 7, today: date | None = None) -> list[dict[str, Any]]:
    """Per day, feature and model: calls, failures, tokens, cost (USD, None if the model has no listed price)."""
    today = today or datetime.now(TZ).date()
    start = (today - timedelta(days=days - 1)).isoformat()
    try:
        with _LOCK, _connect() as con:
            rows = con.execute('''SELECT day, feature, model, COUNT(*), SUM(1 - ok), SUM(input_tokens),
                                         SUM(output_tokens), SUM(thinking_tokens), MAX(estimated)
                                  FROM llm_usage WHERE day >= ? GROUP BY day, feature, model
                                  ORDER BY day DESC, feature, model''', (start,)).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning('LLM usage unreadable: %s', exc)
        return []
    out = []
    for day, feature, model, calls, failed, tin, tout, think, est in rows:
        out.append({'day': day, 'feature': feature, 'model': model, 'calls': calls, 'failed': failed or 0,
                    'input_tokens': tin or 0, 'output_tokens': tout or 0, 'thinking_tokens': think or 0,
                    'estimated': bool(est), 'cost_usd': cost_usd(model, tin or 0, tout or 0, date.fromisoformat(day))})
    return out
