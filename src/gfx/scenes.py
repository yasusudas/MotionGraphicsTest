"""The ten compositions, their transitions and the peripheral metadata layer.

Every scene is ``draw_Sx(c, b, X)`` with ``b`` = global beat (float, 0.5 s each) and
``u = b - b0`` its local beat.  Transitions are driven by elements already on screen:

  S1->S2  the red grid point expands into a circle wipe
  S2->S3  the O of MOTION zooms and match-cuts into the radial ring
  S3->S4  halftone gaps grow into black bars that merge into the next field
  S4->S5  RHYTHM collapses into a line, the line opens as a band
  S5->S6  the chrome torus faces camera and its hole irises open onto S6
  S6->S7  the specimen's "+" mark grows into a cross-shaped wipe
  S7->S8  the crosses' arms extend into stripes that merge
  S8->S9  the wave lines straighten and thicken; their gaps become S9's rules
  S9->S10 the rules cascade to black; the glass sphere shrinks into the period of OPUS.
"""
from __future__ import annotations

import math

import numpy as np
import skia

import layout as L
from config import BEAT, BLACK, COBALT, FPS, H, LIME, PAPER, RED, SCENES, W
from gfx.draw import (cap_font, circle_path, clamp, cross_path, crosshair, draw_text, font, glow_layer,
                      glyph_advances, in_back, in_cubic, in_expo, io_cubic, io_expo, io_quint, lin, mix,
                      mono, out_back, out_cubic, out_elastic, out_expo, paint, reg_mark, smooth, span,
                      star_path, text_width, type_on)

CX, CY = W / 2, H / 2
col, row = L.col, L.row


def rgb(c):
    return skia.Color(*c[:3], 255)


def step8(u, frac=0.55, ease=io_cubic):
    """stepped motion: one eased step per 8th note, holding between steps."""
    k = math.floor(u * 2)
    return k + ease(((u * 2) - k) / frac)


# ================================================================ S1 POINT
S1_RULES = [("h", 540), ("v", col(8)), ("v", col(0)), ("h", 312), ("h", 852), ("v", col(4)),
            ("v", 1824), ("h", 72), ("h", 1008), ("v", col(10)), ("v", col(2))]


def draw_S1(c, b, X):
    u = b
    c.drawColor(rgb(PAPER))
    dx, dy = L.S1_DOT
    ink = BLACK
    # grid rules shoot out of the point on each tick
    ticks = X.times("tick", variant="rule")
    for (kind, pos), t0 in zip(S1_RULES, ticks):
        p = span(u, t0 / BEAT, t0 / BEAT + 0.45, out_expo)
        if p <= 0:
            continue
        pt = paint(ink, 200, stroke=1.0)
        if kind == "h":
            c.drawLine(dx - p * (dx + 10), pos, dx + p * (W - dx + 10), pos, pt)
        else:
            c.drawLine(pos, dy - p * (dy + 10), pos, dy + p * (H - dy + 10), pt)
        # tiny index at the far end of each rule
        if p > 0.9:
            lab = f"{S1_RULES.index((kind, pos)) + 1:02d}"
            if kind == "h":
                draw_text(c, lab, 1830 + 6, pos - 4, mono(10), ink, 200)
            else:
                draw_text(c, lab, pos + 4, 66, mono(10), ink, 200)
    # GRID: revealed column by column, letters rising out of the baseline mask
    word, base, x0 = "GRID", 852, col(0) - 8
    fnt = cap_font("inter", 540, wght=900, opsz=32)
    fit = (dx - 70 - x0) / text_width(word, fnt, -8)
    fnt = cap_font("inter", 540 * min(1.0, fit), wght=900, opsz=32)
    wd = text_width(word, fnt, -8)
    reveals = X.times("reveal")
    strip = wd / len(reveals)
    for i, t0 in enumerate(reveals):
        p = span(u, t0 / BEAT, t0 / BEAT + 0.5, out_expo)
        if p <= 0:
            continue
        c.save()
        c.clipRect(skia.Rect.MakeLTRB(x0 + i * strip, 0, x0 + (i + 1) * strip + 1, base + 1))
        draw_text(c, word, x0, base + (1 - p) * 600, fnt, ink, tracking=-8)
        c.restore()
    # the point, its crosshair and coordinates
    r = L.S1_DOT_R * out_elastic(span(u, 0.0, 0.5))
    r *= 1 - 0.35 * span(u, 3.3, 3.5, in_cubic)          # anticipation before the wipe
    ch = span(u, 0.25, 0.7, out_expo)
    if ch > 0:
        crosshair(c, dx, dy, ink, s=26 + 34 * ch, gap=r + 8, alpha=230)
    c.drawCircle(dx, dy, r, paint(RED))
    lab_u = span(u, 0.35, 1.1)
    if lab_u > 0:
        draw_text(c, type_on("P.01", lab_u, seed=1), dx + 44, dy - 44, mono(13, 600), ink)
        draw_text(c, type_on(f"X {dx:.0f}  Y {dy:.0f}", lab_u, seed=2), dx + 44, dy - 26, mono(12), ink)
    cap_u = span(u, 2.2, 3.1)
    if cap_u > 0:
        draw_text(c, type_on("FIG. 01 — THE POINT GENERATES THE GRID", cap_u, seed=3), col(0), base + 40, mono(13), ink)
        draw_text(c, type_on("12 COL / 8 ROW / 24 PX GUTTER", cap_u, seed=4), col(4), base + 40, mono(13), ink)


def mask_S1_S2(b):
    u = span(b, 3.5, 4.0)
    r = 14 + in_expo(u) * 2350
    return circle_path(*L.S1_DOT, r)


# ================================================================ S2 MOTION
S2_ROWS = 7


