"""The real app with only the vision model replaced by saved transcripts of the 01/11/2026 photos.

Used by scripts/ui_flow.py to click through the whole staff → manager flow in a real browser.
"""
import base64
import hashlib
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage  # noqa: E402

import src.dashboard.shift_closing_ui as shift_ui  # noqa: E402
from src.engine.image_upload import normalize_photo  # noqa: E402
from src.engine.vision_ocr import extract_image  # noqa: E402

SPEC = json.loads((ROOT / 'data/ocr_eval/day_sheet_20261101.json').read_text(encoding='utf-8'))
PHOTOS = ROOT / 'data/shift_photos'
SHEETS = {}
for name, sheet in SPEC['clean'].items():
    raw = (PHOTOS / name).read_bytes()
    for data in (raw, normalize_photo(raw, name)):  # as picked, and as stored after upload
        SHEETS[hashlib.sha256(data).hexdigest()] = sheet


class ReplayReader:
    def invoke(self, messages):
        url = next(part['image_url']['url'] for part in messages[1].content if part.get('type') == 'image_url')
        sheet = SHEETS.get(hashlib.sha256(base64.b64decode(url.split(',', 1)[1])).hexdigest())
        if sheet is None:
            raise RuntimeError('ui_flow: unknown photo')
        return AIMessage(content=json.dumps(sheet, ensure_ascii=False))


def replay_extract(image_bytes=None, image_path=None, images=None, image_paths=None, shift_hint=None, target_date=None, **_):
    return extract_image(image_bytes=image_bytes, image_path=image_path, images=images, image_paths=image_paths,
                         shift_hint=shift_hint, target_date=target_date, model=ReplayReader())


shift_ui.extract_shift_data_from_image = replay_extract
runpy.run_path(str(ROOT / 'src/dashboard/app.py'), run_name='__main__')
