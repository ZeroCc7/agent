import numpy as np
import pytest
from PIL import Image
from app.core.image_processor import apply_extended_edits
from app.types.models import ExtendedEditParams


def _solid(r, g, b, size=100) -> Image.Image:
    return Image.new("RGB", (size, size), (r, g, b))


def test_identity_returns_same_image():
    img = _solid(120, 80, 60)
    result = apply_extended_edits(img, ExtendedEditParams())
    assert np.array_equal(np.array(img), np.array(result))


def test_highlights_darkens_bright_pixels():
    img = _solid(220, 220, 220)  # bright
    result = apply_extended_edits(img, ExtendedEditParams(highlights=-50))
    arr_in = np.array(img).mean()
    arr_out = np.array(result).mean()
    assert arr_out < arr_in


def test_shadows_brightens_dark_pixels():
    img = _solid(40, 40, 40)  # dark
    result = apply_extended_edits(img, ExtendedEditParams(shadows=50))
    arr_in = np.array(img).mean()
    arr_out = np.array(result).mean()
    assert arr_out > arr_in


def test_blacks_raises_black_point():
    img = _solid(10, 10, 10)  # near-black
    result = apply_extended_edits(img, ExtendedEditParams(blacks=50))
    assert np.array(result).mean() > np.array(img).mean()


def test_whites_lowers_white_point():
    img = _solid(240, 240, 240)  # near-white
    result = apply_extended_edits(img, ExtendedEditParams(whites=-50))
    assert np.array(result).mean() < np.array(img).mean()


def test_vibrance_increases_saturation():
    img = _solid(150, 120, 100)  # low saturation
    result = apply_extended_edits(img, ExtendedEditParams(vibrance=40))
    in_arr = np.array(img).astype(float)
    out_arr = np.array(result).astype(float)
    in_sat = in_arr.max(axis=2) - in_arr.min(axis=2)
    out_sat = out_arr.max(axis=2) - out_arr.min(axis=2)
    assert out_sat.mean() > in_sat.mean()


def test_clarity_positive_increases_contrast():
    # Clarity boosts local contrast — edge difference should increase
    arr = np.tile(np.linspace(50, 200, 100, dtype=np.uint8), (100, 1))
    img = Image.fromarray(np.stack([arr, arr, arr], axis=2))
    result = apply_extended_edits(img, ExtendedEditParams(clarity=40))
    in_std = np.array(img).std()
    out_std = np.array(result).std()
    assert out_std > in_std


def test_vignette_positive_darkens_corners():
    img = _solid(200, 200, 200, size=200)
    result = apply_extended_edits(img, ExtendedEditParams(vignette=80))
    arr = np.array(result).astype(float)
    center = arr[90:110, 90:110].mean()
    corner = arr[0:20, 0:20].mean()
    assert corner < center


def test_vignette_negative_brightens_corners():
    img = _solid(100, 100, 100, size=200)
    result = apply_extended_edits(img, ExtendedEditParams(vignette=-80))
    arr = np.array(result).astype(float)
    center = arr[90:110, 90:110].mean()
    corner = arr[0:20, 0:20].mean()
    assert corner > center


def test_grain_changes_pixel_values():
    img = _solid(128, 128, 128)
    result = apply_extended_edits(img, ExtendedEditParams(grain=50))
    assert not np.array_equal(np.array(img), np.array(result))


def test_split_toning_shadow_shifts_dark_pixels():
    img = _solid(30, 30, 30)  # dark image
    result = apply_extended_edits(
        img, ExtendedEditParams(shadow_tint=240, shadow_tint_strength=80)
    )
    # hue=240 is blue — blue channel should increase in dark pixels
    assert np.array(result)[:, :, 2].mean() > np.array(img)[:, :, 2].mean()