def s2_center_state(u):
    """collapse progress and zoom progress for the centre row."""
    col_p = span(u, 1.45, 2.35, io_expo)
    zoom_p = span(u, 2.35, 2.93, in_expo)      # complete on the last frame before the cut
    return col_p, zoom_p


def draw_S2(c, b, X):
    u = b - 4.0
    c.drawColor(rgb(RED))
    rh = H / S2_ROWS
    col_p, zoom_p = s2_center_state(u)
    word = "MOTION"
    for r in (0, 1, 2, 4, 5, 6, 3):          # centre row drawn last
        center = r == 3
        dirn = 1 if r % 2 else -1
        wdth = 62 + 63 * (0.5 + 0.5 * math.sin(r * 1.3 + step8(u) * 0.9))
        cap = rh * 0.74
        if center:
            wdth = mix(wdth, 100, col_p)
            cap = mix(cap, 330, col_p)
        else:
            # outer rows squash to nothing, outermost first
            k = abs(r - 3)
            sq = span(u, 1.45 + (3 - k) * 0.08, 2.1 + (3 - k) * 0.08, io_expo)
            if sq >= 1:
                continue
        fnt = cap_font("archivo", cap, wght=900, wdth=wdth)
        unit = word + " "
        uw = text_width(unit, fnt)
        yc = (r + 0.5) * rh
        if not center:
            yc = mix(yc, CY + (r - 3) * 18, span(u, 1.45, 2.2, io_expo))
        base = yc + cap / 2
        entry = (1 - span(u, -0.6 + r * 0.05, 0.25 + r * 0.05, out_expo)) * W * dirn
        off = dirn * step8(u) * uw / 3 + entry
        color = PAPER if center else BLACK
        c.save()
        if not center:
            c.translate(0, yc)
            c.scale(1, 1 - sq)
            c.translate(0, -yc)
        if center and col_p > 0:
            # centre one MOTION instance on the frame as the row grows
            wf = text_width(word, fnt)
            target = CX - wf / 2
            start = (off % uw) - uw * 3
            x = mix(start + uw * 3, target, col_p)
            if zoom_p <= 0:
                draw_text(c, word, x, base, fnt, color)
                for j in (1, 2, 3):
                    draw_text(c, word, x + j * uw, base, fnt, color)
                    draw_text(c, word, x - j * uw, base, fnt, color)
            else:
                draw_s2_zoom(c, word, x, base, fnt, zoom_p)
            c.restore()
            continue
        x = (off % uw) - uw * 2
        while x < W + uw:
            draw_text(c, unit, x, base, fnt, color)
            x += uw
        c.restore()
    # labels
    lu = span(u, 0.2, 1.0)
    if lu > 0 and col_p < 1:
        draw_text(c, type_on("KINETIC STUDY 02 — REPETITION / STRETCH / STEP", lu, seed=5), col(0), 44 + 1030, mono(12), PAPER)


S3_RING = (440, 250)        # outer / inner radius at the cut: the zoomed O lands here


def draw_s2_zoom(c, word, x, base, fnt, z):
    """letters fly apart, the first O scales about its centre onto the S3 ring."""
    xs, ws = glyph_advances(word, fnt)
    io = word.index("O")
    ob = fnt.getBounds(fnt.textToGlyphs("O"))[0]
    ocx = x + xs[io] + (ob.left() + ob.right()) / 2
    ocy = base + (ob.top() + ob.bottom()) / 2
    oh = ob.height()
    s = mix(1.0, 2 * S3_RING[0] / oh, z)
    for i, ch in enumerate(word):
        if i == io:
            continue
        push = (-1 if i < io else 1) * in_expo(z) * 1400
        draw_text(c, ch, x + xs[i] + push, base, fnt, PAPER)
    c.save()
    tx, ty = mix(ocx, CX, z), mix(ocy, CY, z)
    c.translate(tx, ty)
    c.scale(s, s)
    c.translate(-ocx, -ocy)
    draw_text(c, "O", x + xs[io], base, fnt, PAPER)
    c.restore()


