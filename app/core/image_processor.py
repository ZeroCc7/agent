import numpy as np
from PIL import Image, ImageEnhance

from app.types.models import EditParams


def apply_basic_edits(img: Image.Image, params: EditParams) -> Image.Image:
    img = img.convert("RGB")

    if params.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(params.brightness)
    if params.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(params.contrast)
    if params.saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(params.saturation)
    if params.sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(params.sharpness)
    if params.color_temp != 0:
        img = _adjust_color_temp(img, params.color_temp)

    return img


def _adjust_color_temp(img: Image.Image, temp: int) -> Image.Image:
    arr = np.array(img, dtype=np.float32)
    factor = temp / 100.0
    if factor > 0:  # warm: boost red, reduce blue
        arr[:, :, 0] = np.clip(arr[:, :, 0] * (1 + 0.15 * factor), 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] * (1 - 0.10 * factor), 0, 255)
    else:  # cool: boost blue, reduce red
        factor = -factor
        arr[:, :, 2] = np.clip(arr[:, :, 2] * (1 + 0.15 * factor), 0, 255)
        arr[:, :, 0] = np.clip(arr[:, :, 0] * (1 - 0.10 * factor), 0, 255)
    return Image.fromarray(arr.astype(np.uint8))
