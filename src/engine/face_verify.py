"""Compare a check-in selfie with the employee's approved reference photo using Gemini vision.

The model is asked only "same person or not", plus whether a face is clearly visible and whether the
selfie looks like a photo of a screen / printed photo (a basic anti-cheat hint, not real liveness).
Images are shrunk to 512 px before sending. If AI is off or unavailable the result is UNAVAILABLE and the
check-in goes to the manager to look at — nothing is decided without a person when the AI cannot decide.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)
MATCH_THRESHOLD = 0.8
FACE_MODEL = 'gemini-3.5-flash'

PROMPT = """Bạn so sánh hai ảnh để chấm công tại cửa hàng.
Ảnh 1: ảnh mẫu khuôn mặt nhân viên (đã được quản lý duyệt). Ảnh 2: ảnh vừa chụp khi chấm công.
Trả lời JSON đúng schema:
- face_visible: ảnh 2 có thấy rõ một khuôn mặt người không.
- same_person: hai ảnh có phải CÙNG MỘT NGƯỜI không (bỏ qua khác biệt ánh sáng, góc, khẩu trang kéo xuống, tóc, kính).
- confidence: độ chắc chắn 0..1 cho kết luận same_person.
- looks_like_screen_or_print: ảnh 2 có vẻ chụp lại màn hình điện thoại/máy tính hoặc ảnh in không.
- reason: một câu ngắn tiếng Việt giải thích.
Không đoán danh tính, không mô tả đặc điểm nhạy cảm."""

SCHEMA = {'type': 'object', 'properties': {
    'face_visible': {'type': 'boolean'}, 'same_person': {'type': 'boolean'},
    'confidence': {'type': 'number'}, 'looks_like_screen_or_print': {'type': 'boolean'},
    'reason': {'type': 'string'}}, 'required': ['face_visible', 'same_person', 'confidence', 'looks_like_screen_or_print', 'reason']}


def shrink(data: bytes, size: int = 512) -> bytes:
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB')
    img.thumbnail((size, size))
    out = io.BytesIO()
    img.save(out, 'JPEG', quality=85)
    return out.getvalue()


def _settings():
    from src.agent.config import AgentSettings
    return AgentSettings.from_env()


def available() -> bool:
    cfg = _settings()
    return bool(cfg.llm_enabled and cfg.allow_external_transfer and cfg.api_key.get_secret_value())


def compare(reference: bytes, selfie: bytes) -> dict[str, Any]:
    """{'result': MATCH | NO_MATCH | UNSURE | NO_FACE | SPOOF | UNAVAILABLE, 'confidence', 'reason'}."""
    if not available():
        return {'result': 'UNAVAILABLE', 'confidence': None, 'reason': 'AI so khuôn mặt chưa bật — Quản lý xem ảnh.'}
    import httpx
    cfg = _settings()
    import os
    model = os.environ.get('FACE_MODEL') or FACE_MODEL
    body = {'contents': [{'role': 'user', 'parts': [
        {'text': PROMPT},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(shrink(reference)).decode()}},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(shrink(selfie)).decode()}}]}],
        'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': SCHEMA, 'temperature': 0,
                             'maxOutputTokens': 400}}
    started = time.monotonic()
    try:
        r = httpx.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', json=body,
                       timeout=30, headers={'x-goog-api-key': cfg.api_key.get_secret_value()})
        r.raise_for_status()
        data = r.json()
        text = ''.join(p.get('text', '') for p in data['candidates'][0]['content']['parts'] if not p.get('thought'))
        answer = json.loads(text)
    except Exception as exc:  # noqa: BLE001 - any failure → a person decides
        logger.warning('face compare failed: %s', exc)
        return {'result': 'UNAVAILABLE', 'confidence': None, 'reason': 'Không gọi được AI so khuôn mặt — Quản lý xem ảnh.'}
    try:
        from src.engine import llm_usage
        tin, tout, think = llm_usage.usage_from_metadata(data.get('usageMetadata'))
        llm_usage.record('face', model, tin, tout, think, ok=True, seconds=time.monotonic() - started)
    except Exception:  # noqa: BLE001
        pass
    return classify(answer)


def classify(answer: dict[str, Any]) -> dict[str, Any]:
    conf = max(0.0, min(1.0, float(answer.get('confidence') or 0)))
    reason = str(answer.get('reason') or '')[:300]
    if not answer.get('face_visible'):
        return {'result': 'NO_FACE', 'confidence': conf, 'reason': reason or 'Không thấy rõ khuôn mặt.'}
    if answer.get('looks_like_screen_or_print'):
        return {'result': 'SPOOF', 'confidence': conf, 'reason': reason or 'Ảnh có vẻ chụp lại màn hình / ảnh in.'}
    if answer.get('same_person') and conf >= MATCH_THRESHOLD:
        return {'result': 'MATCH', 'confidence': conf, 'reason': reason}
    if not answer.get('same_person') and conf >= MATCH_THRESHOLD:
        return {'result': 'NO_MATCH', 'confidence': conf, 'reason': reason}
    return {'result': 'UNSURE', 'confidence': conf, 'reason': reason}
