"""skia helpers: variable fonts, easing, paints, text layout, shapes."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import skia

from config import FONTS

FONT_FILES = {
    "inter": FONTS / "inter" / "Inter[opsz,wght].ttf",
    "archivo": FONTS / "archivo" / "Archivo[wdth,wght].ttf",
    "mono": FONTS / "jetbrainsmono" / "JetBrainsMono[wght].ttf",
}
_KEEP = []   # Coordinates / VariationPosition objects must outlive makeClone


def _tag(s: str) -> int:
    return int.from_bytes(s.encode("ascii"), "big")


@lru_cache(maxsize=None)
def _base(family: str):
    return skia.Typeface.MakeFromFile(str(FONT_FILES[family]))


@lru_cache(maxsize=4096)
def typeface(family: str, axes: tuple = ()):
    base = _base(family)
    if not axes:
        return base
    coords = skia.FontArguments.VariationPosition.Coordinates(
        [skia.FontArguments.VariationPosition.Coordinate(_tag(k), float(v)) for k, v in axes])
    pos = skia.FontArguments.VariationPosition(coords)
    args = skia.FontArguments()
    args.setVariationDesignPosition(pos)
    tf = base.makeClone(args)
    _KEEP.append((coords, pos, args))
    return tf


def font(family: str, size: float, **axes) -> skia.Font:
    q = {"wght": 10, "wdth": 1, "opsz": 1}
    ax = tuple(sorted((k, round(v / q.get(k, 1)) * q.get(k, 1)) for k, v in axes.items()))
    f = skia.Font(typeface(family, ax), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    f.setHinting(skia.FontHinting.kNone)
    f.setLinearMetrics(True)
    return f


@lru_cache(maxsize=512)
def _cap_ratio(family: str, ax: tuple) -> float:
    f = skia.Font(typeface(family, ax), 1000)
    b = f.getBounds(f.textToGlyphs("H"))[0]
    return -b.top() / 1000


def cap_font(family: str, cap_px: float, **axes) -> skia.Font:
    """Font sized so capital height == cap_px."""
    q = {"wght": 10, "wdth": 1, "opsz": 1}
    ax = tuple(sorted((k, round(v / q.get(k, 1)) * q.get(k, 1)) for k, v in axes.items()))
    return font(family, cap_px / _cap_ratio(family, ax), **axes)


def mono(size: float, wght: float = 450) -> skia.Font:
    return font("mono", size, wght=wght)


# ---------------------------------------------------------------- easing
def clamp(u, a=0.0, b=1.0):
    return a if u < a else b if u > b else u


def lin(u):
    return clamp(u)


def smooth(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def io_cubic(u):
    u = clamp(u)
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def io_quint(u):
    u = clamp(u)
    return 16 * u ** 5 if u < 0.5 else 1 - (-2 * u + 2) ** 5 / 2


def io_expo(u):
    u = clamp(u)
    if u <= 0 or u >= 1:
        return u
    return 2 ** (20 * u - 10) / 2 if u < 0.5 else (2 - 2 ** (-20 * u + 10)) / 2


def out_expo(u):
    u = clamp(u)
    return 1.0 if u >= 1 else 1 - 2 ** (-10 * u)


def in_expo(u):
    u = clamp(u)
    return 0.0 if u <= 0 else 2 ** (10 * u - 10)


def out_cubic(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def in_cubic(u):
    u = clamp(u)
    return u ** 3


def out_back(u, s=1.70158):
    u = clamp(u)
    return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2


def in_back(u, s=1.70158):
    u = clamp(u)
    return (s + 1) * u ** 3 - s * u ** 2


def out_elastic(u, p=0.36):
    u = clamp(u)
    if u <= 0 or u >= 1:
        return u
    return 2 ** (-10 * u) * math.sin((u - p / 4) * 2 * math.pi / p) + 1


def span(u, a, b, ease=lin):
    """eased 0..1 progress of u through [a, b]."""
    return ease((u - a) / (b - a)) if b != a else float(u >= b)


def mix(a, b, u):
    return a + (b - a) * u


def mixc(c1, c2, u):
    return tuple(int(round(mix(x, y, clamp(u)))) for x, y in zip(c1, c2))


# ---------------------------------------------------------------- paints
def paint(color, alpha=255, stroke=0.0, aa=True, blend=None):
    p = skia.Paint(AntiAlias=aa, Color=skia.Color(*color[:3], alpha))
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
    if blend is not None:
        p.setBlendMode(blend)
    return p


def fill(c: skia.Canvas, color):
    c.drawColor(skia.Color(*color[:3], 255))


# ---------------------------------------------------------------- text
def text_width(txt: str, f: skia.Font, tracking: float = 0.0) -> float:
    if not txt:
        return 0.0
    g = f.textToGlyphs(txt)
    return float(sum(f.getWidths(g))) + tracking * (len(txt) - 1)


def glyph_advances(txt: str, f: skia.Font, tracking: float = 0.0):
    g = f.textToGlyphs(txt)
    w = f.getWidths(g)
    xs, x = [], 0.0
    for a in w:
        xs.append(x)
        x += a + tracking
    return xs, list(w)


def glyph_bounds(ch: str, f: skia.Font) -> skia.Rect:
    return f.getBounds(f.textToGlyphs(ch))[0]


def draw_text(c, txt, x, y, f, color, alpha=255, tracking=0.0, align="left"):
    """y is the baseline."""
    w = text_width(txt, f, tracking)
    if align == "right":
        x -= w
    elif align == "center":
        x -= w / 2
    p = paint(color, alpha)
    if tracking == 0.0:
        c.drawString(txt, x, y, f, p)
    else:
        xs, _ = glyph_advances(txt, f, tracking)
        for ch, dx in zip(txt, xs):
            c.drawString(ch, x + dx, y, f, p)
    return w


def type_on(txt: str, u: float, scramble: bool = True, seed: int = 0) -> str:
    """Letter-by-letter decode: u in 0..1 -> revealed prefix + scrambled next chars."""
    n = len(txt)
    k = int(clamp(u) * n + 1e-6)
    if k >= n:
        return txt
    rng = np.random.default_rng(seed + k)
    tail = ""
    if scramble and k < n:
        pool = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789/+-_#"
        m = min(3, n - k)
        tail = "".join(pool[i] for i in rng.integers(0, len(pool), m))
    return txt[:k] + tail


# ---------------------------------------------------------------- glow
def glow_layer(c, sigma: float, strength: int = 200):
    """with glow_layer(...) draw; -> blurred copy added (kPlus) under the crisp redraw."""
    p = skia.Paint(ImageFilter=skia.ImageFilters.Blur(sigma, sigma), BlendMode=skia.BlendMode.kPlus,
                   Color=skia.Color(255, 255, 255, strength))
    c.saveLayer(paint=p)


# ---------------------------------------------------------------- shapes
def cross_path(cx, cy, arm, thick, rot=0.0) -> skia.Path:
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(-arm, -thick / 2, arm, thick / 2))
    p.addRect(skia.Rect.MakeLTRB(-thick / 2, -arm, thick / 2, arm))
    p.setFillType(skia.PathFillType.kWinding)
    m = skia.Matrix()
    m.setRotate(rot)
    m.postTranslate(cx, cy)
    p.transform(m)
    return p


def star_path(cx, cy, r_out, r_in, points=8, rot=0.0) -> skia.Path:
    p = skia.Path()
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot) + math.pi * i / points - math.pi / 2
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        (p.moveTo if i == 0 else p.lineTo)(x, y)
    p.close()
    return p


def circle_path(cx, cy, r) -> skia.Path:
    p = skia.Path()
    p.addCircle(cx, cy, max(r, 0.0))
    return p


def rect(x0, y0, x1, y1) -> skia.Rect:
    return skia.Rect.MakeLTRB(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def reg_mark(c, x, y, color, s=14, alpha=255):
    p = paint(color, alpha, stroke=1.0)
    c.drawLine(x - s, y, x + s, y, p)
    c.drawLine(x, y - s, x, y + s, p)
    c.drawCircle(x, y, s * 0.55, p)


def crosshair(c, x, y, color, s=26, gap=6, alpha=255, w=1.0):
    p = paint(color, alpha, stroke=w)
    c.drawLine(x - s, y, x - gap, y, p)
    c.drawLine(x + gap, y, x + s, y, p)
    c.drawLine(x, y - s, x, y - gap, p)
    c.drawLine(x, y + gap, x, y + s, p)
