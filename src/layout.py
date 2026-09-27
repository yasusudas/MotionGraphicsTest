"""12-column editorial grid and the anchor points shared by Blender and the 2D compositor.

Blender cameras are orthographic, ortho_scale 16 over 1920 px: 1 unit = 120 px,
world X -> screen x, world Z -> screen -y, origin at the frame centre.
"""
from config import FPS, W, H

M = 96            # outer margin (px)
G = 24            # gutter
COLS = 12
CW = (W - 2 * M - (COLS - 1) * G) / COLS     # 122
RM = 72           # top/bottom margin
ROWS = 8
RH = (H - 2 * RM - (ROWS - 1) * G) / ROWS    # 96
PX_PER_UNIT = W / 16.0


def col(i: float) -> float:
    return M + i * (CW + G)


def row(j: float) -> float:
    return RM + j * (RH + G)


def to_units(px: float, py: float) -> tuple[float, float]:
    return (px - W / 2) / PX_PER_UNIT, (H / 2 - py) / PX_PER_UNIT


def to_px(x: float, z: float) -> tuple[float, float]:
    return W / 2 + x * PX_PER_UNIT, H / 2 - z * PX_PER_UNIT


def frame(b: float) -> float:
    """beat -> frame (15 frames per beat)."""
    return b * FPS * 0.5


# anchors (px)
S1_DOT = (col(8), row(4) - G / 2)        # the red point on the grid (1264, 540)
S1_DOT_R = 22
S5_CENTER = (col(8) + CW / 2 + 12, H / 2)  # chrome torus / cobalt disc (1337, 540)
S5_DISC_R = 372
S10_BASE = row(7) - 4                     # baseline of the final wordmark
S10_DOT_R = 50
S10_DOT = (col(10) + CW * 0.55, S10_BASE - S10_DOT_R)   # period of "OPUS."
S9_START = (col(8) + CW / 2, H / 2 + 20)