# ================================================================ S3 RADIAL
def draw_S3(c, b, X):
    u = b - 7.0
    c.drawColor(rgb(COBALT))
    ink = PAPER
    # halftone field with a travelling wave
    sp = 60
    front = span(u, 0.6, 2.0, out_cubic) * 1500
    bars = span(u, 2.45, 3.0)
    music = X.env("music", b * BEAT)
    xs = np.arange(sp / 2, W, sp)
    ys = np.arange(sp / 2, H, sp)
    gx, gy = np.meshgrid(xs, ys)
    d = np.hypot(gx - CX, gy - CY)
    wave = 0.5 + 0.5 * np.sin(d * 0.013 - u * 6.0)
    rr = (2.5 + (9 + 5 * music) * wave) * np.clip((front - d) / 160, 0, 1)
    rr *= (d > 470) * (1 - span(u, 2.5, 2.9, in_cubic))
    p = paint(ink)
    for x, y, r in zip(gx.ravel(), gy.ravel(), rr.ravel()):
        if r > 0.3:
            c.drawCircle(float(x), float(y), float(r), p)
    # ring -> disk
    ro = mix(S3_RING[0], 300, span(u, 0.0, 0.35, out_back))
    ri = S3_RING[1] * (1 - span(u, 0.05, 0.4, out_expo))
    shrink = span(u, 0.55, 1.0, io_cubic)
    ro = mix(ro, 64, shrink)
    ro *= 1 - span(u, 2.5, 2.8, in_back)
    ring = skia.Path()
    ring.addCircle(CX, CY, max(ro, 0))
    if ri > 0.5:
        ring.addCircle(CX, CY, ri)
        ring.setFillType(skia.PathFillType.kEvenOdd)
    c.drawPath(ring, paint(ink))
    # radial burst
    burst = span(u, 0.0, 0.3, out_expo) * (1 - span(u, 0.55, 1.1, in_cubic))
    if burst > 0:
        rng = np.random.default_rng(3)
        lens = 170 + 230 * rng.random(48)
        pr = paint(ink, stroke=2.0)
        rot = u * 8
        for i in range(48):
            a = math.radians(rot + i * 7.5)
            r0, r1 = 330, 330 + lens[i] * burst
            c.drawLine(CX + r0 * math.cos(a), CY + r0 * math.sin(a), CX + r1 * math.cos(a), CY + r1 * math.sin(a), pr)
    # orbiting nodes (stepped rotation on 8ths)
    nodes = span(u, 0.45, 0.9, out_back) * (1 - span(u, 2.45, 2.8, in_back))
    if nodes > 0:
        ang0 = step8(u - 0.5) * 15
        for i in range(24):
            a = math.radians(ang0 + i * 15)
            s = span(u, 0.45 + i * 0.012, 0.85 + i * 0.012, out_back) * nodes
            c.drawCircle(CX + 300 * math.cos(a), CY + 300 * math.sin(a), 13 * s, paint(ink))
    # type on a circle: big grotesk running around the system
    tu = span(u, 0.6, 1.6)
    if tu > 0 and bars < 1:
        txt = "RADIAL SYSTEM · 48 RAYS · 24 NODES · "
        shown = type_on(txt, tu, scramble=False)
        fnt = cap_font("inter", 30, wght=800, opsz=32)
        rad = 395
        rot = -90 + u * 11 + step8(u) * 2
        ang = rot
        for ch in shown:
            w = text_width(ch, fnt)
            c.save()
            c.translate(CX, CY)
            c.rotate(ang + math.degrees(w / 2 / rad))
            c.translate(0, -rad)
            draw_text(c, ch, -w / 2, 0, fnt, ink, 255 if bars <= 0 else int(255 * (1 - bars)))
            c.restore()
            ang += math.degrees((w + 2) / rad)
    lu = span(u, 1.0, 1.8)
    if lu > 0:
        draw_text(c, type_on("FIG. 03", lu, seed=7), col(0), row(0) + 12, mono(13, 600), ink)
        draw_text(c, type_on("RADIAL / HALFTONE / ORBIT", lu, seed=8), col(0), row(0) + 30, mono(12), ink)
        draw_text(c, type_on("λ 480 PX  ·  ω 6.0 RAD/BEAT", lu, seed=9), col(0), row(0) + 48, mono(12), ink)
    # exit: black bars grow in the halftone gaps and merge
    if bars > 0:
        pb = paint(BLACK)
        for k, x in enumerate(np.arange(0, W + sp, sp)):
            delay = abs(x - CX) / CX * 0.35
            hp = in_expo(clamp((bars - delay * 0.4) / 0.6))
            wp = span(bars, 0.6, 1.0, in_cubic)
            hh = hp * H * 0.52
            ww = 3 + wp * (sp + 2)
            if hh > 0:
                c.drawRect(skia.Rect.MakeLTRB(x - ww / 2, CY - hh, x + ww / 2, CY + hh), pb)


# ================================================================ S4 RHYTHM
def s4_letters(b, X):
    u = b - 10.0
    word = "RHYTHM"
    hits = X.times("letter")
    toms = X.times("tom")
    state = []
    for i, ch in enumerate(word):
        imp = 0.0
        if i < len(hits):
            dt = b * BEAT - hits[i]
            if dt >= 0:
                imp = max(imp, math.exp(-dt / 0.16))
        for j, tt in enumerate(toms[:3]):
            if (j * 2 + 1) % 6 == i:
                dt = b * BEAT - tt
                if dt >= 0:
                    imp = max(imp, 0.7 * math.exp(-dt / 0.14))
        band = X.spec(b * BEAT, 6 + i * 6, 12 + i * 6)
        state.append((ch, imp, band))
    return u, word, state


def draw_S4(c, b, X):
    u, word, state = s4_letters(b, X)
    c.drawColor(rgb(BLACK))
    ink = PAPER
    base = 760
    stut = span(u, 1.5, 1.75)
    collapse = span(u, 1.72, 2.0, in_expo)
    if 0 < stut < 1:
        k = int((u - 1.5) / 0.0625)
        jitter = [0, 14, -10, 22, -18, 6, -24, 12][k % 8]
    else:
        jitter = 0
    cap = 430
    # per-letter width axis responds to its hit: typographic morph
    fonts, widths = [], []
    for ch, imp, band in state:
        wd = 70 + 55 * imp + 10 * band
        f = cap_font("archivo", cap, wght=900, wdth=min(wd, 125))
        fonts.append(f)
        widths.append(text_width(ch, f))
    gap = 6
    total = sum(widths) + gap * (len(widths) - 1)
    fitk = min(1.0, (W - 2 * L.M) / total)
    c.save()
    c.translate(CX, base)
    c.scale(fitk, fitk)
    c.translate(-CX, -base)
    x = CX - total / 2 + jitter
    lime_x = None
    last_hit = -1
    for i, (ch, imp, band) in enumerate(state):
        if imp > 0.25:
            last_hit = i
    for i, ((ch, imp, band), f, w) in enumerate(zip(state, fonts, widths)):
        rise = span(u, 0.0 + i * 0.045, 0.3 + i * 0.045, out_expo)
        sy = (1 + 0.55 * imp + 0.12 * band) * (1 - collapse * 0.995)
        c.save()
        c.clipRect(skia.Rect.MakeLTRB(-W, -H, 2 * W, base + 2 if collapse <= 0 else 2 * H))
        yc = CY if collapse > 0 else base
        c.translate(x, yc)
        c.scale(1, sy)
        c.translate(0, base - yc + (1 - rise) * cap * 1.2)
        draw_text(c, ch, 0, 0, f, ink)
        c.restore()
        if i == last_hit:
            lime_x = (x + w / 2, base - cap * sy - 44)
        x += w + gap
    c.restore()
    total *= fitk
    if lime_x is not None:
        lime_x = (CX + (lime_x[0] - CX) * fitk, base + (lime_x[1] - base) * fitk)
    # the collapsed line extends to the full width
    if collapse > 0:
        lw = mix(total, W + 20, span(u, 1.85, 2.0, io_quint))
        hh = max(3.0, (1 - collapse) * 40)
        c.drawRect(skia.Rect.MakeLTRB(CX - lw / 2, CY - hh, CX + lw / 2, CY + hh), paint(ink))
    # lime accents: marker over the last hit letter + beat progress underline
    if collapse <= 0:
        glow_layer(c, 10, 170)
        _s4_lime(c, u, lime_x, total, base)
        c.restore()
        _s4_lime(c, u, lime_x, total, base)
        lu = span(u, 0.2, 0.9)
        draw_text(c, type_on("04 — RHYTHM / 16TH GRID / 120 BPM", lu, seed=11), col(0), row(0) + 12, mono(13, 600), LIME)
        draw_text(c, type_on("LETTER WIDTH = HIT VELOCITY", lu, seed=12), col(0), row(0) + 30, mono(12), ink)


