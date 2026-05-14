import cv2
import numpy as np
from PIL import Image

from app.types.models import PortraitParams


def apply_portrait(img: Image.Image, params: PortraitParams) -> Image.Image:
    if not params.smooth_skin and not params.brighten_skin:
        return img

    arr = np.array(img.convert("RGB"))

    if params.smooth_skin:
        arr = _smooth_skin(arr, params.smooth_level)
    if params.brighten_skin:
        arr = _brighten_skin(arr, params.brighten_level)

    return Image.fromarray(arr)


def _smooth_skin(arr: np.ndarray, level: float) -> np.ndarray:
    # Bilateral filter: smooths flat regions while preserving edges
    d = max(5, int(5 + level * 10))
    sigma = int(25 + level * 50)

    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    smoothed_bgr = cv2.bilateralFilter(bgr, d, sigma, sigma)
    smoothed = cv2.cvtColor(smoothed_bgr, cv2.COLOR_BGR2RGB)

    alpha = min(0.3 + level * 0.55, 0.85)
    return cv2.addWeighted(arr, 1 - alpha, smoothed, alpha, 0)


def _brighten_skin(arr: np.ndarray, level: float) -> np.ndarray:
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)

    # Skin tone range in OpenCV HSV (H: 0-179, S/V: 0-255)
    skin_mask = (
        (hsv[:, :, 0] >= 0) & (hsv[:, :, 0] <= 25)
        & (hsv[:, :, 1] >= 48)
        & (hsv[:, :, 2] >= 50)
    )

    hsv[:, :, 2] = np.where(
        skin_mask,
        np.clip(hsv[:, :, 2] * (1 + level * 0.25), 0, 255),
        hsv[:, :, 2],
    )

    result_bgr = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    return cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
