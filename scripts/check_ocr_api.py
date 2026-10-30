"""Opt-in vision smoke test with synthetic receipts, never store photos."""
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.agent.config import AgentSettings
from src.engine.vision_ocr import extract_image


def main():
    settings = AgentSettings.from_env()
    if not settings.llm_enabled or not settings.allow_external_transfer:
        raise SystemExit('API and external-transfer configuration must be enabled explicitly.')
    reports = []
    for cash in [123456, 456789]:
        image = Image.new('RGB', (1000, 400), 'white')
        font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 42) if Path('C:/Windows/Fonts/arial.ttf').is_file() else ImageFont.load_default(size=42)
        ImageDraw.Draw(image).multiline_text((35, 30),
            f'SHIFT REPORT - TEST\nDate: 2026-10-16\nCash: {cash} VND\nBank transfer: 200000 VND',
            font=font, fill='black', spacing=18)
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        result = extract_image(image_bytes=buffer.getvalue(), shift_hint='CA_SANG', target_date='2026-10-16')
        row = {'expected_cash': cash, 'status': result['status'], 'read_cash': result.get('cash_vnd'),
               'model': result.get('model'), 'error_type': result.get('error_type'),
               'passed': result['status'] == 'NEEDS_REVIEW' and result.get('cash_vnd') == cash}
        reports.append(row)
        print(json.dumps(row), flush=True)
    path = Path('data/agent_private/ocr-live-check.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reports, indent=2), encoding='utf-8')
    if not all(row['passed'] for row in reports):
        raise SystemExit('Live OCR did not pass both synthetic images; inspect the sanitized report.')


if __name__ == '__main__':
    main()
