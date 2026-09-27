"""Single source of truth shared by audio, Blender and the 2D compositor."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("OPUS_ROOT", Path(__file__).resolve().parents[1]))
TOOLS = Path(os.environ.get("OPUS_TOOLS", ROOT / "_temp_install"))
SAMPLES = TOOLS / "samples"
FONTS = TOOLS / "fonts"
PLUGINS = TOOLS / "plugins"
OUT = ROOT / "out"
SCENE_DIR = ROOT / "scene"
BUILD = Path(os.environ.get("OPUS_BUILD", ROOT / "build"))

# ---------------------------------------------------------------- tempo / format
BPM = 120.0
BEAT = 60.0 / BPM            # 0.5 s  -> exactly 15 frames at 30 fps
BAR = 4 * BEAT               # 2.0 s
STEP = BEAT / 4              # 16th note
SR = 48000
FPS = 30
DURATION = 16.0              # 8 bars
NFRAMES = int(DURATION * FPS)  # 480
W, H = 1920, 1080
TAIL = 1.0                   # audio rendered longer, trimmed at the end


def t_of(bar: float, step: float = 0.0) -> float:
    """bar is 0-based, step in 16ths."""
    return bar * BAR + step * STEP


def beat(b: float) -> float:
    return b * BEAT


# ---------------------------------------------------------------- palette (sRGB 0-255)
BLACK = (12, 12, 13)
PAPER = (241, 236, 226)      # warm off-white
RED = (255, 72, 28)          # vivid red-orange
COBALT = (28, 58, 255)       # electric cobalt
LIME = (205, 255, 36)        # neon lime (occasional)

# ---------------------------------------------------------------- scenes (in beats)
# 3+3+2 groupings between the 4-beat "stillness" scenes give the cut rhythm.
SCENES = [
    # id,  name,       b0, b1, background, ink,   accent
    ("S1", "POINT",     0,  4, PAPER,  BLACK, RED),
    ("S2", "MOTION",    4,  7, RED,    BLACK, PAPER),
    ("S3", "RADIAL",    7, 10, COBALT, PAPER, PAPER),
    ("S4", "RHYTHM",   10, 12, BLACK,  PAPER, LIME),
    ("S5", "FORM",     12, 16, PAPER,  BLACK, COBALT),
    ("S6", "TYPE",     16, 19, RED,    PAPER, BLACK),
    ("S7", "SIGN",     19, 22, BLACK,  RED,   PAPER),
    ("S8", "WAVE",     22, 24, COBALT, PAPER, LIME),
    ("S9", "LENS",     24, 28, PAPER,  COBALT, BLACK),
    ("S10", "OPUS",    28, 32, BLACK,  PAPER, RED),
]


def scene_at(t: float):
    b = t / BEAT
    for s in SCENES:
        if s[2] <= b < s[3]:
            return s
    return SCENES[-1]


def scene_bounds(sid: str) -> tuple[float, float]:
    for s in SCENES:
        if s[0] == sid:
            return beat(s[2]), beat(s[3])
    raise KeyError(sid)
