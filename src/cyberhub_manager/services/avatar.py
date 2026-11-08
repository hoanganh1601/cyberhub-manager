"""Decode uploaded images into a bounded, metadata-free square avatar."""

from hashlib import sha256
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from cyberhub_manager.domain.exceptions import ValidationError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def normalize_avatar(content):
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_UPLOAD_BYTES:
        raise ValidationError(
            field_errors={"avatar": "Chọn ảnh JPEG, PNG hoặc WebP, tối đa 2 MB"}
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if (
                    source.format not in ("JPEG", "PNG", "WEBP")
                    or getattr(source, "n_frames", 1) != 1
                ):
                    raise ValueError()
                if (
                    not 1 <= source.width <= 8192
                    or not 1 <= source.height <= 8192
                    or source.width * source.height > 16_000_000
                ):
                    raise ValueError()
                source.load()
                corrected = ImageOps.exif_transpose(source)
                # Flatten transparency onto the app's dark surface instead of making it black.
                rgba = corrected.convert("RGBA")
                flat = Image.new("RGBA", rgba.size, (17, 25, 39, 255))
                flat.alpha_composite(rgba)
                image = ImageOps.fit(
                    flat.convert("RGB"), (512, 512), method=Image.Resampling.LANCZOS
                )
                output = BytesIO()
                image.save(output, format="WEBP", quality=85, method=4)
                data = output.getvalue()
                if len(data) > 300_000:
                    raise ValueError()
                return data, sha256(data).hexdigest()
    except (
        UnidentifiedImageError,
        ValueError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise ValidationError(
            field_errors={
                "avatar": "Ảnh không hợp lệ; dùng JPEG, PNG hoặc WebP tĩnh, tối đa 16 triệu điểm ảnh"
            }
        ) from None
