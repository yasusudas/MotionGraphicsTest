"""Build the two 3D moments as NEW scenes (existing scenes are left untouched).

  OPUS_CHROME  S5 "FORM": twisted rounded-square chrome torus, transparent film.
               It flips on the beat, then faces camera and scales up so its hole
               irises open onto S6 (the 2D side draws S6 inside the hole).
  OPUS_GLASS   S9 "LENS": glass sphere in front of an emissive backdrop that plays
               the 2D S9 plates, so the refraction of the flat layout is real.
               It ends by shrinking into the red period of "OPUS." (S10).

Run:  $OPUS_PY src/blender/build_scene.py       (bpy module == headless Blender 5.1.1)
Env:  OPUS_BUILD (timeline / analysis / plates / track.json), OPUS_SAVE=path.blend to save
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bpy  # noqa: I001  (bpy must be imported before bmesh in the bpy module)
import bmesh
import numpy as np
from bpy_extras.anim_utils import action_ensure_channelbag_for_slot
from mathutils import Matrix, Vector

SRC = Path(os.environ.get("OPUS_SRC", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(SRC))
import layout as L  # noqa: E402
from config import BUILD, FPS, H, W  # noqa: E402

PREFIX = "OPUS_"
CHROME_RANGE = (176, 246)
GLASS_RANGE = (352, 424)


def srgb(c):
    """sRGB 0-255 -> linear 0-1 (Blender colour inputs are linear)."""
    out = []
    for v in c[:3]:
        v = v / 255
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


PAPER = srgb((241, 236, 226))
BLACK = srgb((12, 12, 13))
RED = srgb((255, 72, 28))
COBALT = srgb((28, 58, 255))
LIME = srgb((205, 255, 36))


# ---------------------------------------------------------------- easing / curves
def clamp01(u):
    return np.clip(u, 0.0, 1.0)


def smoothstep(u):
    u = clamp01(u)
    return u * u * (3 - 2 * u)


def ease_in_out_cubic(u):
    u = clamp01(u)
    return np.where(u < 0.5, 4 * u ** 3, 1 - (-2 * u + 2) ** 3 / 2)


def ease_out_back(u, s=1.70158):
    u = clamp01(u)
    return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2


def ease_out_elastic(u, period=0.32):
    u = clamp01(u)
    return np.where(u <= 0, 0.0, np.where(u >= 1, 1.0,
                    2 ** (-10 * u) * np.sin((u - period / 4) * (2 * np.pi) / period) + 1))


def ease_in_expo(u):
    u = clamp01(u)
    return np.where(u <= 0, 0.0, 2 ** (10 * u - 10))


def ease_out_expo(u):
    u = clamp01(u)
    return np.where(u >= 1, 1.0, 1 - 2 ** (-10 * u))


EASES = {"lin": clamp01, "smooth": smoothstep, "cubic": ease_in_out_cubic, "back": ease_out_back,
         "elastic": ease_out_elastic, "in_expo": ease_in_expo, "out_expo": ease_out_expo,
         "hold": lambda u: np.where(u >= 1, 1.0, 0.0)}


def piecewise(f, keys):
    """keys: [(frame, value, ease_into_this_key), ...] -> values at frames f (array)."""
    f = np.asarray(f, float)
    out = np.full(f.shape, float(keys[0][1]))
    for (f0, v0, _), (f1, v1, ease) in zip(keys[:-1], keys[1:]):
        sel = f >= f0
        u = (f - f0) / max(f1 - f0, 1e-9)
        out = np.where(sel, v0 + (v1 - v0) * EASES[ease](u), out)
    return out


def noise1d(f, seed=0, scale=12.0):
    rng = np.random.default_rng(seed)
    knots = rng.uniform(-1, 1, int(np.max(f) / scale) + 4)
    x = np.asarray(f) / scale
    i = np.floor(x).astype(int)
    u = smoothstep(x - i)
    return knots[i] * (1 - u) + knots[i + 1] * u


# ---------------------------------------------------------------- keyframes (one fcurve per channel, every frame)
def key(idblock, path, index, frames, values, id_type=None):
    ad = idblock.animation_data or idblock.animation_data_create()
    if ad.action is None:
        act = bpy.data.actions.new(PREFIX + idblock.name + "_act")
        slot = act.slots.new(id_type=id_type or "OBJECT", name=idblock.name)
        ad.action = act
        ad.action_slot = slot
    cb = action_ensure_channelbag_for_slot(ad.action, ad.action_slot)
    fc = cb.fcurves.find(path, index=index) or cb.fcurves.new(path, index=index)
    fc.keyframe_points.clear()
    n = len(frames)
    fc.keyframe_points.add(n)
    co = np.empty(2 * n, np.float32)
    co[0::2] = frames
    co[1::2] = values
    fc.keyframe_points.foreach_set("co", co)
    fc.keyframe_points.foreach_set("interpolation", [1] * n)   # LINEAR: exact per-frame values
    fc.update()


# ---------------------------------------------------------------- scene plumbing
def fresh_scene(name):
    old = bpy.data.scenes.get(name)
    if old is not None:
        for ob in list(old.collection.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.scenes.remove(old)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights,
                 bpy.data.worlds, bpy.data.actions, bpy.data.images, bpy.data.node_groups):
        for block in list(coll):
            if block.name.startswith(PREFIX) and block.users == 0:
                coll.remove(block)
    sc = bpy.data.scenes.new(name)
    r = sc.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100
    r.fps = FPS
    r.use_motion_blur = True
    r.motion_blur_shutter = 0.5
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "8"
    r.dither_intensity = 1.0
    sc.view_settings.view_transform = "Standard"     # palette colours must survive untouched
    sc.view_settings.look = "None"
    c = sc.cycles
    c.device = "CPU"
    c.use_adaptive_sampling = True
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.use_animated_seed = True
    return sc


def camera(sc):
    cd = bpy.data.cameras.new(PREFIX + sc.name + "_cam")
    cd.type = "ORTHO"
    cd.ortho_scale = 16.0
    cd.sensor_fit = "HORIZONTAL"
    cd.clip_end = 200
    cam = bpy.data.objects.new(PREFIX + sc.name + "_cam", cd)
    cam.location = (0, -40, 0)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def band_world(sc, name):
    """Graphic studio: flat colour bands by elevation + a red stripe (seen only in reflections)."""
    wd = bpy.data.worlds.new(PREFIX + name)
    wd.use_nodes = True
    nt = wd.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    stops = [(0.0, BLACK), (0.22, tuple(v * 0.75 for v in PAPER[:3]) + (1,)), (0.40, BLACK),
             (0.47, COBALT), (0.62, BLACK), (0.76, PAPER), (0.81, BLACK), (0.93, COBALT), (0.97, BLACK)]
    els[0].position, els[0].color = stops[0]
    els[1].position, els[1].color = stops[1]
    for p, col_ in stops[2:]:
        e = els.new(p)
        e.color = col_
    # elevation z in [-1,1] -> [0,1]
    mz = nt.nodes.new("ShaderNodeMath")
    mz.operation = "MULTIPLY_ADD"
    mz.inputs[1].default_value = 0.5
    mz.inputs[2].default_value = 0.5
    nt.links.new(sep.outputs["Z"], mz.inputs[0])
    nt.links.new(mz.outputs[0], ramp.inputs[0])
    # red vertical stripe on +X
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.62
    nt.links.new(sep.outputs["X"], gt.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(gt.outputs[0], mix.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = RED
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(mix.outputs[2], bg.inputs["Color"])
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    sc.world = wd


def strip_light(sc, name, loc, rot, size, energy, color=(1, 1, 1)):
    ld = bpy.data.lights.new(PREFIX + name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = size
    ld.energy = energy
    ld.color = color
    ob = bpy.data.objects.new(PREFIX + name, ld)
    ob.location = loc
    ob.rotation_euler = rot
    sc.collection.objects.link(ob)
    return ob


def principled(name, **inputs):
    m = bpy.data.materials.new(PREFIX + name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    for k, v in inputs.items():
        p.inputs[k].default_value = v
    return m


# ---------------------------------------------------------------- geometry
def twisted_torus(R=1.9, r=0.62, nu=320, nv=72, n=3.4, twist=math.pi):
    """Torus whose cross-section is a rounded square (superellipse) rotating `twist` per loop."""
    u = np.linspace(0, 2 * np.pi, nu, endpoint=False)
    v = np.linspace(0, 2 * np.pi, nv, endpoint=False)
    U, V = np.meshgrid(u, v, indexing="ij")
    a = V - twist * U / (2 * np.pi)
    rho = r / (np.abs(np.cos(a)) ** n + np.abs(np.sin(a)) ** n) ** (1 / n)
    x = (R + rho * np.cos(V)) * np.cos(U)
    y = (R + rho * np.cos(V)) * np.sin(U)
    z = rho * np.sin(V)
    verts = np.stack([x, y, z], -1).reshape(-1, 3)
    i = np.arange(nu)[:, None]
    j = np.arange(nv)[None, :]
    a0 = i * nv + j
    a1 = ((i + 1) % nu) * nv + j
    a2 = ((i + 1) % nu) * nv + (j + 1) % nv
    a3 = i * nv + (j + 1) % nv
    faces = np.stack([a0, a1, a2, a3], -1).reshape(-1, 4)
    me = bpy.data.meshes.new(PREFIX + "torus")
    me.from_pydata(verts.tolist(), [], faces.tolist())
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()
    return me, float(R - r), float(R + r * 2 ** (1 / n))


def sphere(radius=1.5, subdiv=6):
    me = bpy.data.meshes.new(PREFIX + "sphere")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()
    return me


def backdrop(sc, plate_first: Path, depth=5.0):
    me = bpy.data.meshes.new(PREFIX + "backdrop")
    hw, hh = 8.0, 4.5
    me.from_pydata([(-hw, depth, -hh), (hw, depth, -hh), (hw, depth, hh), (-hw, depth, hh)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", [0, 0, 1, 0, 1, 1, 0, 1])
    ob = bpy.data.objects.new(PREFIX + "backdrop", me)
    sc.collection.objects.link(ob)
    m = bpy.data.materials.new(PREFIX + "plate")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(plate_first), check_existing=False)
    img.name = PREFIX + "plates"
    img.source = "SEQUENCE"
    tex.image = img
    tex.interpolation = "Closest"
    iu = tex.image_user
    iu.frame_start = 1
    iu.frame_offset = 0
    iu.frame_duration = 100000
    iu.use_auto_refresh = True
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    ob.data.materials.append(m)
    ob.visible_shadow = False
    return ob


# ---------------------------------------------------------------- S5 chrome
def build_chrome():
    sc = fresh_scene("OPUS_CHROME")
    sc.frame_start, sc.frame_end = CHROME_RANGE
    sc.render.film_transparent = True
    c = sc.cycles
    c.samples = 160
    c.adaptive_threshold = 0.02
    c.max_bounces, c.glossy_bounces, c.transmission_bounces = 8, 8, 2
    camera(sc)
    band_world(sc, "chrome_world")
    strip_light(sc, "key_strip", (-6, -9, 5.5), (math.radians(60), 0, math.radians(-30)), (9.0, 0.45), 1300)
    strip_light(sc, "rim_strip", (7, -6, -2.5), (math.radians(100), 0, math.radians(45)), (0.4, 7.0), 900)
    strip_light(sc, "top_card", (0, -3, 8), (math.radians(15), 0, 0), (6.0, 0.8), 250, color=(0.95, 0.97, 1.0))

    me, hole_r, outer_r = twisted_torus()
    ob = bpy.data.objects.new(PREFIX + "torus", me)
    ob.data.materials.append(principled("chrome", **{"Base Color": (0.93, 0.93, 0.95, 1), "Metallic": 1.0,
                                                    "Roughness": 0.04, "Coat Weight": 0.0}))
    sc.collection.objects.link(ob)
    ob.rotation_mode = "XYZ"

    fb = L.frame                      # beat -> frame
    f = np.arange(CHROME_RANGE[0], CHROME_RANGE[1] + 1, dtype=float)
    cx, cz = L.to_units(*L.S5_CENTER)
    mx, mz = 0.0, 0.0                 # centre of frame for the iris
    # drop in with overshoot (b12), hold, flip burst (b14.5), face camera + recentre (b15), iris (b15.5 -> b16)
    scale = piecewise(f, [(fb(12.0), 0.0, "lin"), (fb(12.6), 1.0, "elastic"), (fb(15.5), 1.0, "lin"),
                          (fb(16.0), 9.5, "in_expo")])
    posx = piecewise(f, [(fb(12.0), cx, "lin"), (fb(15.0), cx, "lin"), (fb(15.5), mx, "cubic")])
    posz = piecewise(f, [(fb(12.0), cz + 0.9, "lin"), (fb(12.6), cz, "back"), (fb(15.0), cz, "lin"), (fb(15.5), mz, "cubic")])
    tilt = piecewise(f, [(fb(12.0), 68.0, "lin"), (fb(12.8), 56.0, "back"), (fb(14.5), 50.0, "smooth"),
                         (fb(15.0), 50.0 - 180.0, "cubic"), (fb(15.5), -180.0, "back")])
    yaw = piecewise(f, [(fb(12.0), -25.0, "lin"), (fb(14.5), 8.0, "smooth"), (fb(15.0), 28.0, "cubic"), (fb(15.5), 0.0, "cubic")])
    spin = piecewise(f, [(fb(12.0), -90.0, "lin"), (fb(12.6), 0.0, "out_expo"), (fb(14.5), 30.0, "lin"),
                         (fb(15.0), 120.0, "cubic"), (fb(16.0), 170.0, "out_expo")])
    wob = noise1d(f, 3, 9.0) * 2.0 * (1 - smoothstep((f - fb(15.0)) / 6))
    eul = []
    prev = None
    track = {}
    for k, fr in enumerate(f):
        # torus axis is local Z; facing camera == axis along -Y  (rotate X by 90 - tilt)
        m = (Matrix.Rotation(math.radians(yaw[k]), 4, "Z")
             @ Matrix.Rotation(math.radians(90.0 - tilt[k] + wob[k]), 4, "X")
             @ Matrix.Rotation(math.radians(spin[k]), 4, "Z"))
        e = m.to_euler("XYZ", prev) if prev is not None else m.to_euler("XYZ")
        prev = e
        eul.append(e)
        px, py = L.to_px(posx[k], posz[k])
        facing = abs(((tilt[k] + 90) % 180) - 90) < 1.5 and abs(yaw[k]) < 1.5
        track[int(fr)] = {"x": px, "y": py, "scale": float(scale[k]),
                          "hole_px": hole_r * scale[k] * L.PX_PER_UNIT,
                          "mid_px": 1.9 * scale[k] * L.PX_PER_UNIT,     # tube centre line: safe iris mask
                          "outer_px": outer_r * scale[k] * L.PX_PER_UNIT, "facing": bool(facing),
                          "tilt": float(tilt[k])}
    eul = np.array([[e.x, e.y, e.z] for e in eul])
    for i in range(3):
        key(ob, "rotation_euler", i, f, eul[:, i])
    key(ob, "location", 0, f, posx)
    key(ob, "location", 1, f, np.zeros_like(f))
    key(ob, "location", 2, f, posz)
    for i in range(3):
        key(ob, "scale", i, f, np.maximum(scale, 1e-4))
    return sc, track


# ---------------------------------------------------------------- S9 glass
def build_glass():
    sc = fresh_scene("OPUS_GLASS")
    sc.frame_start, sc.frame_end = GLASS_RANGE
    sc.render.film_transparent = False
    c = sc.cycles
    c.samples = 256
    c.adaptive_threshold = 0.012
    c.max_bounces, c.glossy_bounces, c.transmission_bounces = 16, 8, 16
    camera(sc)
    band_world(sc, "glass_world")
    strip_light(sc, "key_strip", (-5, -8, 5), (math.radians(58), 0, math.radians(-28)), (7.0, 0.35), 1800)
    strip_light(sc, "rim_strip", (6, -5, -3), (math.radians(105), 0, math.radians(40)), (0.3, 5.0), 900)
    plates = BUILD / "plates"
    first = plates / f"p_{GLASS_RANGE[0]:04d}.png"
    backdrop(sc, first)
    radius = 1.5
    ob = bpy.data.objects.new(PREFIX + "glass", sphere(radius))
    ob.data.materials.append(principled("glass", **{"Base Color": (1, 1, 1, 1), "Metallic": 0.0, "Roughness": 0.0,
                                                   "IOR": 1.47, "Transmission Weight": 1.0,
                                                   "Coat Weight": 0.0, "Specular IOR Level": 0.6}))
    sc.collection.objects.link(ob)

    fb = L.frame
    f = np.arange(GLASS_RANGE[0], GLASS_RANGE[1] + 1, dtype=float)
    x0, z0 = L.to_units(*L.S9_START)
    xa, za = L.to_units(L.col(3) + L.CW / 2, L.H / 2 + 60)
    xb, zb = L.to_units(L.col(6), L.H / 2 - 40)
    xd, zd = L.to_units(*L.S10_DOT)
    end_scale = L.S10_DOT_R / (radius * L.PX_PER_UNIT)
    s_in = piecewise(f, [(fb(23.9), 0.0, "lin"), (fb(24.6), 1.0, "elastic")])
    s_mid = piecewise(f, [(fb(25.9), 1.0, "lin"), (fb(26.25), 1.18, "back"), (fb(27.5), 1.18, "lin"),
                          (fb(28.0), end_scale, "cubic")])
    scale = s_in * s_mid
    posx = piecewise(f, [(fb(24.0), x0, "lin"), (fb(24.9), x0, "lin"), (fb(25.25), xa, "back"),
                         (fb(25.9), xa, "lin"), (fb(26.25), xb, "back"), (fb(27.5), xb, "lin"), (fb(28.0), xd, "cubic")])
    posz = piecewise(f, [(fb(24.0), z0, "lin"), (fb(24.9), z0, "lin"), (fb(25.25), za, "back"),
                         (fb(25.9), za, "lin"), (fb(26.25), zb, "back"), (fb(27.5), zb, "lin"), (fb(28.0), zd, "cubic")])
    spin = piecewise(f, [(fb(24.0), 0.0, "lin"), (fb(28.0), 140.0, "lin")])
    key(ob, "location", 0, f, posx)
    key(ob, "location", 1, f, np.zeros_like(f))
    key(ob, "location", 2, f, posz)
    for i in range(3):
        key(ob, "scale", i, f, np.maximum(scale, 1e-4))
    key(ob, "rotation_euler", 2, f, np.radians(spin))
    track = {}
    for k, fr in enumerate(f):
        px, py = L.to_px(posx[k], posz[k])
        track[int(fr)] = {"x": px, "y": py, "r_px": radius * scale[k] * L.PX_PER_UNIT, "scale": float(scale[k])}
    return sc, track


def main():
    chrome, t_chrome = build_chrome()
    glass, t_glass = build_glass()
    BUILD.mkdir(parents=True, exist_ok=True)
    json.dump({"chrome": t_chrome, "glass": t_glass}, open(BUILD / "track.json", "w"))
    save = os.environ.get("OPUS_SAVE")
    if save:
        Path(save).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=save, copy=True)
    print("built scenes:", [s.name for s in bpy.data.scenes], "track frames:", len(t_chrome), len(t_glass))


if __name__ == "__main__":
    main()
