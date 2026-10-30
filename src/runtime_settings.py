"""Small shared settings with safe defaults; importing never provisions accounts."""

import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def setting(name, default=""):
    return os.environ.get(name, dotenv_values(ROOT / ".env").get(name) or default)


def demo_enabled():
    return setting("APP_DEMO_MODE", "false").lower() == "true" and setting("APP_ENV", "development").lower() != "production"


def configured_store_id():
    return setting("STORE_ID", "").strip()


def resolve_store_id(db, requested=None):
    """A single-store install can infer identity; multiple stores must be explicit."""
    from src.models import SalesDaily

    selected = requested or configured_store_id()
    stores = [row[0] for row in db.query(SalesDaily.store_id).distinct().all()]
    if selected:
        if stores and selected not in stores:
            raise ValueError("STORE_ID không khớp dữ liệu bán hàng. Hãy kiểm tra cấu hình cửa hàng.")
        return selected
    if len(stores) > 1:
        raise ValueError("Dữ liệu có nhiều cửa hàng; cần cấu hình STORE_ID trước khi tra cứu.")
    return stores[0] if stores else "2132"