def _s4_lime(c, u, lime_x, total, base):
    if lime_x is not None:
        c.drawRect(skia.Rect.MakeXYWH(lime_x[0] - 9, lime_x[1] - 9, 18, 18), paint(LIME))
    prog = clamp(u / 2.0)
    c.drawRect(skia.Rect.MakeLTRB(CX - total / 2, base + 30, CX - total / 2 + total * prog, base + 36), paint(LIME))


def mask_S4_S5(b):
    u = span(b, 12.0, 12.4)
    hh = 3 + out_expo(u) * (H / 2 + 10)
    p = skia.Path()
    p.addRect(skia.Rect.MakeLTRB(-10, CY - hh, W + 10, CY + hh))
    return p


# ================================================================ S5 FORM (+ chrome)
def draw_S5(c, b, X, with_chrome=True):
    u = b - 12.0
    c.drawColor(rgb(PAPER))
    ink = BLACK
    cx, cy = L.S5_CENTER
    ds = span(u, 0.1, 0.55, out_back) * (1 - span(u, 3.0, 3.35, in_back))
    if ds > 0:
        c.drawCircle(cx, cy, L.S5_DISC_R * ds, paint(COBALT))
    # FORM — rising out of the baseline, flipping letter by letter on 14.5
    fnt = cap_font("inter", 420, wght=900, opsz=32)
    base = 1008
    xs, ws = glyph_advances("FORM", fnt, -10)
    for i, ch in enumerate("FORM"):
        rise = span(u, 0.25 + i * 0.07, 0.75 + i * 0.07, out_expo)
        drop = span(u, 3.05 + i * 0.05, 3.45 + i * 0.05, in_expo)
        flip = math.cos(2 * math.pi * span(u, 2.5 + i * 0.06, 2.9 + i * 0.06, io_cubic))
        if rise <= 0:
            continue
        c.save()
        c.clipRect(skia.Rect.MakeLTRB(0, 0, W, base + 1))
        yc = base - 210
        c.translate(col(0) - 12 + xs[i], yc)
        c.scale(1, flip)
        c.translate(0, base - yc + (1 - rise) * 460 + drop * 460)
        draw_text(c, ch, 0, 0, fnt, ink)
        c.restore()
    # annotations
    au = span(u, 0.8, 1.6)
    ex = span(u, 2.95, 3.2)
    if au > 0 and ex < 1:
        a = int(255 * (1 - ex))
        lx = span(u, 0.8, 1.2, out_expo)
        # dimension line over the disc
        y = cy - L.S5_DISC_R - 34
        x0, x1 = cx - L.S5_DISC_R, cx + L.S5_DISC_R
        pl = paint(ink, a, stroke=1.0)
        c.drawLine(cx - (cx - x0) * lx, y, cx + (x1 - cx) * lx, y, pl)
        c.drawLine(x0, y - 7, x0, y + 7, pl)
        c.drawLine(x1, y - 7, x1, y + 7, pl)
        draw_text(c, type_on(f"Ø {2 * L.S5_DISC_R} PX", au, seed=13), cx, y - 10, mono(12), ink, a, align="center")
        # leader to the object
        tx, ty = cx - 290, cy - 120                      # a point on the torus' left flank
        lx2, ly2 = col(4) + L.CW, row(1) + 30            # label block in the empty upper-left field
        c.drawLine(tx, ty, mix(tx, lx2, lx), mix(ty, ly2, lx), pl)
        c.drawCircle(tx, ty, 3.5, paint(ink, a))
        c.drawLine(lx2, ly2, lx2 - 262 * lx, ly2, pl)
        for k, line in enumerate(["OBJ.01 — CHROME", "TORUS R1.90 / r0.62", "SECTION n=3.4 · TWIST 180°"]):
            draw_text(c, type_on(line, au, seed=14 + k), lx2 - 262, ly2 + 20 + k * 17, mono(12, 600 if k == 0 else 450), ink, a)
        draw_text(c, type_on("FIG. 05 — FORM FOLLOWS RHYTHM", au, seed=20), col(0), row(0) + 12, mono(13, 600), ink, a)
        draw_text(c, type_on("RENDER: CYCLES / ORTHOGRAPHIC 1:1", au, seed=21), col(0), row(0) + 30, mono(12), ink, a)
    if with_chrome:
        X.draw_chrome(c)


