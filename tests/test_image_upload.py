"""Any phone photo is accepted by content and stored as a light, upright JPEG."""
import io

import pytest
from PIL import Image

from src.engine.image_upload import STORE_LONG_SIDE, UploadError, normalize_photo, save_photo, thumbnail


def _image(fmt, size=(4000, 3000), mode='RGB', **kwargs):
    buffer = io.BytesIO()
    Image.new(mode, size, 'white' if mode != 'RGBA' else (255, 255, 255, 0)).save(buffer, fmt, **kwargs)
    return buffer.getvalue()


@pytest.mark.parametrize('fmt,mode', [('JPEG', 'RGB'), ('PNG', 'RGBA'), ('WEBP', 'RGB'), ('BMP', 'RGB')])
def test_any_format_becomes_small_jpeg(fmt, mode):
    out = normalize_photo(_image(fmt, mode=mode), f'photo.{fmt.lower()}')
    with Image.open(io.BytesIO(out)) as image:
        assert image.format == 'JPEG' and max(image.size) == STORE_LONG_SIDE


def test_file_name_does_not_matter_and_exif_rotation_is_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # rotated 90° by the camera
    raw = _image('JPEG', size=(1200, 800), exif=exif.tobytes())
    with Image.open(io.BytesIO(normalize_photo(raw, 'IMG_0001.HEIC'))) as image:
        assert image.size == (800, 1200)


def test_non_image_is_rejected_with_message():
    with pytest.raises(UploadError, match='không phải ảnh'):
        normalize_photo(b'%PDF-1.7 not a photo', 'so_ca.pdf')


def test_save_is_content_addressed_and_thumbnail_is_small(tmp_path):
    raw = _image('PNG', size=(3000, 2000))
    first, second = save_photo(raw, 'a.png', tmp_path), save_photo(raw, 'b.png', tmp_path)
    assert first == second and first.suffix == '.jpg'
    with Image.open(io.BytesIO(thumbnail(first))) as image:
        assert max(image.size) <= 720
