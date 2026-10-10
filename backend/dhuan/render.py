"""Turn an hourly smoke grid into a translucent PNG the map can drape over North India."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageFilter

# estimated PM2.5 contribution (ug/m3) -> RGBA. Transparent below the first stop.
STOPS = [
    (0.0, (255, 235, 180, 0)),
    (1.5, (255, 235, 185, 28)),  # a faint haze, so the plume's shape is visible before it counts as "light"
    (8.0, (255, 225, 150, 95)),
    (25.0, (255, 190, 90, 145)),
    (50.0, (255, 130, 50, 175)),
    (100.0, (225, 60, 50, 210)),
    (200.0, (150, 20, 80, 235)),
    (400.0, (70, 0, 60, 245)),
]
UPSCALE = 3


def colorize(ug: np.ndarray) -> np.ndarray:
    """Piecewise-linear colour ramp over the value grid. Returns (H, W, 4) uint8."""
    xs = np.array([s[0] for s in STOPS])
    rgba = np.array([s[1] for s in STOPS], dtype=float)
    out = np.empty(ug.shape + (4,), dtype=np.uint8)
    flat = np.clip(ug, xs[0], xs[-1]).ravel()
    for c in range(4):
        out[..., c] = np.interp(flat, xs, rgba[:, c]).reshape(ug.shape).round().astype(np.uint8)
    return out


def to_png(ug: np.ndarray, upscale: int = UPSCALE, blur: float = 1.2, colors: int = 96) -> bytes:
    """`ug` has row 0 at the southern edge; the image has north at the top.

    The frame is quantised to a small palette (with alpha) before saving: 61 frames are preloaded by every visitor,
    and a palette PNG is 4-6x smaller than true colour with no visible difference on a dark map.
    """
    img = Image.fromarray(colorize(ug[::-1]), mode="RGBA")
    if upscale > 1:
        img = img.resize((img.width * upscale, img.height * upscale), Image.Resampling.BICUBIC)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if colors:
        img = img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