def mask_S5_S6(b, X):
    tr = X.chrome_track()
    if tr is None or not tr["facing"] or b < 15.3:
        return None
    return circle_path(tr["x"], tr["y"], tr["mid_px"])


# ================================================================ S6 TYPE
S6_GLYPHS = ["Aa", "Gg", "Rr", "Qq", "Ee"]
S6_PLUS = (col(8) - 70, CY)


def s6_weight(u):
    k = math.floor(u)
    a, bb = (900, 180) if k % 2 == 0 else (180, 900)
    return mix(a, bb, span(u - k, 0.0, 0.3, io_expo))


def draw_S6(c, b, X):
    u = b - 16.0
    c.drawColor(rgb(RED))
    ink, acc = PAPER, BLACK
    wght = s6_weight(u)
    flips = X.times("flip")
    idx, fx = 0, 1.0
    for i, t0 in enumerate(flips):
        p = span(b, t0 / BEAT - 0.12, t0 / BEAT + 0.12, io_cubic)
        if p > 0:
            idx = i if p >= 0.5 else max(i - 1, 0)
            if p < 1:
                fx = abs(math.cos(math.pi * p))
    glyphs = S6_GLYPHS[min(idx, len(S6_GLYPHS) - 1)]
    widest = text_width(glyphs, cap_font("archivo", 560, wght=900, wdth=100), -10)
    fnt = cap_font("archivo", 560 * min(1.0, (S6_PLUS[0] - 60 - col(0)) / widest), wght=wght, wdth=100)
    base = 852
    w = text_width(glyphs, fnt, -10)
    c.save()
    gx = col(0) - 10
    c.translate(gx + w / 2, 0)
    c.scale(max(fx, 0.02), 1)
    c.translate(-(gx + w / 2), 0)
    draw_text(c, glyphs, gx, base, fnt, ink, tracking=-10)
    c.restore()
    # specimen column
    x0 = col(8)
    lu = span(u, -0.3, 0.8)
    draw_text(c, type_on("ARCHIVO VARIABLE", lu, seed=30), x0, row(0) + 12, mono(13, 600), ink)
    draw_text(c, type_on("wght 100—900 · wdth 62—125", lu, seed=31), x0, row(0) + 30, mono(12), ink)
    small = font("archivo", 40, wght=wght, wdth=100)
    for k, line in enumerate(["ABCDEFGHIJKLM", "NOPQRSTUVWXYZ", "abcdefghijklm", "0123456789&?!"]):
        draw_text(c, type_on(line, span(u, 0.0 + k * 0.1, 0.6 + k * 0.1), scramble=False), x0, row(1) + 40 + k * 52, small, ink)
    # weight scale with a black indicator
    ys = row(4) + 20
    for k, wv in enumerate(range(100, 1000, 100)):
        yy = ys + k * 22
        draw_text(c, f"{wv}", x0, yy, mono(12), ink)
        c.drawLine(x0 + 44, yy - 4, x0 + 44 + 200, yy - 4, paint(ink, 90, stroke=1))
    ind = ys + (wght - 100) / 100 * 22
    c.drawRect(skia.Rect.MakeXYWH(x0 + 44, ind - 9, 200 * (wght - 100) / 800 + 4, 10), paint(acc))
    draw_text(c, f"{wght:5.0f}", x0 + 260, ind, mono(12, 700), acc)
    # accent block + the "+" mark that becomes the next wipe
    c.drawRect(skia.Rect.MakeXYWH(col(11), row(0), L.CW, L.CW * span(u, 0.1, 0.5, out_expo)), paint(acc))
    pl = 16 + 6 * X.imp("kick", b * BEAT, 0.1)
    c.drawPath(cross_path(*S6_PLUS, pl, 6, 0), paint(acc))


def mask_S6_S7(b):
    u = span(b, 18.55, 19.0)
    if u <= 0:
        return None
    arm = 22 + in_expo(u) * 2200
    thick = 6 + in_expo(span(b, 18.7, 19.0)) * 1700
    return cross_path(*S6_PLUS, arm, thick, 45 * io_cubic(u))


