"""Render frames of a scene in scene/opus_scene.blend (headless, Cycles CPU).

  $OPUS_PY src/blender/render_3d.py --scene OPUS_CHROME --frames 190,220 --out DIR/t_####
  $OPUS_PY src/blender/render_3d.py --scene OPUS_GLASS --start 352 --end 424 --out DIR/g_####
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import bpy

ap = argparse.ArgumentParser()
ap.add_argument("--blend", default=str(Path(__file__).resolve().parents[2] / "scene" / "opus_scene.blend"))
ap.add_argument("--scene", required=True)
ap.add_argument("--frames", default="")
ap.add_argument("--start", type=int)
ap.add_argument("--end", type=int)
ap.add_argument("--out", required=True)
ap.add_argument("--samples", type=int)
ap.add_argument("--percent", type=int, default=100)
ap.add_argument("--skip-existing", action="store_true")
ap.add_argument("--border-track", default="", help="track.json key: render only a region around the object")
a = ap.parse_args()

bpy.ops.wm.open_mainfile(filepath=a.blend)
sc = bpy.data.scenes[a.scene]
if bpy.context.window is not None:
    bpy.context.window.scene = sc     # animation is evaluated for the window scene

if a.samples:
    sc.cycles.samples = a.samples
sc.render.resolution_percentage = a.percent
sc.render.threads_mode = "AUTO"
TRACK = json.load(open(Path(os.environ.get("OPUS_BUILD", ".")) / "track.json")) if a.border_track else {}
frames = [int(x) for x in a.frames.split(",") if x] if a.frames else list(range(a.start, a.end + 1))
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
for fr in frames:
    path = a.out.replace("####", f"{fr:04d}") + ".png"
    if a.skip_existing and os.path.exists(path):
        continue
    t = time.time()
    if a.border_track:
        tr = TRACK[a.border_track].get(str(fr))
        if tr is None:
            continue
        r = tr.get("r_px", tr.get("outer_px", 0))
        m = r * 0.6 + 32                       # room for motion blur
        W, H = sc.render.resolution_x, sc.render.resolution_y
        sc.render.use_border, sc.render.use_crop_to_border = True, False
        sc.render.border_min_x = max(0.0, (tr["x"] - r - m) / W)
        sc.render.border_max_x = min(1.0, (tr["x"] + r + m) / W)
        sc.render.border_min_y = max(0.0, 1 - (tr["y"] + r + m) / H)
        sc.render.border_max_y = min(1.0, 1 - (tr["y"] - r - m) / H)
    sc.frame_set(fr)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    print(f"frame {fr} -> {path}  {time.time() - t:.1f}s", flush=True)
print("done", file=sys.stderr)
