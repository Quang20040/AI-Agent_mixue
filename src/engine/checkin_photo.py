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

PROMPT = """Đây là ảnh nhân viên vừa tự chụp bằng điện thoại để chấm công ở cửa hàng đồ uống.
Dải chữ trắng nền tối ở cuối ảnh (giờ, ngày, ca, khoảng cách tới quán, tọa độ) do hệ thống tự in lên — đó KHÔNG phải
dấu hiệu chụp màn hình; chỉ xét phần ảnh phía trên.
Kiểm tra và trả JSON đúng schema:
- person_visible: có thấy rõ một người thật (mặt hoặc nửa người) trong ảnh không.
- looks_like_screen_or_print: ảnh có vẻ là chụp lại màn hình điện thoại / máy tính hoặc ảnh in không.
- indoor_shop_like: bối cảnh có giống trong cửa hàng / quầy pha chế không (chỉ để tham khảo).
- reason: một câu ngắn tiếng Việt.
Không nhận diện danh tính, không mô tả đặc điểm cá nhân nhạy cảm."""

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


def _ask(model: str, key: str, image: bytes) -> tuple[dict[str, Any], dict]:
    import httpx
    body = {'contents': [{'role': 'user', 'parts': [
        {'text': PROMPT + '\nChỉ trả về một object JSON với các khóa: person_visible, looks_like_screen_or_print, '
                          'indoor_shop_like, reason.'},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(image).decode()}}]}],
        # Thinking tokens share the output budget on Gemini 3: keep thinking minimal and the budget generous,
        # otherwise the answer is cut off before the JSON.
        'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0, 'maxOutputTokens': 2048}}
    if model.startswith('gemini-3'):
        body['generationConfig']['thinkingConfig'] = {'thinkingLevel': 'low'}
    r = httpx.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', json=body,
                   timeout=40, headers={'x-goog-api-key': key})
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code}: {r.text[:200]}')
    data = r.json()
    parts = ((data.get('candidates') or [{}])[0].get('content') or {}).get('parts', [])
    text = ''.join(p.get('text', '') for p in parts if not p.get('thought')).strip()
    if text.startswith('```'):
        text = text.strip('`').removeprefix('json').strip()
    return json.loads(text), data


def review(photo: bytes) -> dict[str, Any]:
    """{'result': OK | NO_PERSON | SCREEN | UNAVAILABLE, 'reason'}. Tries the same Gemini models as OCR."""
    if not available():
        return {'result': 'UNAVAILABLE', 'reason': 'AI chưa bật (LLM_ENABLED / ALLOW_EXTERNAL_DATA_TRANSFER / API key) — Quản lý xem ảnh.'}
    from src.agent.config import AgentSettings
    from src.engine import llm_usage
    from src.engine.vision_ocr import ocr_model_chain
    cfg = AgentSettings.from_env()
    chain = [os.environ['CHECKIN_PHOTO_MODEL']] if os.environ.get('CHECKIN_PHOTO_MODEL') else ocr_model_chain(cfg)
    image = shrink(photo, 512)
    last = ''
    for model in chain:
        started = time.monotonic()
        try:
            answer, data = _ask(model, cfg.api_key.get_secret_value(), image)
        except Exception as exc:  # noqa: BLE001 - try the next model, then hand over to the manager
            last = f'{model}: {exc}'[:200]
            logger.warning('check-in photo review failed on %s: %s', model, exc)
            try:
                llm_usage.record('checkin', model, ok=False, seconds=time.monotonic() - started)
            except Exception:  # noqa: BLE001
                pass
            continue
        try:
            tin, tout, think = llm_usage.usage_from_metadata(data.get('usageMetadata'))
            llm_usage.record('checkin', model, tin, tout, think, ok=True, seconds=time.monotonic() - started)
        except Exception:  # noqa: BLE001
            pass
        return classify(answer)
    return {'result': 'UNAVAILABLE', 'reason': f'Không gọi được AI ({last}) — Quản lý xem ảnh.'}
