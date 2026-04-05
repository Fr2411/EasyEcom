from __future__ import annotations

import io

import pytest
from PIL import Image

from easy_ecom.domain.services.product_media_service import LARGE_MAX_EDGE, ProductMediaService, THUMB_CANVAS_SIZE


def _build_jpeg(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), (10, 20, 30))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


@pytest.mark.parametrize(
    ("width", "height", "expected_large_width", "expected_large_height"),
    [
        (4000, 1000, LARGE_MAX_EDGE, LARGE_MAX_EDGE // 4),
        (1000, 4000, LARGE_MAX_EDGE // 4, LARGE_MAX_EDGE),
        (1200, 900, 1200, 900),
    ],
)
def test_normalize_image_keeps_large_asset_aspect_and_square_thumbnail(
    width: int,
    height: int,
    expected_large_width: int,
    expected_large_height: int,
):
    service = ProductMediaService()
    payload = _build_jpeg(width, height)

    rendered = service._normalize_image(payload)

    assert rendered.large_width == expected_large_width
    assert rendered.large_height == expected_large_height
    assert rendered.thumbnail_width == THUMB_CANVAS_SIZE
    assert rendered.thumbnail_height == THUMB_CANVAS_SIZE
    assert rendered.large_bytes
    assert rendered.thumbnail_bytes
