"""Images are served from /app/static (cached by the browser), not inlined as base64 on every rerun."""
import json
from pathlib import Path

from src.dashboard.brand_ui import STATIC_DIR, asset, static_url

ASSETS = Path(__file__).resolve().parents[1] / 'src' / 'dashboard' / 'assets'


def test_every_page_image_has_a_static_copy():
    named = ['snow-king-cutout.png', 'snow-king-reference.png', 'brand-pattern.svg', 'ice-cream.png', 'lemonade.png',
             'milk-tea.png', 'login-snow-world-v1.png', 'login-snow-world-mobile-v1.png']
    products = {item['file'] for item in json.loads((ASSETS / 'product-images.json').read_text(encoding='utf-8')).values()}
    missing = [name for name in [*named, *products] if static_url(name) is None]
    assert not missing, f'Run scripts/build_static_assets.py; missing: {missing}'


def test_asset_returns_a_short_cached_url_not_base64():
    url = asset('login-snow-world-v1.png')
    assert url == 'app/static/login-snow-world-v1.webp'
    assert (STATIC_DIR / 'login-snow-world-v1.webp').stat().st_size < 300_000
    assert not asset('snow-king-cutout.png').startswith('data:')
