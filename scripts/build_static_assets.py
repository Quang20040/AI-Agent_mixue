"""Build src/dashboard/static/ — the images the browser downloads once and caches.

Streamlit serves this folder at /app/static/ (server.enableStaticServing). Before, every page
re-sent ~1 MB of base64 images inside the HTML on each rerun; now the HTML carries short URLs.
Large PNGs are re-encoded to WebP (alpha kept). Re-run after changing src/dashboard/assets/.
"""
from pathlib import Path
import json
import shutil

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src' / 'dashboard' / 'assets'
OUT = ROOT / 'src' / 'dashboard' / 'static'

# Images the pages reference through brand_ui.asset(); products come from product-images.json.
NAMED = ['snow-king-cutout.png', 'snow-king-reference.png', 'brand-pattern.svg', 'ice-cream.png', 'lemonade.png',
         'milk-tea.png', 'login-snow-world-v1.png', 'login-snow-world-mobile-v1.png']
MAX_SIDE = {'login-snow-world-v1.png': 1920, 'login-snow-world-mobile-v1.png': 900}


def static_name(name):
    """PNG/JPG become WebP; other files keep their name."""
    path = Path(name)
    return str(path.with_suffix('.webp')) if path.suffix.lower() in {'.png', '.jpg', '.jpeg'} else name


def build():
    OUT.mkdir(exist_ok=True)
    products = sorted({item['file'] for item in json.loads((SRC / 'product-images.json').read_text(encoding='utf-8')).values()})
    for name in NAMED + products:
        source, target = SRC / name, OUT / static_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
            image = Image.open(source)
            image.thumbnail((MAX_SIDE.get(name, 640),) * 2)
            image.save(target, 'WEBP', quality=82, method=6)
        else:
            shutil.copyfile(source, target)
        print(f'{name:40} {source.stat().st_size // 1024:6} KB -> {target.stat().st_size // 1024:5} KB')


if __name__ == '__main__':
    build()