# ================================================================ S7 SIGN
def draw_S7(c, b, X):
    u = b - 19.0
    c.drawColor(rgb(BLACK))
    ink, acc = RED, PAPER
    rots = X.times("rotate")
    sp = 128
    nx, ny = 15, 9
    ox = CX - (nx - 1) * sp / 2
    oy = CY - (ny - 1) * sp / 2
    ext = span(u, 2.35, 2.8, in_expo)          # horizontal arms extend into stripes
    band = span(u, 2.6, 3.0, in_cubic)
    title = cap_font("inter", 300, wght=900, opsz=32)
    tw = text_width("SIGN", title, -6)
    tbox = skia.Rect.MakeLTRB(col(0) - 20, row(0) - 20, col(0) + tw + 30, row(0) + 330)
    glow_layer(c, 7, 150)
    _s7_crosses(c, b, u, rots, sp, nx, ny, ox, oy, ext, tbox, ink)
    c.restore()
    _s7_crosses(c, b, u, rots, sp, nx, ny, ox, oy, ext, tbox, ink)
    if band > 0:
        for j in range(ny):
            y = oy + j * sp
            hh = 3 + band * (sp / 2 + 2)
            c.drawRect(skia.Rect.MakeLTRB(0, y - hh, W, y + hh), paint(COBALT))
    if band >= 1:
        return
    # central asterisk star
    kick = X.imp("kick", b * BEAT, 0.12)
    sr = (170 + 26 * kick) * span(u, -0.4, 0.0, out_back) * (1 - ext)
    srot = step8(u) * 22.5
    if sr > 1:
        c.drawPath(star_path(col(8) + L.CW / 2, CY + 60, sr, sr * 0.2, 8, srot), paint(acc))
    # title set into the cleared field
    rise = span(u, -0.3, 0.1, out_expo)
    c.save()
    c.clipRect(skia.Rect.MakeLTRB(0, 0, W, row(0) + 301))
    draw_text(c, "SIGN", col(0) - 8, row(0) + 300 + (1 - rise) * 330 + ext * 400, title, acc, tracking=-6)
    c.restore()
    # sine wave driven by the bass envelope
    bass = X.env("bass", b * BEAT)
    amp = (30 + 70 * bass) * (1 - ext)
    path = skia.Path()
    for k, x in enumerate(np.linspace(0, W, 240)):
        y = 870 + amp * math.sin(x / W * 2 * math.pi * 3 - u * 5)
        (path.moveTo if k == 0 else path.lineTo)(float(x), float(y))
    wv = span(u, 0.2, 0.7, out_expo)
    c.save()
    c.clipRect(skia.Rect.MakeLTRB(0, 0, W * wv, H))
    c.drawPath(path, paint(acc, stroke=2.5))
    c.restore()
    lu = span(u, 0.3, 1.1)
    draw_text(c, type_on("SYM. 07 — CROSS / STAR / WAVE", lu, seed=40), col(8), row(0) + 12, mono(13, 600), acc)
    draw_text(c, type_on("15 × 9 FIELD · ROT 45° / 8TH · RIPPLE 0.4 BEAT", lu, seed=41), col(8), row(0) + 30, mono(12), acc)


def _s7_crosses(c, b, u, rots, sp, nx, ny, ox, oy, ext, tbox, ink):
    pc = paint(ink)
    for j in range(ny):
        for i in range(nx):
            x, y = ox + i * sp, oy + j * sp
            if tbox.contains(x, y):
                continue
            d = math.hypot(x - CX, y - CY)
            appear = span(u, -0.45 + d / 2600, -0.05 + d / 2600, out_back)
            if appear <= 0:
                continue
            rot = 0.0
            for t0 in rots:
                rot += 45 * out_back(clamp((b - t0 / BEAT - d / 2800) / 0.3))
            arm = 22 * appear
            if ext > 0:
                hw = mix(arm, W, ext)
                c.drawRect(skia.Rect.MakeLTRB(x - hw, y - 2.5, x + hw, y + 2.5), pc)
                va = arm * (1 - ext)
                if va > 0.5:
                    c.drawRect(skia.Rect.MakeLTRB(x - 2.5, y - va, x + 2.5, y + va), pc)
                continue
            c.drawPath(cross_path(x, y, arm, 5, rot), pc)
            if (i + j) % 3 == 0:
                c.drawPath(cross_path(x, y, arm * 0.62, 3, rot + 45), pc)


# ================================================================ S8 WAVE
S8_LINES = 16
S8_SP = H / S8_LINES


def draw_S8(c, b, X):
    u = b - 22.0
    c.drawColor(rgb(COBALT))
    ink, acc = PAPER, LIME
    settle = span(u, 1.45, 1.95, io_cubic)
    thick = mix(3.0, S8_SP - 3.0, span(u, 1.5, 2.0, in_cubic))
    amp = (18 + 70 * span(u, 0.0, 1.2, out_cubic) + 40 * X.env("hats", b * BEAT)) * (1 - settle)
    xs = np.linspace(-10, W + 10, 200)
    for k in range(S8_LINES):
        y0 = (k + 0.5) * S8_SP
        ph = k * 0.55
        ys = y0 + amp * np.sin(xs / 640 * 2 * np.pi + ph - u * 7.0)
        path = skia.Path()
        path.moveTo(float(xs[0]), float(ys[0] - thick / 2))
        for x, y in zip(xs, ys):
            path.lineTo(float(x), float(y - thick / 2))
        for x, y in zip(xs[::-1], ys[::-1]):
            path.lineTo(float(x), float(y + thick / 2))
        path.close()
        c.drawPath(path, paint(ink))
    # WAVE riding the same field, letter by letter
    fnt = cap_font("archivo", 380, wght=900, wdth=125)
    xs_, ws_ = glyph_advances("WAVE", fnt, -6)
    fnt = cap_font("archivo", 380 * min(1.0, (W - 2 * L.M) / (xs_[-1] + ws_[-1])), wght=900, wdth=125)
    xs_, ws_ = glyph_advances("WAVE", fnt, -6)
    tw = xs_[-1] + ws_[-1]
    x0 = CX - tw / 2
    for i, ch in enumerate("WAVE"):
        gx = x0 + xs_[i] + ws_[i] / 2
        off = amp * 1.4 * math.sin(gx / 640 * 2 * math.pi - u * 7.0)
        rise = span(u, 0.0 + i * 0.05, 0.3 + i * 0.05, out_expo)
        c.save()
        c.clipRect(skia.Rect.MakeLTRB(0, 0, W, CY + 190 + 120))
        draw_text(c, ch, x0 + xs_[i], CY + 190 + off + (1 - rise) * 500, fnt, ink)
        c.restore()
    if settle < 1:
        a = int(255 * (1 - settle))
        lu = span(u, 0.15, 0.8)
        glow_layer(c, 6, 160)
        _s8_labels(c, u, lu, acc, a, amp)
        c.restore()
        _s8_labels(c, u, lu, acc, a, amp)


