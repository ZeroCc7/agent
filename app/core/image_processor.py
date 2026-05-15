import colorsys

import cv2
import numpy as np
from PIL import Image, ImageEnhance

from app.types.models import EditParams, ExtendedEditParams


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


def apply_extended_edits(img: Image.Image, params: ExtendedEditParams) -> Image.Image:
    if _is_identity_extended(params):
        return img

    img = img.convert("RGB")
    arr = np.array(img, dtype=np.float32)

    if any(v != 0 for v in [params.highlights, params.shadows, params.whites, params.blacks]):
        arr = _adjust_tonal_range(arr, params.highlights, params.shadows, params.whites, params.blacks)

    if params.vibrance != 0:
        arr = _adjust_vibrance(arr, params.vibrance)

    if params.clarity != 0:
        arr = _adjust_clarity(arr, params.clarity)

    if params.shadow_tint_strength > 0 or params.highlight_tint_strength > 0:
        arr = _apply_split_toning(
            arr,
            params.shadow_tint, params.shadow_tint_strength,
            params.highlight_tint, params.highlight_tint_strength,
        )

    img = Image.fromarray(arr.astype(np.uint8))

    if params.vignette != 0:
        img = _apply_vignette(img, params.vignette)

    if params.grain > 0:
        img = _apply_grain(img, params.grain)

    return img


def _is_identity_extended(params: ExtendedEditParams) -> bool:
    return all([
        params.highlights == 0, params.shadows == 0,
        params.whites == 0, params.blacks == 0,
        params.vibrance == 0, params.clarity == 0,
        params.vignette == 0, params.grain == 0,
        params.shadow_tint_strength == 0, params.highlight_tint_strength == 0,
    ])


def _adjust_tonal_range(
    arr: np.ndarray, highlights: int, shadows: int, whites: int, blacks: int
) -> np.ndarray:
    lut = np.arange(256, dtype=np.float32)

    if blacks != 0:
        mask = np.clip((64.0 - lut) / 64.0, 0, 1) ** 2
        lut += blacks * 0.5 * mask

    if shadows != 0:
        mask = np.clip((128.0 - lut) / 128.0, 0, 1)
        lut += shadows * 0.4 * mask

    if highlights != 0:
        mask = np.clip((lut - 128.0) / 127.0, 0, 1)
        lut += highlights * 0.4 * mask

    if whites != 0:
        mask = np.clip((lut - 192.0) / 63.0, 0, 1) ** 2
        lut += whites * 0.5 * mask

    lut = lut.clip(0, 255).astype(np.uint8)
    return lut[arr.astype(np.uint8)].astype(np.float32)


def _adjust_vibrance(arr: np.ndarray, vibrance: int) -> np.ndarray:
    img_uint8 = arr.astype(np.uint8)
    hsv = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2HSV).astype(np.float32)
    sat = hsv[:, :, 1] / 255.0
    factor = vibrance / 60.0
    delta = factor * (1.0 - sat) * 255.0
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] + delta, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)


def _adjust_clarity(arr: np.ndarray, clarity: int) -> np.ndarray:
    img_uint8 = arr.astype(np.uint8)
    if clarity > 0:
        blurred = cv2.GaussianBlur(img_uint8, (0, 0), 10)
        alpha = clarity / 60.0 * 0.5
        result = cv2.addWeighted(img_uint8, 1 + alpha, blurred, -alpha, 0)
    else:
        sigma = abs(clarity) / 60.0 * 3.0
        ksize = max(3, int(sigma * 3) | 1)
        result = cv2.GaussianBlur(img_uint8, (ksize, ksize), sigma)
    return result.astype(np.float32)


def _apply_vignette(img: Image.Image, vignette: int) -> Image.Image:
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt(((X - w / 2.0) / (w / 2.0)) ** 2 + ((Y - h / 2.0) / (h / 2.0)) ** 2)
    center_mask = np.clip(1.0 - dist, 0, 1) ** 2
    factor = vignette / 100.0
    blend = (1.0 + factor * (1.0 - center_mask))[:, :, np.newaxis]
    return Image.fromarray(np.clip(arr * blend, 0, 255).astype(np.uint8))


def _apply_grain(img: Image.Image, grain: int) -> Image.Image:
    arr = np.array(img, dtype=np.float32)
    sigma = grain / 100.0 * 20.0
    noise = np.random.normal(0, sigma, arr.shape)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def _apply_split_toning(
    arr: np.ndarray,
    shadow_hue: int, shadow_strength: int,
    highlight_hue: int, highlight_strength: int,
) -> np.ndarray:
    luma = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]) / 255.0
    result = arr.copy()

    if shadow_strength > 0:
        s_mask = np.clip(1.0 - luma * 2, 0, 1)[:, :, np.newaxis] * (shadow_strength / 100.0) * 0.25
        color = np.array(colorsys.hsv_to_rgb(shadow_hue / 360.0, 1.0, 1.0)) * 255.0
        result = result * (1 - s_mask) + color * s_mask

    if highlight_strength > 0:
        h_mask = np.clip((luma - 0.5) * 2, 0, 1)[:, :, np.newaxis] * (highlight_strength / 100.0) * 0.25
        color = np.array(colorsys.hsv_to_rgb(highlight_hue / 360.0, 1.0, 1.0)) * 255.0
        result = result * (1 - h_mask) + color * h_mask

    return np.clip(result, 0, 255)
