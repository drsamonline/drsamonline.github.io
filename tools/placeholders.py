"""Branded placeholder thumbnails for the showcase hub.

Used in two places:

* by ``tools/capture_shots.py`` when a live capture fails or times out, so that
  every card always has *some* local image (and never a third-party request);
* as the initial committed set of ``assets/shots/<repo>.webp`` so the directory
  exists and the page is fast from the very first deploy.

Placeholders are deliberately quiet and neutral — no emoji, no saturated colour —
so they read as an intentional "no preview" tile rather than a broken image.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 600, 375

# Calm, neutral palette (matches the light theme's surface tokens).
BG_TOP = (238, 240, 244)
BG_BOTTOM = (229, 232, 238)
TILE = (255, 255, 255)
TILE_LINE = (222, 226, 233)
INK = (60, 67, 79)
FAINT = (125, 133, 149)
ACCENT = (47, 86, 214)

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def _fit(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "\u2026", font=font) > max_w:
        text = text[:-1]
    return text + "\u2026"


def make_placeholder(name: str, out_path: str) -> str:
    """Render a neutral branded tile for *name* and save it as WebP."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_TOP)
    draw = ImageDraw.Draw(img)

    # Subtle vertical gradient.
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        r = round(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Centred rounded tile.
    tw, th = 150, 150
    tx, ty = (WIDTH - tw) // 2, 74
    draw.rounded_rectangle([tx, ty, tx + tw, ty + th], radius=28, fill=TILE, outline=TILE_LINE, width=2)

    initial = (name or "?").strip()[:1].upper() or "?"
    big = _font(78)
    ib = draw.textbbox((0, 0), initial, font=big)
    draw.text((tx + (tw - (ib[2] - ib[0])) / 2 - ib[0],
               ty + (th - (ib[3] - ib[1])) / 2 - ib[1]), initial, font=big, fill=ACCENT)

    # Project name + label.
    nf = _font(30)
    name_txt = _fit(draw, name or "", nf, WIDTH - 120)
    nb = draw.textbbox((0, 0), name_txt, font=nf)
    draw.text(((WIDTH - (nb[2] - nb[0])) / 2 - nb[0], ty + th + 34), name_txt, font=nf, fill=INK)

    lf = _font(19)
    label = "preview unavailable"
    lb = draw.textbbox((0, 0), label, font=lf)
    draw.text(((WIDTH - (lb[2] - lb[0])) / 2 - lb[0], ty + th + 80), label, font=lf, fill=FAINT)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path, "WEBP", quality=80, method=6)
    return out_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        print(make_placeholder(sys.argv[1], sys.argv[2]))
