"""Color curve adjustment using PCHIP monotone cubic interpolation.

Each channel (rgb/r/g/b) has control points [[x0,y0],[x1,y1],...] in 0-255 space.
We build a 256-value LUT per channel using the Fritsch-Carlson PCHIP algorithm,
then apply per-channel curves first and the master RGB curve after.
"""

from typing import List

import numpy as np
from PIL import Image

_IDENTITY = [[0, 0], [255, 255]]


def _build_lut(points: List[List[int]]) -> List[int]:
    """Return a 256-value int list mapping input → output via PCHIP spline."""
    if not points or len(points) < 2:
        return list(range(256))

    # Deduplicate by x (last y wins), then sort
    seen: dict = {}
    for p in points:
        x = max(0, min(255, int(p[0])))
        y = max(0, min(255, int(p[1])))
        seen[x] = y
    pts = sorted(seen.items())

    if len(pts) < 2:
        return [pts[0][1]] * 256

    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)
    n = len(xs)

    # Secant slopes
    d = np.diff(ys) / np.diff(xs)

    # Initial tangent estimates
    m = np.zeros(n)
    m[0] = d[0]
    m[-1] = d[-1]
    for i in range(1, n - 1):
        m[i] = 0.0 if d[i - 1] * d[i] <= 0 else (d[i - 1] + d[i]) / 2.0

    # Fritsch-Carlson monotonicity constraint
    for i in range(n - 1):
        di = d[i]
        if abs(di) < 1e-10:
            m[i] = m[i + 1] = 0.0
            continue
        a, b_ = m[i] / di, m[i + 1] / di
        s2 = a * a + b_ * b_
        if s2 > 9:
            tau = 3.0 / np.sqrt(s2)
            m[i] = tau * a * di
            m[i + 1] = tau * b_ * di

    lut = []
    for x in range(256):
        if x <= xs[0]:
            lut.append(int(max(0, min(255, round(ys[0])))))
        elif x >= xs[-1]:
            lut.append(int(max(0, min(255, round(ys[-1])))))
        else:
            i = int(np.searchsorted(xs, x, side="right") - 1)
            i = min(i, n - 2)
            h = xs[i + 1] - xs[i]
            t = (x - xs[i]) / h
            y = (
                ys[i]       * (2 * t**3 - 3 * t**2 + 1)
                + h * m[i]  * (t**3 - 2 * t**2 + t)
                + ys[i + 1] * (-2 * t**3 + 3 * t**2)
                + h * m[i + 1] * (t**3 - t**2)
            )
            lut.append(int(max(0, min(255, round(y)))))
    return lut


def _is_identity(points: List[List[int]]) -> bool:
    clean = sorted((max(0, min(255, p[0])), max(0, min(255, p[1]))) for p in points)
    return clean == [(0, 0), (255, 255)]


def apply_curves(img: Image.Image, params) -> Image.Image:
    """Apply master RGB + per-channel curves to a PIL Image."""
    if all(_is_identity(getattr(params, ch)) for ch in ("rgb", "r", "g", "b")):
        return img  # fast path — nothing to do

    rgb_lut = _build_lut(params.rgb)
    r_lut   = _build_lut(params.r)
    g_lut   = _build_lut(params.g)
    b_lut   = _build_lut(params.b)

    # Per-channel curve first, then master RGB on top
    fr = [rgb_lut[r_lut[i]] for i in range(256)]
    fg = [rgb_lut[g_lut[i]] for i in range(256)]
    fb = [rgb_lut[b_lut[i]] for i in range(256)]

    r, g, b = img.convert("RGB").split()
    return Image.merge("RGB", (r.point(fr), g.point(fg), b.point(fb)))