def _s8_labels(c, u, lu, acc, a, amp):
    draw_text(c, type_on("08 — WAVE", lu, seed=50), col(0), row(0) + 12, mono(13, 600), acc, a)
    hz = 0.26 * (14000 / 260) ** clamp(u / 2.0)
    draw_text(c, f"LPF {hz:5.2f} kHz · A {amp:5.1f} PX", col(0), row(0) + 30, mono(12), acc, a)
    for k in range(5):
        x = (u * 260 + k * 384) % W
        y = (5 + 0.5) * S8_SP + amp * math.sin(x / 640 * 2 * math.pi + 5 * 0.55 - u * 7.0)
        c.drawCircle(x, y, 7, paint(acc, a))


# ================================================================ S9 LENS (plate) + overlays
def draw_S9(c, b, X):
    u = b - 24.0
    c.drawColor(rgb(PAPER))
    casc = span(u, 3.45, 4.0)
    rule_col = COBALT if casc <= 0 else BLACK
    shift = sum(out_back(clamp((u - k) / 0.25)) for k in (1, 2, 3)) * (S8_SP / 2)
    for k in range(-1, S8_LINES + 2):
        y = k * S8_SP + (shift % S8_SP)
        delay = (S8_LINES - k) * 0.025
        th = 1.5 + in_cubic(clamp((casc - delay) / 0.55)) * (S8_SP / 2 + 1)
        c.drawRect(skia.Rect.MakeLTRB(0, y - th, W, y + th), paint(rule_col))
    fnt = cap_font("inter", 470, wght=900, opsz=32)
    xs, ws = glyph_advances("LENS", fnt, -10)
    base = row(7) + L.RH
    for i, ch in enumerate("LENS"):
        rise = span(u, -0.1 + i * 0.06, 0.35 + i * 0.06, out_expo)
        c.save()
        c.clipRect(skia.Rect.MakeLTRB(0, 0, W, base + 1))
        draw_text(c, ch, col(0) - 14 + xs[i], base + (1 - rise) * 520, fnt, BLACK)
        c.restore()


def overlay_S9(c, b, X):
    u = b - 24.0
    tr = X.glass_track()
    if tr is None or u < 0.3 or u > 3.5:
        return
    ink = BLACK
    a = int(255 * (1 - span(u, 3.2, 3.5)))
    x, y, r = tr["x"], tr["y"], tr["r_px"]
    crosshair(c, x, y, ink, s=16, gap=5, alpha=a)
    au = span(u, 0.35, 1.0)
    lx, ly = min(x + r + 80, 1600), max(y - r - 60, 150)
    k = span(u, 0.35, 0.6, out_expo)
    pl = paint(ink, a, stroke=1.0)
    ex, ey = x + r * 0.72, y - r * 0.72
    c.drawLine(ex, ey, mix(ex, lx, k), mix(ey, ly, k), pl)
    c.drawLine(lx, ly, lx + 150 * k, ly, pl)
    lines = ["OBJ.02 — GLASS", "IOR 1.47 · CYCLES", f"Ø {2 * r:5.0f} PX", f"X {x:6.1f}  Y {y:6.1f}"]
    for i, line in enumerate(lines):
        draw_text(c, type_on(line, au, seed=60 + i) if au < 1 else line, lx, ly + 20 + i * 17,
                  mono(12, 650 if i == 0 else 450), ink, a)
    lu = span(u, 0.2, 0.9)
    draw_text(c, type_on("FIG. 09 — LENS / REFRACTION OF THE GRID", lu, seed=70), col(8), row(0) + 12, mono(13, 600), ink, a)
    draw_text(c, type_on("RULE 3 PX @ 67.5 PX · SPHERE r 180 PX", lu, seed=71), col(8), row(0) + 30, mono(12), ink, a)


# ================================================================ S10 OPUS
def s10_font():
    target = L.S10_DOT[0] - L.S10_DOT_R - 30 - (col(0) - 14)
    f = cap_font("inter", 400, wght=900, opsz=32)
    w = text_width("OPUS", f, -12)
    return cap_font("inter", 400 * target / w, wght=900, opsz=32)


