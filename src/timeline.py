"""Event timeline: the one piece of data audio, Blender and 2D all read.

Events are dicts ``{kind, t (s), b (beats), vel, ...}``; ``len`` is always in beats.
Section map (beats, 0.5 s each):

  S1  0- 4  POINT   stillness -> ticks -> riser           (no kick)
  S2  4- 7  MOTION  groove in: kick / clap / hats / bass / stabs
  S3  7-10  RADIAL  groove + bleep arps on the dot wave
  S4 10-12  RHYTHM  drum-letter hits, stutter into a hard stop
  S5 12-16  FORM    breakdown: pad, glass pings, snare roll + cymbal swell
  S6 16-19  TYPE    drop 2: full groove + stabs on letter flips
  S7 19-22  SIGN    groove, metal hits on cross rotations
  S8 22-24  WAVE    filter burst, 32nd hats, reverse suck
  S9 24-28  LENS    half-time: pad, glock, sparse kick
  S10 28-32 OPUS    letter drops (hits) -> final chord -> tail
"""
from __future__ import annotations

import json
import random

from config import BEAT, BUILD, SCENES

A_MINOR = {"Am": [57, 60, 64, 67], "F": [53, 57, 60, 64], "C": [48, 55, 60, 64],
           "G": [55, 59, 62, 67], "Dm": [50, 57, 60, 65]}


