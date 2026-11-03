"""Keep Gemini 3 tool calling working through the OpenAI-compatible endpoint.

Gemini 3 models attach a ``thought_signature`` to every function call they make
(``tool_calls[i].extra_content.google.thought_signature``) and reject the next request with
HTTP 400 unless the signature is sent back on that assistant message. LangChain's OpenAI client
drops unknown fields, so without this layer every turn that used a tool failed on the follow-up
call — and every later turn too, because the tool call stays in the conversation history.

This transport sits under the OpenAI client: it remembers signatures from responses (by tool-call
id, in memory only) and puts them back on outgoing assistant messages. Calls whose signature is no
longer known (server restart, old history) get Google's documented placeholder
``skip_thought_signature_validator``. Nothing else in the request or response is changed.
"""
from __future__ import annotations

import json
import threading
from collections import OrderedDict

import httpx

PLACEHOLDER = 'skip_thought_signature_validator'
_MAX_REMEMBERED = 2000


class SignatureMemory:
    def __init__(self):
        self._items: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()

    def remember(self, call_id, extra):
        with self._lock:
            self._items[call_id] = extra
            self._items.move_to_end(call_id)
            while len(self._items) > _MAX_REMEMBERED:
                self._items.popitem(last=False)

    def get(self, call_id):
        with self._lock:
            return self._items.get(call_id)


MEMORY = SignatureMemory()


def add_signatures(payload: dict, memory: SignatureMemory = MEMORY) -> bool:
    changed = False
    for message in payload.get('messages') or []:
        if not isinstance(message, dict) or message.get('role') != 'assistant':
            continue
        for call in message.get('tool_calls') or []:
            if not isinstance(call, dict) or call.get('extra_content'):
                continue
            known = memory.get(call.get('id'))
            # Only the first call of a parallel batch carries a signature; the placeholder is accepted on any.
            call['extra_content'] = known or {'google': {'thought_signature': PLACEHOLDER}}
            changed = True
    return changed


def remember_signatures(body: dict, memory: SignatureMemory = MEMORY) -> None:
    for choice in body.get('choices') or []:
        for call in ((choice or {}).get('message') or {}).get('tool_calls') or []:
            extra = (call or {}).get('extra_content')
            if call.get('id') and isinstance(extra, dict) and extra.get('google', {}).get('thought_signature'):
                memory.remember(call['id'], extra)


def _rewrite(request: httpx.Request) -> httpx.Request:
    if request.method != 'POST' or not request.url.path.endswith('/chat/completions'):
        return request
    try:
        payload = json.loads(request.content)
    except (ValueError, TypeError):
        return request
    if not add_signatures(payload):
        return request
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'content-length'}
    return httpx.Request(request.method, request.url, headers=headers, json=payload, extensions=request.extensions)


def _inspect(response: httpx.Response) -> None:
    if response.status_code != 200 or 'json' not in response.headers.get('content-type', ''):
        return
    try:
        remember_signatures(json.loads(response.content))
    except (ValueError, TypeError, AttributeError):
        return


class SignatureTransport(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport | None = None):
        self.inner = inner or httpx.HTTPTransport()

    def handle_request(self, request):
        response = self.inner.handle_request(_rewrite(request))
        response.read()
        _inspect(response)
        return response

    def close(self):
        self.inner.close()


class AsyncSignatureTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: httpx.AsyncBaseTransport | None = None):
        self.inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        response = await self.inner.handle_async_request(_rewrite(request))
        await response.aread()
        _inspect(response)
        return response

    async def aclose(self):
        await self.inner.aclose()


def http_clients(timeout: float):
    return (httpx.Client(transport=SignatureTransport(), timeout=timeout),
            httpx.AsyncClient(transport=AsyncSignatureTransport(), timeout=timeout))
