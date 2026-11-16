"""Decode only supported raster formats with explicit byte and pixel budgets."""

import io

from PIL import Image, UnidentifiedImageError

from app.domain.errors import DomainError

MAX_PIXELS = 24_000_000
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def validate_image(content: bytes, content_type: str, max_bytes: int) -> None:
    try:
        if not content or len(content) > max_bytes or content_type not in FORMATS:
            raise ValueError
        with Image.open(io.BytesIO(content), formats=[FORMATS[content_type]]) as image:
            if image.width * image.height > MAX_PIXELS or getattr(image, "n_frames", 1) != 1:
                raise ValueError
            image.verify()
        with Image.open(io.BytesIO(content), formats=[FORMATS[content_type]]) as image:
            image.load()
    except (
        ValueError,
        OSError,
        SyntaxError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        raise DomainError(
            "INVALID_IMAGE", "Upload a valid JPEG, PNG or WebP image.", status_code=422
        ) from exc
