"""Small DSP toolkit on (2, n) float32 arrays at config.SR."""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache

import numpy as np
import pyloudnorm
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt, sosfiltfilt

from config import SR, FPS


@lru_cache(maxsize=None)
def _load(path: str) -> np.ndarray:
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.T
    if x.shape[0] == 1:
        x = np.repeat(x, 2, axis=0)
    x = x[:2]
    if sr != SR:
        fr = Fraction(SR, sr).limit_denominator(1000)
        x = resample_poly(x, fr.numerator, fr.denominator, axis=1).astype(np.float32)
    x = x - x.mean(axis=1, keepdims=True)
    return x


def load(path) -> np.ndarray:
    return _load(str(path)).copy()


def repitch(x: np.ndarray, semis: float) -> np.ndarray:
    """Tape-style repitch (length changes with pitch)."""
    if abs(semis) < 1e-3:
        return x
    fr = Fraction(2 ** (-semis / 12)).limit_denominator(400)
    return resample_poly(x, fr.numerator, fr.denominator, axis=1).astype(np.float32)


def trim(x: np.ndarray, sec: float, fade: float = 0.01) -> np.ndarray:
    n = min(x.shape[1], int(sec * SR))
    y = x[:, :n].copy()
    f = min(n, int(fade * SR))
    if f > 1:
        y[:, n - f:] *= np.linspace(1, 0, f, dtype=np.float32) ** 2
    return y


def fade_in(x: np.ndarray, sec: float, curve: float = 2.0) -> np.ndarray:
    y = x.copy()
    f = min(y.shape[1], int(sec * SR))
    if f > 1:
        y[:, :f] *= np.linspace(0, 1, f, dtype=np.float32) ** curve
    return y


def fade_out(x: np.ndarray, sec: float, curve: float = 2.0) -> np.ndarray:
    y = x.copy()
    f = min(y.shape[1], int(sec * SR))
    if f > 1:
        y[:, -f:] *= np.linspace(1, 0, f, dtype=np.float32) ** curve
    return y


def db(v: float) -> float:
    return 10 ** (v / 20)


def place(bus: np.ndarray, x: np.ndarray, t: float, gain_db: float = 0.0, pan: float = 0.0):
    """Add x into bus at time t with equal-power pan (-1..1)."""
    i0 = int(round(t * SR))
    a = (pan + 1) * np.pi / 4
    g = db(gain_db) * np.array([np.cos(a), np.sin(a)], np.float32)[:, None] * np.sqrt(2)
    s0, s1 = max(0, i0), min(bus.shape[1], i0 + x.shape[1])
    if s1 <= s0:
        return
    bus[:, s0:s1] += x[:, s0 - i0:s1 - i0] * g


def rms_db(x, t0=None, t1=None) -> float:
    if t0 is not None:
        x = x[:, int(t0 * SR):int(t1 * SR)]
    return 20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-12)


def peak_db(x) -> float:
    return 20 * np.log10(np.abs(x).max() + 1e-12)


def true_peak_db(x) -> float:
    return peak_db(resample_poly(x, 4, 1, axis=1))


def lufs(x, t0=None, t1=None) -> float:
    if t0 is not None:
        x = x[:, int(t0 * SR):int(t1 * SR)]
    return pyloudnorm.Meter(SR).integrated_loudness(x.T.astype(np.float64))


def normalize_rms(x, target_db, t0=None, t1=None):
    return x * db(target_db - rms_db(x, t0, t1))


def _sos(kind, f, order):
    return butter(order, np.clip(f, 10, SR / 2 - 100), btype=kind, fs=SR, output="sos")


def hp(x, f, order=2, zero_phase=False):
    return (sosfiltfilt if zero_phase else sosfilt)(_sos("highpass", f, order), x, axis=1).astype(np.float32)


def lp(x, f, order=2, zero_phase=False):
    return (sosfiltfilt if zero_phase else sosfilt)(_sos("lowpass", f, order), x, axis=1).astype(np.float32)


def mono(x):
    m = x.mean(axis=0, keepdims=True)
    return np.repeat(m, 2, axis=0)


def widen(x, amount=1.0):
    m = (x[0] + x[1]) / 2
    s = (x[0] - x[1]) / 2 * amount
    return np.stack([m + s, m - s]).astype(np.float32)


def automate(plugin, x, params: dict, block: int = 128) -> np.ndarray:
    """Run a pedalboard plugin block by block; params = {name: f(t_seconds) -> value}."""
    out = np.zeros_like(x)
    plugin.reset()
    n = x.shape[1]
    for i in range(0, n, block):
        t = i / SR
        for k, f in params.items():
            setattr(plugin, k, f(t))
        out[:, i:i + block] = plugin.process(x[:, i:i + block], SR, reset=False)
    return out


def exp_sweep(t, t0, t1, v0, v1, curve=1.0):
    u = np.clip((t - t0) / max(t1 - t0, 1e-9), 0, 1) ** curve
    return float(v0 * (v1 / v0) ** u)


def duck_env(n, times, depth_db=-8.0, attack=0.004, release=0.18) -> np.ndarray:
    """Sidechain gain curve from kick times."""
    g = np.ones(n, np.float32)
    lo = db(depth_db)
    ta = np.arange(n) / SR
    for t in times:
        i0 = int(t * SR)
        i1 = min(n, i0 + int((attack + release * 4) * SR))
        if i0 >= n:
            continue
        tt = ta[i0:i1] - t
        a = np.clip(tt / attack, 0, 1)
        r = np.exp(-np.maximum(tt - attack, 0) / release)
        dip = 1 - (1 - lo) * a * r
        g[i0:i1] = np.minimum(g[i0:i1], dip)
    # a touch of pre-dip smoothing so the attack does not click
    k = int(0.002 * SR)
    g = np.convolve(g, np.ones(k) / k, mode="same").astype(np.float32)
    return g


def env_follow(x, nframes: int, fps: int = FPS) -> np.ndarray:
    m = x.mean(axis=0) if x.ndim == 2 else x
    hop = SR // fps
    out = np.zeros(nframes, np.float32)
    for f in range(nframes):
        seg = m[f * hop:(f + 1) * hop]
        out[f] = np.sqrt(np.mean(seg ** 2)) if seg.size else 0.0
    return out


def write_wav(path, x, subtype="PCM_24"):
    sf.write(str(path), np.asarray(x, np.float32).T, SR, subtype=subtype)
