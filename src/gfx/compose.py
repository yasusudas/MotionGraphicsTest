"""2D compositor (skia-python): scene stack + Blender layers + post, one PNG per frame.

  $OPUS_PY src/gfx/compose.py --frames 30,120,200         test frames -> $OPUS_BUILD/test2d
  $OPUS_PY src/gfx/compose.py --all --workers 4          all frames  -> $OPUS_BUILD/comp
  $OPUS_PY src/gfx/compose.py --plates 352-424           S9 backdrop plates for Blender
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np
import skia

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import layout as L  # noqa: E402
import timeline  # noqa: E402
from config import BEAT, BUILD, FPS, H, NFRAMES, RED, W  # noqa: E402
from gfx import scenes  # noqa: E402

SUB = 5            # motion-blur subframes
SHUTTER = 0.5      # 180 degrees


class Ctx:
    """Everything a scene may read: events, audio analysis, Blender tracks and layers."""

    def __init__(self):
        self.events = timeline.load()
        a = np.load(BUILD / "audio" / "analysis.npz")
        self.an = {k: a[k] for k in a.files}
        tp = BUILD / "track.json"
        self.track = json.load(open(tp)) if tp.exists() else {"chrome": {}, "glass": {}}
        self.f = 0
        self._img = {}
        self._times = {}

    # --------------------------------------------------------- data
    def times(self, kind, **flt):
        key = (kind, tuple(sorted(flt.items())))
        if key not in self._times:
            self._times[key] = sorted(e["t"] for e in self.events if e["kind"] == kind
                                      and all(e.get(k) == v for k, v in flt.items()))
        return self._times[key]

    def env(self, name, t):
        arr = self.an[name]
        x = t * FPS
        i = int(np.clip(math.floor(x), 0, len(arr) - 2))
        u = min(max(x - i, 0.0), 1.0)
        return float(arr[i] * (1 - u) + arr[i + 1] * u)

    def spec(self, t, b0, b1):
        i = int(np.clip(round(t * FPS), 0, NFRAMES - 1))
        return float(self.an["spec"][i, b0:b1].mean())

    def imp(self, kind, t, decay):
        v = 0.0
        for te in self.times(kind):
            if te <= t:
                v = max(v, math.exp(-(t - te) / decay))
        return v

    # --------------------------------------------------------- Blender layers
    def _load(self, path):
        if path not in self._img:
            if len(self._img) > 6:
                self._img.clear()
            im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED) if Path(path).exists() else None
            if im is not None:
                if im.shape[2] == 3:
                    im = cv2.cvtColor(im, cv2.COLOR_BGR2RGBA)
                else:
                    im = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)
                im = skia.Image.fromarray(np.ascontiguousarray(im), colorType=skia.kRGBA_8888_ColorType)
            self._img[path] = im
        return self._img[path]

    def chrome_track(self):
        return self.track["chrome"].get(str(self.f))

    def glass_track(self):
        return self.track["glass"].get(str(self.f))

    def draw_chrome(self, c):
        im = self._load(BUILD / "frames3d" / f"chrome_{self.f:04d}.png")
        if im is not None:
            c.drawImage(im, 0, 0)

    def draw_glass(self, c, b):
        tr = self.glass_track()
        if tr is None or tr["r_px"] < 0.5 or not (23.9 <= b < 28.0):
            return
        im = self._load(BUILD / "frames3d" / f"glass_{self.f:04d}.png")
        if im is None:
            return
        c.save()
        c.clipPath(scenes.circle_path(tr["x"], tr["y"], tr["r_px"] + 0.6), doAntiAlias=True)
        c.drawImage(im, 0, 0)
        c.restore()
        red = scenes.span(b, 27.55, 28.0, scenes.io_cubic)
        if red > 0:     # the lens becomes the red period of OPUS.
            c.drawCircle(tr["x"], tr["y"], tr["r_px"] + 0.6, scenes.paint(RED, int(255 * red)))


# ------------------------------------------------------------------ colour helpers
_LUT = ((np.arange(256) / 255.0) ** 2.2).astype(np.float32)   # display gamma approx for blur maths


def to_lin(img8):
    return _LUT[img8]


def to_srgb(lin):
    return np.power(np.clip(lin, 0, 1), 1 / 2.2)


_GRAIN = None
_VIG = None


def grain_tex():
    global _GRAIN
    if _GRAIN is None:
        rng = np.random.default_rng(1234)
        g = rng.standard_normal((H + 64, W + 64)).astype(np.float32)
        g = cv2.GaussianBlur(g, (0, 0), 0.65)
        _GRAIN = g / g.std()
    return _GRAIN


def vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) / math.sqrt(2)
        _VIG = (1 - 0.06 * np.clip(d - 0.35, 0, 1) ** 1.6 / 0.65 ** 1.6)[..., None].astype(np.float32)
    return _VIG


def post(lin, f, X):
    t = f / FPS
    # restrained bloom on near-white highlights only
    hi = np.clip(lin.min(axis=2, keepdims=True) - 0.9, 0, None) * 6.0   # whites only; colour glows live in skia
    if hi.max() > 1e-3:
        bloom = cv2.GaussianBlur((lin * hi).astype(np.float32), (0, 0), 14)
        lin = lin + 0.18 * bloom
    # chromatic aberration: radial scale of R / B, kicked by impacts
    k = 0.0007 + 0.0035 * X.imp("impact", t, 0.12)
    out = lin.copy()
    for ch, s in ((0, 1 + k), (2, 1 - k)):
        m = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s)
        out[..., ch] = cv2.warpAffine(lin[..., ch], m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    srgb = to_srgb(out * vignette())
    # grain: monochrome, strongest in the midtones
    g = grain_tex()
    rng = np.random.default_rng(f)
    ox, oy = rng.integers(0, 64, 2)
    gr = g[oy:oy + H, ox:ox + W, None]
    luma = srgb.mean(axis=2, keepdims=True)
    wgt = 0.55 + 0.45 * (1 - np.abs(2 * luma - 1))
    srgb = srgb + gr * 0.016 * wgt
    dither = (rng.random((H, W, 1), dtype=np.float32) - 0.5) / 255
    return np.clip((srgb + dither) * 255 + 0.5, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ frame
_SURF = None


def raster(X, b, meta=True, glass=True):
    global _SURF
    if _SURF is None:
        _SURF = skia.Surface(W, H)
    c = _SURF.getCanvas()
    c.save()
    c.clear(skia.Color(0, 0, 0, 255))
    scenes.draw_stack(c, b, X)
    if glass:
        X.draw_glass(c, b)
        if 24.0 <= b < 28.0:
            scenes.overlay_S9(c, b, X)
    if meta:
        scenes.draw_meta(c, b, X)
    c.restore()
    return _SURF.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]


def render_frame(X, f, sub=SUB):
    X.f = f
    acc = np.zeros((H, W, 3), np.float32)
    for k in range(sub):
        tf = f + ((k + 0.5) / sub - 0.5) * SHUTTER if sub > 1 else f
        acc += to_lin(raster(X, tf / FPS / BEAT))
    return post(acc / sub, f, X)


# ------------------------------------------------------------------ workers
_X = None


def _init():
    global _X
    _X = Ctx()


def _work(job):
    f, out, sub = job
    t0 = time.time()
    img = render_frame(_X, f, sub)
    cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    return f, time.time() - t0


def _plate(job):
    f, out = job
    _X.f = f
    img = raster(_X, f / FPS / BEAT, meta=False, glass=False)
    cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    return f, 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default="")
    ap.add_argument("--range", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--plates", default="")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--out", default="")
    ap.add_argument("--sub", type=int, default=SUB)
    ap.add_argument("--skip-existing", action="store_true")
    a = ap.parse_args()

    if a.plates:
        f0, f1 = map(int, a.plates.split("-"))
        od = BUILD / "plates"
        od.mkdir(parents=True, exist_ok=True)
        jobs = [(f, od / f"p_{f:04d}.png") for f in range(f0, f1 + 1)]
        fn = _plate
    else:
        if a.all:
            frames = list(range(NFRAMES))
            od = Path(a.out) if a.out else BUILD / "comp"
        elif a.range:
            f0, f1 = map(int, a.range.split("-"))
            frames = list(range(f0, f1 + 1))
            od = Path(a.out) if a.out else BUILD / "comp"
        else:
            frames = [int(x) for x in a.frames.split(",") if x]
            od = Path(a.out) if a.out else BUILD / "test2d"
        od.mkdir(parents=True, exist_ok=True)
        jobs = [(f, od / f"c_{f:04d}.png", a.sub) for f in frames
                if not (a.skip_existing and (od / f"c_{f:04d}.png").exists())]
        fn = _work
    t0 = time.time()
    if a.workers <= 1 or len(jobs) <= 1:
        _init()
        for j in jobs:
            f, dt = fn(j)
            print(f"frame {f} {dt:.2f}s", flush=True)
    else:
        with Pool(a.workers, initializer=_init) as pool:
            for i, (f, dt) in enumerate(pool.imap_unordered(fn, jobs, chunksize=2)):
                if i % 20 == 0:
                    print(f"[{time.time() - t0:6.1f}s] {i + 1}/{len(jobs)} frame {f} {dt:.2f}s", flush=True)
    print(f"done {len(jobs)} frames in {time.time() - t0:.1f}s -> {od}")


if __name__ == "__main__":
    main()
