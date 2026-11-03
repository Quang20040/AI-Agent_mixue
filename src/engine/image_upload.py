"""Uploaded photos from any phone: accept whatever the picker sends, store one light, upright JPEG.

Phones send HEIC (iPhone), huge JPEGs, PNG screenshots or WebP. The app does not ask the user to pick a size or a
format; it decodes by content (not by file name), turns the photo upright, shrinks it to a size that is still sharp
for handwriting and saves it as JPEG. Smaller files upload to the vision model faster, render faster on phones and
take less disk on the free host.
"""
from __future__ import annotations

import hashlib
import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

try:  # HEIC/HEIF from iPhones; optional so the app still runs where the wheel is missing.
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:  # pragma: no cover - depends on the platform wheel
    HEIF_SUPPORTED = False

MAX_UPLOAD_BYTES = 40 * 1024 * 1024
STORE_LONG_SIDE = 2400  # enough for 1-2 mm handwriting on an A4 page
THUMB_LONG_SIDE = 720
Image.MAX_IMAGE_PIXELS = 80_000_000


class UploadError(ValueError):
    """A file the user picked that is not a readable photo; the message is shown as is."""


def _looks_heif(data: bytes) -> bool:
    return data[4:12] in {b'ftypheic', b'ftypheix', b'ftyphevc', b'ftypmif1', b'ftypmsf1', b'ftypheim', b'ftypheis'}


def _decode_small(image: Image.Image, long_side: int) -> None:
    """Ask the JPEG decoder for the smallest 1/2, 1/4 or 1/8 scale whose long side stays >= 1800 px."""
    if image.format != 'JPEG':
        return
    width, height = image.size
    floor = min(long_side, 1800)
    for k in (8, 4, 2):
        if max(width, height) // k >= floor:
            image.draft('RGB', (width // k, height // k))
            return


def normalize_photo(data: bytes, name: str = 'ảnh') -> bytes:
    """Return an upright RGB JPEG no larger than STORE_LONG_SIDE, or raise UploadError with a friendly message."""
    if not data:
        raise UploadError(f"Tệp '{name}' rỗng.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError(f"Tệp '{name}' lớn hơn {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            # Keep the peak small on the 512 MB host: a 12 MP phone JPEG decodes at 1/2 or 1/4 scale straight
            # from the file (draft), and every other format is shrunk before the rotate/convert copies are made.
            _decode_small(image, STORE_LONG_SIDE)
            image.thumbnail((STORE_LONG_SIDE, STORE_LONG_SIDE), Image.LANCZOS, reducing_gap=3.0)
            image = ImageOps.exif_transpose(image)
            if image.mode not in ('RGB', 'L'):
                background = Image.new('RGB', image.size, 'white')
                rgba = image.convert('RGBA')
                background.paste(rgba, mask=rgba.getchannel('A'))
                image = background
            image = image.convert('RGB')
            image.thumbnail((STORE_LONG_SIDE, STORE_LONG_SIDE), Image.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, 'JPEG', quality=88, optimize=True)
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        if _looks_heif(data) and not HEIF_SUPPORTED:
            raise UploadError(f"Máy chủ chưa đọc được ảnh HEIC '{name}'. Hãy chụp màn hình ảnh đó rồi gửi lại.") from exc
        raise UploadError(f"'{name}' không phải ảnh đọc được. Hãy chọn ảnh chụp sổ chốt ca hoặc phiếu POS.") from exc


def save_photo(data: bytes, name: str, directory: Path) -> Path:
    """Normalize and store under a content hash of the normalized photo (same photo → same file)."""
    jpeg = normalize_photo(data, name)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{hashlib.sha256(jpeg).hexdigest()}.jpg'
    if not path.exists():
        path.write_bytes(jpeg)
    return path


@lru_cache(maxsize=64)
def _thumbnail(path: str, mtime: float) -> bytes:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((THUMB_LONG_SIDE, THUMB_LONG_SIDE), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=80, optimize=True)
        return buffer.getvalue()


def thumbnail(path: str | Path) -> bytes | str:
    """Small preview for the page (phones download this, not the full photo). Falls back to the path."""
    try:
        return _thumbnail(str(path), Path(path).stat().st_mtime)
    except (OSError, ValueError):
        return str(path)
