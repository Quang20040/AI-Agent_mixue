"""Time live photo reads on the deployed app. Each photo is re-encoded with a tiny change so its hash is new
(no cached reading). Scenarios: one photo read right after upload; three photos at once; and one photo read
after a 30 s pause (the background read started at upload)."""
import json
import random
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'ocr_timing']
import qa_live as q  # noqa: E402  (shares the login / navigation helpers)

OUT = q.OUT
PHOTOS = sorted((q.ROOT / 'data/shift_photos').glob('20261101*.jpg'))


def fresh(src: Path, tag: str) -> Path:
    im = Image.open(src).convert('RGB')
    x, y = random.randrange(im.width), random.randrange(im.height)
    im.putpixel((x, y), (random.randrange(256), 0, 0))
    out = OUT / f'{tag}_{src.name}'
    im.save(out, quality=93)
    return out


def read(page, files, pause=0.0, label=''):
    page.locator('.st-key-shift_photo_uploader input[type=file]').first.set_input_files([str(f) for f in files])
    q.idle(page, 800)
    if pause:
        page.wait_for_timeout(int(pause * 1000))
    t = time.time()
    page.locator('.st-key-run_shift_ocr button').first.click()
    page.locator('.px-read-summary, [data-testid="stAlert"]').first.wait_for(timeout=240000)
    q.idle(page, 500, limit=240)
    seconds = round(time.time() - t, 1)
    body = q.text(page)
    summary = next((ln for ln in body.split('\n') if ln.startswith('Đọc xong')), '')
    q.shot(page, label)
    return {'case': label, 'photos': len(files), 'pause_before_click_s': pause, 'seconds_after_click': seconds,
            'app_summary': summary, 'error': '' if summary else body[:300]}


def main():
    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for label, files, pause in [
            ('one_photo_click_now', [fresh(PHOTOS[0], 'a')], 0),
            ('three_photos_click_now', [fresh(p, 'b') for p in PHOTOS], 0),
            ('one_photo_after_30s', [fresh(PHOTOS[1], 'c')], 30),
        ]:
            page = q.new_page(browser, label=label)
            try:
                q.quick_login(page, 'quick_login_manager')
                q.nav(page, 'Chốt ca')
                rows.append(read(page, files, pause, label))
            except Exception as exc:  # noqa: BLE001
                rows.append({'case': label, 'error': f'{type(exc).__name__}: {exc}'[:300]})
            print(rows[-1], flush=True)
            page.context.close()
        browser.close()
    (OUT / 'timing.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
