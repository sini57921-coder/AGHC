import hashlib
import io
import struct
from PIL import Image, ImageOps, UnidentifiedImageError

VERSION = "exif_rgb_png_v1"
SUPPORTED = {"JPEG", "PNG", "WEBP", "BMP"}


class InputImageError(ValueError):
    def __init__(self, reason, code="input_decode_failed", status_code=422):
        super().__init__(reason)
        self.code = code
        self.status_code = status_code


def normalize_image(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            fmt = image.format
            if fmt not in SUPPORTED:
                raise InputImageError("不支持该图像格式；请上传JPEG、PNG、WEBP或BMP静态照片。", "unsupported_image_format", 415)
            if getattr(image, "n_frames", 1) != 1:
                raise InputImageError("不支持动态图，请上传单张静态照片。", "animated_image_unsupported", 415)
            image.load()
            original_size, original_mode = image.size, image.mode
            orientation = image.getexif().get(274)
            upright = ImageOps.exif_transpose(image)
            alpha = "A" in upright.getbands() or "transparency" in upright.info
            if alpha:
                rgba = upright.convert("RGBA")
                rgb = Image.new("RGB", upright.size, "white")
                rgb.paste(rgba, mask=rgba.getchannel("A"))
            else:
                rgb = upright.convert("RGB")
            pixels = rgb.tobytes()
            clean = Image.frombytes("RGB", rgb.size, pixels)
            encoded = io.BytesIO()
            clean.save(encoded, format="PNG", compress_level=6)
            normalized = encoded.getvalue()
            info = {
                "version": VERSION, "decoded_format": fmt,
                "original_mode": original_mode, "original_dimensions": list(original_size),
                "exif_orientation": orientation, "processed_mode": "RGB",
                "processed_dimensions": list(rgb.size), "processed_format": "PNG",
                "alpha_policy": "composite_on_white" if alpha else "not_applicable",
                "processed_pixel_sha256": hashlib.sha256(struct.pack(">II", *rgb.size) + pixels).hexdigest(),
                "processed_sha256": hashlib.sha256(normalized).hexdigest(),
            }
            return normalized, info
    except InputImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise InputImageError("无法完整解码该文件；请确认照片未损坏，并使用JPEG、PNG、WEBP或BMP格式。") from error
