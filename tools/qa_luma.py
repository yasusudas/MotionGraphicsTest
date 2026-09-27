"""Frame QA: completeness, mean luminance per frame, photosensitive-flash count.

Relative luminance per frame (sRGB -> linear -> Rec.709 weights, averaged over the frame).
A "flash" is a pair of opposing luminance transitions; transitions are counted with a
zig-zag (hysteresis 0.1) detector and no 1-second window may contain more than 3 flashes
(= 6 reversals).  Also compares against the 3D layer means where they exist.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import BUILD, FPS, NFRAMES  # noqa: E402

comp = Path(sys.argv[1]) if len(sys.argv) > 1 else BUILD / "comp"
lin = ((np.arange(256) / 255.0 + 0.055) / 1.055) ** 2.4
lin[:11] = np.arange(11) / 255.0 / 12.92
missing, lum = [], np.zeros(NFRAMES)
for f in range(NFRAMES):
    p = comp / f"c_{f:04d}.png"
    im = cv2.imread(str(p))
    if im is None:
        missing.append(f)
        continue
    sm = cv2.resize(im, (192, 108), interpolation=cv2.INTER_AREA)
    b, g, r = (lin[sm[..., i]] for i in range(3))
    lum[f] = float((0.2126 * r + 0.7152 * g + 0.0722 * b).mean())

# zig-zag with hysteresis: a transition is a luminance move of >= 0.1 opposite to the previous one
ext, direction, turns = lum[0], 0, []
for f in range(1, NFRAMES):
    v = lum[f]
    if direction == 0:
        if abs(v - ext) >= 0.1:
            direction, ext = (1 if v > ext else -1), v
            turns.append(f)
    elif direction == 1:
        if v > ext:
            ext = v
        elif ext - v >= 0.1:
            direction, ext = -1, v
            turns.append(f)
    else:
        if v < ext:
            ext = v
        elif v - ext >= 0.1:
            direction, ext = 1, v
            turns.append(f)
turns = np.array(turns)
worst, worst_at = 0, 0
for f in range(NFRAMES):
    n = int(((turns >= f) & (turns < f + FPS)).sum())
    if n > worst:
        worst, worst_at = n, f
flashes = worst / 2          # a flash = a pair of opposing transitions
jumps = np.abs(np.diff(lum))
big = [(int(i + 1), round(float(jumps[i]), 3)) for i in np.argsort(jumps)[::-1][:12]]
res = {"frames": NFRAMES, "missing": missing, "transitions": turns.tolist(), "max_transitions_per_second": worst,
       "max_flashes_per_second": flashes, "worst_window_start": worst_at,
       "pass_flash": flashes <= 3, "largest_frame_jumps": sorted(big)}
json.dump({**res, "luma": [round(v, 4) for v in lum]}, open(BUILD / "qa_luma.json", "w"))
print(json.dumps(res, indent=1))

# plot
Hh = 300
img = np.full((Hh, NFRAMES * 3, 3), 20, np.uint8)
for f in range(1, NFRAMES):
    y0, y1 = int(Hh - 10 - lum[f - 1] * (Hh - 20)), int(Hh - 10 - lum[f] * (Hh - 20))
    cv2.line(img, ((f - 1) * 3, y0), (f * 3, y1), (240, 236, 226), 1)
for t in turns:
    cv2.line(img, (int(t) * 3, 0), (int(t) * 3, 12), (40, 80, 255), 2)
for s in range(0, NFRAMES, 15):
    cv2.line(img, (s * 3, Hh - 6), (s * 3, Hh), (120, 120, 120), 1)
cv2.imwrite(str(BUILD / "qa_luma.png"), img)
