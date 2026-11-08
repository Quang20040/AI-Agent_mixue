"""AI review of a check-in / check-out photo (Gemini vision). No face recognition: the model only says
whether the photo is a real, freshly taken picture of a person — not a photo of a screen or printed
picture, not empty. OK → counted automatically; anything else (or AI off) → the manager looks at it."""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)
MODEL = 'gemini-3.5-flash'

PROMPT = """Đây là ảnh nhân viên vừa tự chụp bằng điện thoại để chấm công ở cửa hàng đồ uống.
Kiểm tra và trả JSON đúng schema:
- person_visible: có thấy rõ một người thật (mặt hoặc nửa người) trong ảnh không.
- looks_like_screen_or_print: ảnh có vẻ là chụp lại màn hình điện thoại / máy tính hoặc ảnh in không.
- indoor_shop_like: bối cảnh có giống trong cửa hàng / quầy pha chế không (chỉ để tham khảo).
- reason: một câu ngắn tiếng Việt.
Không nhận diện danh tính, không mô tả đặc điểm cá nhân nhạy cảm."""

SCHEMA = {'type': 'object', 'properties': {
    'person_visible': {'type': 'boolean'}, 'looks_like_screen_or_print': {'type': 'boolean'},
    'indoor_shop_like': {'type': 'boolean'}, 'reason': {'type': 'string'}},
    'required': ['person_visible', 'looks_like_screen_or_print', 'indoor_shop_like', 'reason']}


def shrink(data: bytes, size: int = 640) -> bytes:
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB')
    img.thumbnail((size, size))
    out = io.BytesIO()
    img.save(out, 'JPEG', quality=85)
    return out.getvalue()


def available() -> bool:
    from src.agent.config import AgentSettings
    cfg = AgentSettings.from_env()
    return bool(cfg.llm_enabled and cfg.allow_external_transfer and cfg.api_key.get_secret_value())


def classify(answer: dict[str, Any]) -> dict[str, Any]:
    reason = str(answer.get('reason') or '')[:300]
    if answer.get('looks_like_screen_or_print'):
        return {'result': 'SCREEN', 'reason': reason or 'Ảnh có vẻ chụp lại màn hình / ảnh in.'}
    if not answer.get('person_visible'):
        return {'result': 'NO_PERSON', 'reason': reason or 'Không thấy người trong ảnh.'}
    return {'result': 'OK', 'reason': reason}


def review(photo: bytes) -> dict[str, Any]:
    """{'result': OK | NO_PERSON | SCREEN | UNAVAILABLE, 'reason'}."""
    if not available():
        return {'result': 'UNAVAILABLE', 'reason': 'AI chưa bật — Quản lý xem ảnh.'}
    import httpx
    from src.agent.config import AgentSettings
    cfg = AgentSettings.from_env()
    model = os.environ.get('CHECKIN_PHOTO_MODEL') or MODEL
    body = {'contents': [{'role': 'user', 'parts': [
        {'text': PROMPT}, {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(shrink(photo, 512)).decode()}}]}],
        'generationConfig': {'responseMimeType': 'application/json', 'responseSchema': SCHEMA, 'temperature': 0, 'maxOutputTokens': 300}}
    started = time.monotonic()
    try:
        r = httpx.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', json=body,
                       timeout=30, headers={'x-goog-api-key': cfg.api_key.get_secret_value()})
        r.raise_for_status()
        data = r.json()
        answer = json.loads(''.join(p.get('text', '') for p in data['candidates'][0]['content']['parts'] if not p.get('thought')))
    except Exception as exc:  # noqa: BLE001 - any failure → a person decides
        logger.warning('check-in photo review failed: %s', exc)
        return {'result': 'UNAVAILABLE', 'reason': 'Không gọi được AI — Quản lý xem ảnh.'}
    try:
        from src.engine import llm_usage
        tin, tout, think = llm_usage.usage_from_metadata(data.get('usageMetadata'))
        llm_usage.record('checkin', model, tin, tout, think, ok=True, seconds=time.monotonic() - started)
    except Exception:  # noqa: BLE001
        pass
    return classify(answer)
