"""Semantic vectors for SOP lookups (Gemini embedding API).

* Document vectors are built once, offline (scripts/build_sop_embeddings.py), for the SOP / recipe / rule
  chunks only. Day-by-day log rows (sales, purchases, stock counts, waste) are never sent.
* At question time the question alone is embedded (one small API call, cached). Any problem — AI disabled,
  external transfer not allowed, no key, quota, timeout — returns None and the search runs on the lexical
  signals only. Nothing here can make a lookup fail.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
API = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents'
DIM = 768


def embed_model() -> str:
    return os.environ.get('SOP_EMBED_MODEL') or 'gemini-embedding-001'


def vectors_path(model: str | None = None) -> Path:
    return ROOT / 'data' / 'sop_embeddings' / f'{model or embed_model()}.npz'


def embed_texts(texts: list[str], task: str, api_key: str, model: str | None = None, timeout: float = 30.0,
                titles: list[str] | None = None) -> np.ndarray:
    """Unit-length vectors for `texts`. task: RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY. Raises on any error."""
    import httpx
    model = model or embed_model()
    out = []
    for start in range(0, len(texts), 100):
        requests = []
        for i, text in enumerate(texts[start:start + 100]):
            req: dict[str, Any] = {'model': f'models/{model}', 'content': {'parts': [{'text': text}]},
                                   'taskType': task, 'outputDimensionality': DIM}
            if titles and task == 'RETRIEVAL_DOCUMENT':
                req['title'] = titles[start + i]
            requests.append(req)
        resp = httpx.post(API.format(model=model), json={'requests': requests}, timeout=timeout,
                          headers={'x-goog-api-key': api_key.strip()})
        if resp.status_code != 200:
            raise RuntimeError(f'embedding HTTP {resp.status_code}')
        out += [e['values'] for e in resp.json()['embeddings']]
    v = np.asarray(out, dtype=np.float32)
    v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)  # truncated dimensions are not unit length
    return v


_DOCS: dict[str, Any] = {}
_QUERIES: dict[str, np.ndarray] = {}
_LOCK = threading.Lock()
_COOLDOWN_UNTIL = [0.0]


def document_vectors() -> dict[str, np.ndarray] | None:
    """chunk_id -> vector for the shipped corpus, or None when no vectors were built for this model."""
    model = embed_model()
    if model not in _DOCS:
        try:
            data = np.load(vectors_path(model))
            vecs = data['vectors'].astype(np.float32)
            _DOCS[model] = dict(zip([str(i) for i in data['ids']], vecs))
        except (OSError, KeyError, ValueError):
            _DOCS[model] = None
    return _DOCS[model]


def query_vector(query: str, settings=None) -> np.ndarray | None:
    """The question's vector, or None (semantic signal unavailable: search falls back to lexical)."""
    if str(os.environ.get('SOP_DENSE', '1')).strip().lower() in {'0', 'false', 'off', 'no'}:
        return None
    if document_vectors() is None or time.monotonic() < _COOLDOWN_UNTIL[0]:
        return None
    key = query.strip().lower()
    if key in _QUERIES:
        return _QUERIES[key]
    try:
        from src.agent.config import AgentSettings
        cfg = settings or AgentSettings.from_env()
        if not (cfg.llm_enabled and cfg.allow_external_transfer and cfg.api_key
                and cfg.provider in {'gemini', 'google', 'google_genai'}):
            return None
        vec = embed_texts([query], 'RETRIEVAL_QUERY', cfg.api_key, timeout=float(os.environ.get('SOP_EMBED_TIMEOUT') or 4))[0]
    except Exception as exc:  # noqa: BLE001 - any failure means "no semantic signal this time"
        logger.warning('SOP query embedding unavailable (%s); lexical ranking only', type(exc).__name__)
        _COOLDOWN_UNTIL[0] = time.monotonic() + 60
        return None
    with _LOCK:
        if len(_QUERIES) > 512:
            _QUERIES.clear()
        _QUERIES[key] = vec
    return vec
