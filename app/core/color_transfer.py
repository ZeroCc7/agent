import cv2
import numpy as np
from PIL import Image


def color_transfer(source: Image.Image, reference: Image.Image) -> Image.Image:
    """
    Transfer color palette from reference to source.
    Uses Reinhard et al. (2001) mean/std matching in LAB color space.
    LAB separates luminance from color, producing natural-looking results
    without the hue shifts that RGB-channel histogram matching causes.
    """
    src_rgb = np.array(source.convert("RGB"))
    ref_rgb = np.array(reference.convert("RGB"))

    src_lab = cv2.cvtColor(src_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    ref_lab = cv2.cvtColor(ref_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    result = np.empty_like(src_lab)
    for ch in range(3):
        s = src_lab[:, :, ch]
        r = ref_lab[:, :, ch]
        s_std = s.std()
        if s_std < 1e-6:
            result[:, :, ch] = s
        else:
            result[:, :, ch] = (s - s.mean()) / s_std * r.std() + r.mean()

    result = np.clip(result, 0, 255).astype(np.uint8)
    rgb = cv2.cvtColor(result, cv2.COLOR_LAB2RGB)
    return Image.fromarray(rgb)
