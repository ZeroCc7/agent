from PIL import Image, ImageFilter

from app.types.models import BackgroundParams


def apply_background(img: Image.Image, params: BackgroundParams) -> Image.Image:
    if params.action == "none":
        return img
    if params.action == "blur":
        return _blur_background(img, max(params.blur_radius, 1))
    if params.action == "remove":
        return _remove_background(img)
    return img


def _blur_background(img: Image.Image, radius: int) -> Image.Image:
    try:
        from rembg import remove

        mask = remove(img, only_mask=True)
        if mask.mode != "L":
            mask = mask.convert("L")

        blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
        result = blurred.copy()
        result.paste(img, mask=mask)
        return result
    except Exception:
        # rembg unavailable or failed — apply simple blur as fallback
        return img.filter(ImageFilter.GaussianBlur(radius=radius))


def _remove_background(img: Image.Image) -> Image.Image:
    try:
        from rembg import remove

        return remove(img)
    except ImportError:
        # rembg not installed; install with: pip install rembg onnxruntime
        return img
    except Exception:
        return img