def build_events(seed: int = 7) -> list[dict]:
    rnd = random.Random(seed)
    ev: list[dict] = []

    def add(kind, b, vel=1.0, **kw):
        ev.append(dict(kind=kind, b=round(b, 5), t=round(b * BEAT, 6), vel=round(vel, 3), **kw))

    def hum(v, amt=0.08):
        return max(0.05, min(1.0, v + rnd.uniform(-amt, amt)))

    # ---------------------------------------------------------------- structure
    for sid, name, b0, b1, *_ in SCENES:
        add("cut", b0, scene=sid, name=name, end=b1)

    groove = [(4, 12), (16, 22)]          # four-on-the-floor regions
    half = (24, 28)

    # ---------------------------------------------------------------- S1 POINT
    add("dot", 0.0, 1.0)                                   # red dot appears
    add("pluck", 0.0, 0.9, note=81, len=0.4, patch="dot")
    add("tick", 0.0, 0.8, variant="blip")
    for i, b in enumerate([1.0, 1.5, 2.0, 2.5, 2.75, 3.0, 3.25, 3.5, 3.625, 3.75, 3.875]):
        add("tick", b, hum(0.45 + 0.05 * i, 0.04), variant="rule", idx=i)   # grid rules draw
    for i in range(6):                                     # GRID reveal columns
        add("reveal", 2.0 + i * 0.25, 0.7, idx=i)
        add("bleep", 2.0 + i * 0.25, hum(0.55), note=[76, 79, 81, 84, 88, 91][i], len=0.18)
    add("pad", 0.0, 0.35, notes=A_MINOR["Am"], len=4.0, patch="pad_a")
    add("riser", 2.0, 0.9, len=2.0)                        # noise sweep into the first impact
    add("reverse", 4.0, 0.8, len=1.0, variant="crash")     # reversed cymbal ending on b4

    # ---------------------------------------------------------------- impacts / transitions
    for b, v in [(4, 1.0), (7, 0.8), (10, 0.75), (16, 1.0), (19, 0.7), (22, 0.7), (24, 0.85), (28, 0.9)]:
        add("impact", b, v)
    add("crash", 4.0, 1.0); add("crash", 16.0, 1.0); add("crash", 8.0, 0.55)
    add("crash", 28.0, 0.7); add("crash", 30.0, 0.95)
    add("whoosh", 7.0, 0.8, len=0.5)
    add("zap", 7.0, 0.9)
    add("whoosh", 19.0, 0.6, len=0.4)
    add("sub_drop", 4.0, 1.0); add("sub_drop", 16.0, 1.0); add("sub_drop", 30.0, 0.9)

    # ---------------------------------------------------------------- drums
    for g0, g1 in groove:
        b = g0
        while b < g1:
            add("kick", b, 1.0 if b % 4 == 0 else hum(0.92, 0.04))
            b += 1
        for b in range(g0, g1):
            if b % 2 == 1:
                add("clap", b, hum(0.9, 0.05))
        s = g0 * 4
        while s < g1 * 4:
            bb = s / 4
            pos = s % 4
            vel = [0.55, 0.3, 0.75, 0.35][pos]
            if pos == 2:
                add("ohat", bb, hum(0.6, 0.05))
            else:
                add("hat", bb, hum(vel, 0.06))
            s += 1
    # S4 RHYTHM: extra toms per letter, stutter at the end
    for i, b in enumerate([10.0, 10.5, 10.75, 11.0, 11.25]):
        add("letter", b, 1.0, idx=i)
    for i, b in enumerate([10.25, 10.75, 11.25]):
        add("tom", b, hum(0.7), note=[0, 1, 2][i])
    add("stutter", 11.5, 1.0, len=0.5)
    # S5 breakdown: snare roll + cymbal crescendo into b16
    s = 15.0
    while s < 16.0:
        frac = (s - 15.0)
        add("snare", s, 0.3 + 0.6 * frac, roll=True)
        s += 0.125 if s < 15.5 else 0.0625
    add("cresc", 16.0, 0.8, len=3.0)                         # peak aligned to b16
    # S7 metal hits on cross rotations (every 8th)
    for i, b in enumerate([19.0, 19.5, 20.0, 20.5, 21.0, 21.5]):
        add("rotate", b, 1.0, idx=i)
        add("metal", b + 0.25, hum(0.5), idx=i)
    # S8 WAVE: 32nd hats + filter burst, reverse suck into b24
    s = 22.0
    while s < 24.0:
        add("hat", s, hum(0.35 + 0.25 * ((s * 8) % 2 == 0), 0.05), fast=True)
        s += 0.125
    for b in (22.0, 23.0):
        add("kick", b, 0.95)
    add("clap", 23.0, 0.85)
    add("sweep", 22.0, 1.0, len=2.0)
    add("suck", 24.0, 0.9, len=1.0)
    # S9 LENS half time
    add("kick", 24.0, 0.9); add("kick", 26.0, 0.75); add("kick", 27.5, 0.6)
    add("clap", 26.0, 0.8)
    for b in [24.5, 25.5, 26.5, 27.0, 27.25]:
        add("rim", b, hum(0.5))
    s = 27.0
    while s < 28.0:
        add("snare", s, 0.25 + 0.55 * (s - 27.0), roll=True)
        s += 0.125
    add("riser", 27.0, 0.6, len=1.0)
    # S10 OPUS letter drops then final chord
    for i, b in enumerate([28.0, 28.5, 29.0, 29.5]):
        add("drop", b, 1.0, idx=i)
        add("kick", b, 1.0)
        add("clap", b, 0.55 + 0.1 * i)
        add("tom", b + 0.25, hum(0.5), note=i % 3)
    add("kick", 30.0, 1.0)
    add("final", 30.0, 1.0)
    add("tick", 31.0, 0.5, variant="blip")
    add("pluck", 31.0, 0.5, note=81, len=0.5, patch="dot")

    # ---------------------------------------------------------------- bass (Tacky 1, 16ths)
    riff = [45, 0, 45, 57, 0, 45, 55, 45, 0, 45, 57, 45, 0, 43, 45, 52]
    roots = {4: 45, 8: 45, 10: 41, 16: 45, 20: 50, 22: 45}
    for g0, g1 in [(4, 12), (16, 24)]:
        s = g0 * 4
        while s < g1 * 4:
            bb = s / 4
            root = [v for k, v in sorted(roots.items()) if k <= bb][-1]
            n = riff[s % 16]
            if n:
                add("bass", bb, hum(0.85 if s % 4 == 0 else 0.7, 0.05), note=n - 45 + root, len=0.2)
            s += 1
    add("sub", 12.0, 0.7, note=41, len=4.0)                     # F under the breakdown
    add("sub", 24.0, 0.5, note=50, len=2.0); add("sub", 26.0, 0.45, note=50, len=2.0)
    add("sub", 30.0, 1.0, note=45, len=2.0)

    # ---------------------------------------------------------------- stabs / chords
    stab_pat = [0.75, 1.5, 2.25, 3.0, 3.5]                      # syncopated inside a bar
    for bar0, chord in [(4, "Am"), (8, "Am"), (16, "Am"), (20, "Dm")]:
        for off in stab_pat:
            b = bar0 + off
            if (bar0 == 8 and b >= 10) or (bar0 == 20 and b >= 22):
                continue
            add("stab", b, hum(0.75), note={"Am": 57, "Dm": 50}[chord], len=0.3)
    for i, b in enumerate([16.0, 16.75, 17.5, 18.25, 19.0]):   # S6 letter flips
        add("flip", b, 1.0, idx=i)
    add("stab", 28.0, 0.7, note=57, len=0.5); add("stab", 30.0, 1.0, note=57, len=2.0)

    # ---------------------------------------------------------------- melodic colour
    arp = [69, 72, 76, 79, 81, 79, 76, 72]
    for i in range(12):                                          # S3 dot-wave bleeps
        b = 7.0 + i * 0.25
        add("pluck", b, hum(0.55), note=arp[i % 8] + 12, len=0.2, patch="arp")
    add("pad", 12.0, 0.6, notes=A_MINOR["F"] + [67], len=4.0, patch="pad_a")
    for b, n in [(12.0, 84), (13.0, 91), (13.5, 88), (14.5, 96), (15.0, 91)]:
        add("glock", b, hum(0.6), note=n)
    add("pad", 24.0, 0.5, notes=A_MINOR["Dm"] + [64], len=4.0, patch="pad_b")
    for i, b in enumerate([24.0, 24.75, 25.5, 26.0, 26.75, 27.5]):
        add("pluck", b, hum(0.5), note=[74, 77, 81, 84, 81, 77][i], len=0.6, patch="glass")
    for b, n in [(24.0, 96), (26.0, 91)]:
        add("glock", b, 0.55, note=n)
    add("pad", 28.0, 0.5, notes=A_MINOR["Am"] + [71], len=4.0, patch="pad_a")
    add("fx", 11.5, 0.6, len=0.5, patch="fx_up")
    add("fx", 23.0, 0.5, len=1.0, patch="fx_up")
    for b in [12.5, 13.25, 14.0, 14.75, 25.0, 25.75, 26.5]:     # interface beeps for annotations
        add("tick", b, 0.35, variant="ui")

    ev.sort(key=lambda e: (e["t"], e["kind"]))
    return ev


def save(path=None) -> list[dict]:
    path = path or BUILD / "timeline.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    ev = build_events()
    json.dump(ev, open(path, "w"), indent=0)
    return ev


def load(path=None) -> list[dict]:
    return json.load(open(path or BUILD / "timeline.json"))


if __name__ == "__main__":
    evs = save()
    from collections import Counter
    print(len(evs), "events", dict(Counter(e["kind"] for e in evs)))
