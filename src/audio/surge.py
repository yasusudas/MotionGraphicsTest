"""Surge XT (VST3) driven through pedalboard: load factory .fxp patches, render MIDI."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import mido
import numpy as np
import pedalboard

from config import PLUGINS, SR
from audio.plugin_state import fxp_to_sub3, split_raw_state, sub3_name, with_component

SURGE_DATA = Path(os.environ.get("SURGE_DATA_HOME", PLUGINS / "SurgeXTData"))


@lru_cache(maxsize=None)
def _plugin(path: str):
    return pedalboard.load_plugin(path)


def patch_path(rel: str) -> Path:
    """'Keys/Pluck Something' -> factory .fxp (searches factory then 3rd party)."""
    for root in ("patches_factory", "patches_3rdparty"):
        p = SURGE_DATA / root / f"{rel}.fxp"
        if p.exists():
            return p
    hits = sorted(SURGE_DATA.glob(f"patches_*/**/{Path(rel).name}.fxp"))
    if not hits:
        raise FileNotFoundError(rel)
    return hits[0]


def silence(sec: float) -> np.ndarray:
    return np.zeros((2, int(sec * SR)), np.float32)


class Surge:
    """One Surge XT instance; ``load`` swaps patches in place."""

    def __init__(self, patch: str | None = None, instance: str = "Surge XT.vst3"):
        self.plugin = _plugin(str(PLUGINS / instance))
        self.patch = None
        if patch:
            self.load(patch)

    def load(self, patch: str):
        sub3 = fxp_to_sub3(patch_path(patch).read_bytes())
        self.plugin.reset()
        self.plugin.raw_state = with_component(self.plugin.raw_state, sub3)
        # the new patch is applied by the audio thread on the next block
        self.plugin.process([], duration=0.25, sample_rate=SR, num_channels=2, reset=False)
        got = sub3_name(split_raw_state(self.plugin.raw_state)["IComponent"])
        self.patch, self.patch_name = patch, got
        return self

    def set(self, **params):
        for k, v in params.items():
            setattr(self.plugin, k, v)
        return self

    def render(self, notes, duration: float, pitch_offset: int = 0) -> np.ndarray:
        """notes: iterable of (t_sec, midi_note, length_sec, velocity 0..1)."""
        evs = []
        for t, n, ln, vel in notes:
            n = int(n) + pitch_offset
            v = int(np.clip(round(vel * 127), 1, 127))
            evs.append((max(t, 0.0), 1, mido.Message("note_on", note=n, velocity=v)))
            evs.append((max(t, 0.0) + ln, 0, mido.Message("note_off", note=n, velocity=0)))
        evs.sort(key=lambda e: (e[0], e[1]))
        # mido messages carrying absolute seconds in .time (pedalboard's accepted form)
        msgs = [m.copy(time=t) for t, _, m in evs]
        out = self.plugin.process(msgs, duration=duration, sample_rate=SR,
                                  num_channels=2, buffer_size=256, reset=True)
        return np.asarray(out, np.float32)