def draw_S10(c, b, X):
    u = b - 28.0
    c.drawColor(rgb(BLACK))
    ink, acc = PAPER, RED
    fnt = s10_font()
    xs, ws = glyph_advances("OPUS", fnt, -12)
    base = L.S10_BASE
    drops = X.times("drop")
    for i, ch in enumerate("OPUS"):
        t0 = drops[i] / BEAT
        p = span(b, t0 - 0.25, t0 + 0.02, in_cubic)
        if p <= 0:
            continue
        land = span(b, t0 + 0.02, t0 + 0.3, out_back)
        sq = (1 - land) * 0.14 if p >= 1 else 0.0
        y = base - (1 - p) * 900
        c.save()
        gx = col(0) - 14 + xs[i]
        c.translate(gx + ws[i] / 2, base)
        c.scale(1 + sq * 0.5, 1 - sq)
        c.translate(-(gx + ws[i] / 2), -base)
        draw_text(c, ch, gx, y, fnt, ink)
        c.restore()
    # the red period (the glass sphere became it at b28)
    pulse = 1 + 0.16 * out_elastic(span(u, 3.0, 3.6)) * (1 - span(u, 3.3, 3.8))
    glow_layer(c, 16, 120)
    c.drawCircle(L.S10_DOT[0], L.S10_DOT[1], L.S10_DOT_R * pulse, paint(acc))
    c.restore()
    c.drawCircle(L.S10_DOT[0], L.S10_DOT[1], L.S10_DOT_R * pulse, paint(acc))
    # lock-up at the final hit
    fu = span(u, 2.0, 2.9)
    if fu > 0:
        k = span(u, 2.0, 2.4, out_expo)
        pl = paint(ink, 220, stroke=1.0)
        y1 = row(2) + 36
        c.drawLine(col(0), y1, col(0) + (1824 - col(0)) * k, y1, pl)
        y2 = base + 46
        c.drawLine(1824 - (1824 - col(0)) * k, y2, 1824, y2, pl)
        draw_text(c, type_on("OPUS — MOTION STUDIES", fu, seed=80), col(0), row(0) + 12, mono(14, 650), ink)
        draw_text(c, type_on("A SHOWREEL IN TEN COMPOSITIONS", fu, seed=81), col(0), row(0) + 32, mono(13), ink)
        draw_text(c, type_on("SWISS / EDITORIAL / KINETIC", fu, seed=82), col(0), row(0) + 50, mono(13), ink)
        items = [f"{i + 1:02d} {s[1]}" for i, s in enumerate(SCENES)]
        for i, it in enumerate(items):
            cx_ = col(7) + (i // 5) * L.CW * 2.4
            cy_ = row(0) + 12 + (i % 5) * 18
            colr = acc if i == 9 else ink
            draw_text(c, type_on(it, span(u, 2.05 + i * 0.04, 2.6 + i * 0.04), seed=90 + i), cx_, cy_, mono(13, 600 if i == 9 else 450), colr)
        foot = ["16.0 SEC", "480 FRAMES", "30 FPS", "120 BPM", "1920 × 1080", "© 2026"]
        for i, it in enumerate(foot):
            draw_text(c, type_on(it, fu, seed=100 + i), col(i * 2), y2 + 34, mono(12), ink)


# ================================================================ metadata / interface layer
def draw_meta(c, b, X):
    sid, name, b0, b1, bg, ink, acc = scene_tuple(b)
    idx = [s[0] for s in SCENES].index(sid) + 1
    t = b * BEAT
    intro = span(b, 0.2, 1.2)
    a = 235
    f12 = mono(12, 500)
    top, bot = 44, 1046
    draw_text(c, type_on("OPUS / MOTION STUDIES 2026", intro, seed=200), col(0), top, f12, ink, a, tracking=1.2)
    draw_text(c, type_on(f"{idx:02d} — {name}", intro, seed=201), col(4), top, f12, ink, a, tracking=1.2)
    draw_text(c, type_on(f"{idx:02d}/10", intro, seed=202), 1824, top, mono(12, 700), ink, a, align="right")
    sec, fr = int(t), int(round((t - int(t)) * FPS)) % FPS
    draw_text(c, f"TC 00:00:{sec:02d}:{fr:02d}", col(0), bot, f12, ink, a, tracking=1.0)
    bar, bt = int(b // 4) + 1, int(b % 4) + 1
    draw_text(c, f"120 BPM · {bar}.{bt}", 1824, bot, f12, ink, a, align="right", tracking=1.0)
    # beat ruler
    rx0, rx1, ry = col(3), col(9) - L.G, bot - 4
    k = span(b, 0.3, 1.3, out_expo)
    pl = paint(ink, 170, stroke=1.0)
    c.drawLine(rx0, ry, rx0 + (rx1 - rx0) * k, ry, pl)
    starts = {s[2] for s in SCENES}
    for i in range(33):
        x = rx0 + (rx1 - rx0) * i / 32
        if x > rx0 + (rx1 - rx0) * k:
            break
        h = 9 if i in starts else (5 if i % 4 == 0 else 3)
        c.drawLine(x, ry, x, ry - h, pl)
    px = rx0 + (rx1 - rx0) * clamp(b / 32)
    c.drawRect(skia.Rect.MakeXYWH(px - 3, ry - 3, 6, 6), paint(ink, a))
    # registration marks + side text
    for (x, y) in ((40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)):
        if intro > 0:
            reg_mark(c, x, y, ink, s=9 * out_back(intro), alpha=200)
    c.save()
    c.translate(46, CY)
    c.rotate(-90)
    draw_text(c, type_on("ISSUE 01 — GRID · TYPE · RHYTHM", intro, seed=203), 0, 0, mono(11), ink, 200,
              align="center", tracking=2.0)
    c.restore()


def scene_tuple(b):
    for s in SCENES:
        if s[2] <= b < s[3]:
            return s
    return SCENES[-1]


# ================================================================ scene stack
DRAW = {"S1": draw_S1, "S2": draw_S2, "S3": draw_S3, "S4": draw_S4, "S5": draw_S5, "S6": draw_S6,
        "S7": draw_S7, "S8": draw_S8, "S9": draw_S9, "S10": draw_S10}


def draw_stack(c, b, X):
    """Draw the correct scene(s) for beat b, including masked transitions."""
    sid = scene_tuple(b)[0]
    if sid == "S1" and b >= 3.5:                       # point -> circle wipe
        draw_S1(c, b, X)
        c.save()
        c.clipPath(mask_S1_S2(b), doAntiAlias=True)
        draw_S2(c, b, X)
        c.restore()
        return
    if sid == "S5":
        if b < 12.4:                                   # collapsed line -> band
            draw_S4(c, b, X)
            c.save()
            c.clipPath(mask_S4_S5(b), doAntiAlias=True)
            draw_S5(c, b, X)
            c.restore()
            return
        m = mask_S5_S6(b, X)                           # torus hole iris
        draw_S5(c, b, X, with_chrome=m is None)
        if m is not None:
            c.save()
            c.clipPath(m, doAntiAlias=True)
            draw_S6(c, b, X)
            c.restore()
            X.draw_chrome(c)
        return
    if sid == "S6" and b >= 18.55:                     # "+" mark -> cross wipe
        draw_S6(c, b, X)
        m = mask_S6_S7(b)
        if m is not None:
            c.save()
            c.clipPath(m, doAntiAlias=True)
            draw_S7(c, b, X)
            c.restore()
        return
    DRAW[sid](c, b, X)
