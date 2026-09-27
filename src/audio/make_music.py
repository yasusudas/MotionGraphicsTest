"""Render the soundtrack from timeline.json: samples + Surge XT + Dragonfly / Surge FX sends
+ CHOW Tape buses + master chain.  Writes out/opus_soundtrack.wav, stems, analysis.npz, mixlog.json.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict

import numpy as np
import pedalboard
from pedalboard import Compressor, HighpassFilter, LadderFilter, Limiter
from scipy.signal import resample_poly, stft

import timeline
from audio import dsp
from audio.dsp import db, place
from audio.surge import Surge
from config import (BEAT, BUILD, DURATION, FPS, NFRAMES, OUT, PLUGINS, SAMPLES, SCENES, SR, TAIL)

T0 = time.time()
N = int((DURATION + TAIL) * SR)
DM = SAMPLES / "drum-machines"
DIRT = SAMPLES / "dirt"
VCSL = SAMPLES / "vcsl"
rng = np.random.default_rng(11)


def S(rel):
    return dsp.load(SAMPLES / rel)


def bus():
    return np.zeros((2, N), np.float32)


def vel_db(v, span=18.0):
    return 20 * np.log10(max(v, 1e-3)) * (span / 20) if v < 1 else 0.0


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


# ---------------------------------------------------------------- plugins
def vst(name):
    return pedalboard.load_plugin(str(PLUGINS / name))


def tape(dry_wet, drive, sat=0.5, bias=0.5):
    p = vst("CHOWTapeModel.vst3")
    p.dry_wet = dry_wet
    p.tape_drive = drive
    p.tape_saturation = sat
    p.tape_bias = bias
    p.wow_flutter_on_off = False
    p.loss_on_off = True
    p.tape_speed = 30.0
    p.oversampling_factor_render = 2.0
    return p


def plugin_latency(p):
    """Latency a plugin adds that pedalboard does not already compensate: impulse peak offset."""
    x = np.zeros((2, SR // 2), np.float32)
    x[:, 2048] = 1.0
    y = np.asarray(p.process(x, SR, reset=True), np.float32)
    return max(0, int(np.argmax(np.abs(y).sum(0))) - 2048)


def run(p, x, comp=True):
    lag = plugin_latency(p) if comp else 0
    y = np.asarray(p.process(x, SR, reset=True), np.float32)
    if lag:
        log(f"   latency comp {lag} samples")
        y = np.concatenate([y[:, lag:], np.zeros((2, lag), np.float32)], axis=1)
    return y


# ---------------------------------------------------------------- events
ev = timeline.save()
by = defaultdict(list)
for e in ev:
    by[e["kind"]].append(e)
log(f"timeline: {len(ev)} events")

stem = {k: bus() for k in ["kick", "clap", "hats", "perc", "bass", "sub", "stab", "pluck", "pad", "glock", "fx", "crash"]}
send_hall, send_plate, send_delay = bus(), bus(), bus()

# ---------------------------------------------------------------- drums
kick909 = S("drum-machines/RolandTR909/rolandtr909-bd/Bassdrum-04.wav")
kick808 = dsp.lp(dsp.trim(S("drum-machines/RolandTR808/rolandtr808-bd/BD0050.WAV"), 0.45, 0.08), 140)
for e in by["kick"]:
    g = vel_db(e["vel"])
    place(stem["kick"], dsp.trim(kick909, 0.42), e["t"], g)
    place(stem["kick"], kick808, e["t"], g - 3)

clap909 = S("drum-machines/RolandTR909/rolandtr909-cp/Clap.wav")
clap808 = S("drum-machines/RolandTR808/rolandtr808-cp/cp3.wav")
for e in by["clap"]:
    g = vel_db(e["vel"])
    place(stem["clap"], dsp.trim(clap909, 0.5, 0.15), e["t"], g, pan=-0.05)
    place(stem["clap"], clap808, e["t"] + 0.004, g - 6, pan=0.1)
    place(send_plate, dsp.trim(clap909, 0.3), e["t"], g - 8)

snare = S("drum-machines/RolandTR909/rolandtr909-sd/sd03.wav")
for e in by["snare"]:
    g = vel_db(e["vel"], 26)
    place(stem["clap"], dsp.trim(snare, 0.16), e["t"], g - 2, pan=rng.uniform(-0.15, 0.15))
    place(send_plate, dsp.trim(snare, 0.1), e["t"], g - 10)

hh = S("drum-machines/RolandTR909/rolandtr909-hh/hh01.wav")
oh = dsp.trim(S("drum-machines/RolandTR909/rolandtr909-oh/oh01.wav"), 0.22, 0.08)
ch808 = S("drum-machines/RolandTR808/rolandtr808-hh/CH.WAV")
for i, e in enumerate(by["hat"]):
    g = vel_db(e["vel"], 24)
    if e.get("fast"):
        x = dsp.repitch(dsp.trim(ch808, 0.06), rng.uniform(-1, 3))
        place(stem["hats"], x, e["t"], g - 1, pan=0.55 * (1 if i % 2 else -1))
    else:
        place(stem["hats"], hh, e["t"], g, pan=rng.uniform(-0.2, 0.2))
for e in by["ohat"]:
    place(stem["hats"], oh, e["t"], vel_db(e["vel"], 24) - 2, pan=0.25)

rim = S("drum-machines/RolandTR909/rolandtr909-rim/rs01.wav")
for e in by["rim"]:
    place(stem["perc"], rim, e["t"], vel_db(e["vel"]) - 2, pan=0.35)
    place(send_delay, rim, e["t"], -12)
toms = [S(f"drum-machines/RolandTR909/rolandtr909-{k}/{k}02.wav") for k in ("lt", "mt", "ht")]
for e in by["tom"]:
    place(stem["perc"], dsp.trim(toms[e["note"]], 0.35, 0.1), e["t"], vel_db(e["vel"]) - 1,
          pan=[-0.4, 0.0, 0.4][e["note"]])
for e in by["metal"]:
    x = dsp.repitch(S(f"dirt/metal/00{e['idx'] % 10}_{e['idx'] % 10}.wav"), [-5, -2, 0, 2, -3, 3][e["idx"] % 6])
    place(stem["perc"], x, e["t"], vel_db(e["vel"]) - 4, pan=0.5 * (1 if e["idx"] % 2 else -1))
    place(send_hall, x, e["t"], -10)

tick_src = {
    "blip": S("dirt/blip/000_blipp01.wav"),
    "rule": dsp.trim(S("dirt/glitch/003_HH.wav"), 0.08),
    "ui": S("dirt/bleep/tiniest.wav"),
}
for e in by["tick"]:
    x = tick_src[e.get("variant", "rule")]
    if e.get("variant") == "rule":
        x = dsp.repitch(x, e.get("idx", 0) * 1.0)
    place(stem["perc"], x, e["t"], vel_db(e["vel"]) - 3, pan=rng.uniform(-0.6, 0.6))
    if e.get("variant") != "rule":
        place(send_delay, x, e["t"], -10)

crash909 = S("drum-machines/RolandTR909/rolandtr909-cr/Crash.wav")
crash_big = dsp.trim(S("vcsl/cymbal_crash2_fff1.wav"), 3.0, 1.5)
for e in by["crash"]:
    g = vel_db(e["vel"])
    place(stem["crash"], crash909, e["t"], g, pan=-0.2)
    place(stem["crash"], dsp.hp(crash_big, 400), e["t"], g - 6, pan=0.2)
log("drums placed")

# ---------------------------------------------------------------- FX from samples
boom = dsp.lp(dsp.trim(S("drum-machines/RolandTR808/rolandtr808-bd/BD0010.WAV"), 1.4, 0.9), 200)
orch = dsp.trim(S("vcsl/bassdrum_hit_ff.wav"), 1.1, 0.8)
hit = S("dirt/tech/tn1hit2.wav")
for e in by["impact"]:
    g = vel_db(e["vel"])
    place(stem["fx"], boom, e["t"], g - 2)
    place(stem["fx"], orch, e["t"], g - 6)
    place(stem["fx"], dsp.trim(hit, 0.9, 0.4), e["t"], g - 8, pan=0.1)
    place(send_plate, dsp.trim(hit, 0.5), e["t"], g - 12)

rev_crash = dsp.fade_in(crash909[:, ::-1].copy(), 0.5)
for e in by["reverse"]:
    x = rev_crash[:, -int(e["len"] * BEAT * SR):]
    place(stem["crash"], dsp.fade_in(x, 0.3), e["t"] - x.shape[1] / SR, vel_db(e["vel"]) - 2)

wind = dsp.hp(S("dirt/wind/000_wind1.wav"), 300)
for e in by["whoosh"]:
    x = dsp.fade_in(wind[:, ::-1].copy(), 0.3)
    n = x.shape[1]
    pan = np.linspace(-1, 1, n)                       # autopan L -> R across the cut
    a = (pan + 1) * np.pi / 4
    x = x * np.stack([np.cos(a), np.sin(a)]).astype(np.float32) * 1.4
    place(stem["fx"], x, e["t"] - n / SR * 0.8, vel_db(e["vel"]) - 4)
zap = S("dirt/hit/zap-to-crack.wav")
for e in by["zap"]:
    place(stem["fx"], zap, e["t"], vel_db(e["vel"]) - 6)
    place(send_delay, zap, e["t"], -8)

# noise riser: LadderFilter band-pass swept exponentially, amplitude swell
for e in by["riser"]:
    n = int(e["len"] * BEAT * SR)
    noise = rng.standard_normal((2, n)).astype(np.float32) * 0.3
    t0, t1 = 0.0, e["len"] * BEAT
    bp = LadderFilter(mode=LadderFilter.Mode.BPF12, cutoff_hz=400, resonance=0.55, drive=1.0)
    y = dsp.automate(bp, noise, {"cutoff_hz": lambda t: dsp.exp_sweep(t, t0, t1, 350, 9000, 1.3)})
    y *= np.linspace(0, 1, n, dtype=np.float32) ** 2.2
    place(stem["fx"], y, e["t"], vel_db(e["vel"]) - 2)
    place(send_hall, y, e["t"], -8)

# real cymbal crescendo: align its loudness peak to the target time
for e in by["cresc"]:
    x = S("vcsl/susCymb2_cresc_4s.wav")
    env = dsp.env_follow(x, x.shape[1] // (SR // 100), fps=100)
    pk = int(np.argmax(env)) / 100
    ln = e["len"] * BEAT
    x = dsp.trim(x[:, int(max(0, pk - ln) * SR):], min(ln, pk) + 0.25, 0.2)
    lead = min(ln, pk)
    place(stem["crash"], dsp.fade_in(x, 0.8), e["t"] - lead, vel_db(e["vel"]))

# sub drop (synth sine sweep)
for e in by["sub_drop"]:
    tt = np.arange(int(1.4 * SR)) / SR
    f = 38 + 62 * np.exp(-tt / 0.18)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) * np.exp(-tt / 0.55) * np.minimum(tt / 0.004, 1)).astype(np.float32)
    place(stem["sub"], np.stack([x, x]), e["t"], vel_db(e["vel"]) - 3)

# glockenspiel (VCSL) pitched from nearest sample
glk = {79: "glock_medium_G5_01", 84: "glock_medium_C6_01", 91: "glock_medium_G6_01", 96: "glock_medium_C7_01"}
for e in by["glock"]:
    base = min(glk, key=lambda k: abs(k - e["note"]))
    x = dsp.trim(dsp.repitch(S(f"vcsl/{glk[base]}.wav"), e["note"] - base), 2.5, 1.2)
    place(stem["glock"], x, e["t"], vel_db(e["vel"]) - 2, pan=rng.uniform(-0.4, 0.4))
    place(send_hall, x, e["t"], vel_db(e["vel"]) - 6)
    place(send_plate, x, e["t"], vel_db(e["vel"]) - 10)
log("fx placed")

# ---------------------------------------------------------------- Surge XT parts
PATCH = {  # role: (factory patch, midi offset so the part sounds in the written octave)
    "bass": ("Basses/Tacky 1", 0),
    "sub": ("Basses/Sub 2", 0),
    "stab": ("Chords/Minor Chord Retro Stab", 0),
    "dot": ("Plucks/Diamonds", 0),
    "arp": ("Plucks/Diamonds", 0),
    "bleep": ("Plucks/Icebreaker", 0),
    "glass": ("Plucks/Bell 2", 0),
    "pad_a": ("Pads/Bell Pad", 0),
    "pad_b": ("Pads/Computers In Space", 12),
    "fx_up": ("FX/Space Adventure 1", 0),
}
parts = defaultdict(list)
for kind in ("bass", "sub", "stab", "bleep"):
    for e in by[kind]:
        parts[kind].append((e["t"], e["note"], e["len"] * BEAT, e["vel"]))
for e in by["pluck"]:
    parts[e["patch"]].append((e["t"], e["note"], e["len"] * BEAT, e["vel"]))
for e in by["pad"]:
    for n in e["notes"]:
        parts[e["patch"]].append((e["t"], n, e["len"] * BEAT - 0.05, e["vel"]))
for e in by["fx"]:
    parts[e["patch"]].append((e["t"], 72, e["len"] * BEAT, e["vel"]))

synth = Surge()
dest = {"bass": "bass", "sub": "sub", "stab": "stab", "dot": "pluck", "arp": "pluck", "bleep": "pluck",
        "glass": "pluck", "pad_a": "pad", "pad_b": "pad", "fx_up": "fx"}
for role, notes in parts.items():
    patch, off = PATCH[role]
    synth.load(patch)
    y = synth.render(notes, DURATION + TAIL, pitch_offset=off)[:, :N]
    if role in ("bass", "sub"):
        y = dsp.hp(y, 30)
    stem[dest[role]] += y
    log(f"surge {role:6s} <- {patch} ({synth.patch_name}) {len(notes)} notes, rms {dsp.rms_db(y):.1f}")
    if role in ("stab", "dot", "arp", "glass", "bleep"):
        send_delay[:] += y * db(-9 if role != "stab" else -12)
    if role in ("stab", "pad_a", "pad_b", "glass", "fx_up", "dot"):
        send_hall[:] += y * db(-8)

# ---------------------------------------------------------------- "sweep": filter burst on S8
for e in by["sweep"]:
    t0, t1 = e["t"], e["t"] + e["len"] * BEAT
    i0, i1 = int((t0 - 0.02) * SR), int((t1 + 0.02) * SR)
    for k in ("bass", "stab", "hats"):
        seg = stem[k][:, i0:i1].copy()
        lpf = LadderFilter(mode=LadderFilter.Mode.LPF24, cutoff_hz=300, resonance=0.35, drive=1.3)
        y = dsp.automate(lpf, seg, {"cutoff_hz": lambda t: dsp.exp_sweep(t, 0.0, t1 - t0, 260, 14000, 1.6)})
        stem[k][:, i0:i1] = y
# "suck": plate-verbed stab reversed so it swells into the target
plate_full = vst("DragonflyPlateReverb.vst3")
plate_full.dry_level, plate_full.wet_level, plate_full.decay_s = 0.0, 100.0, 2.4
for e in by["suck"]:
    src = bus()
    place(src, stem["stab"][:, int(9.9 * SR):int(10.3 * SR)], 0.0)
    place(src, dsp.trim(clap909, 0.3), 0.0, -4)
    wet = run(plate_full, src[:, :int(3 * SR)], comp=False)
    ln = e["len"] * BEAT
    x = wet[:, ::-1][:, -int(ln * SR) - int(0.4 * SR):]
    x = dsp.fade_in(x[:, : int(ln * SR)], 0.4)
    place(stem["fx"], x, e["t"] - ln, vel_db(e["vel"]) + 4)
log("surge + automation done")

# ---------------------------------------------------------------- stem levels (RMS over active region)
ACTIVE = {  # stem: (t0, t1, target RMS dBFS)
    "kick": (2.0, 6.0, -15.5), "clap": (2.0, 6.0, -23.5), "hats": (2.0, 6.0, -27.0),
    "perc": (0.0, 16.0, -31.0), "bass": (2.0, 6.0, -19.0), "sub": (6.0, 8.0, -21.0),
    "stab": (2.0, 5.0, -25.5), "pluck": (3.5, 5.0, -27.0), "pad": (6.0, 8.0, -25.0),
    "glock": (6.0, 8.0, -30.0), "fx": (0.0, 16.0, -24.0), "crash": (0.0, 16.0, -28.5),
}
for k, (a, b, target) in ACTIVE.items():
    stem[k] = dsp.normalize_rms(stem[k], target, a, b)
# per-section trims (dB) with short ramps: S9 LENS is a still moment carried by the glass pluck
SECTION_GAIN = [("sub", 12.0, 14.0, -9.0), ("pluck", 12.0, 14.0, 9.0), ("kick", 12.0, 14.0, -3.0),
                ("pad", 12.0, 14.0, -2.0)]
for k, a, b, g in SECTION_GAIN:
    curve = np.ones(N, np.float32)
    i0, i1, r = int(a * SR), int(b * SR), int(0.03 * SR)
    curve[i0:i1] = db(g)
    curve[i0 - r:i0] = np.linspace(1, db(g), r)
    curve[i1:i1 + r] = np.linspace(db(g), 1, r)
    stem[k] *= curve
log("stems normalised")

# ---------------------------------------------------------------- send returns
kicks = [e["t"] for e in by["kick"]]
duck = dsp.duck_env(N, kicks, depth_db=-9, release=0.16)
duck_ret = dsp.duck_env(N, kicks, depth_db=-6, release=0.22)

hall = vst("DragonflyHallReverb.vst3")
hall.dry_level, hall.early_level, hall.late_level = 0.0, 15.0, 100.0
hall.size_m, hall.decay_s, hall.predelay_ms = 32.0, 2.4, 14.0
hall.low_cut_hz, hall.high_cut_hz, hall.width = 160.0, 9500.0, 130.0
plate = vst("DragonflyPlateReverb.vst3")
plate.dry_level, plate.wet_level, plate.decay_s = 0.0, 100.0, 1.1
plate.low_cut_hz, plate.high_cut_hz, plate.algorithm = 200.0, 12000.0, "Tank"
dly = vst("Surge XT Effects.vst3")
dly.fx_type = "Delay"
P = dly.parameters
P["input_channel"].raw_value = 0.5
P["delay_time_left"].raw_value = (np.log2(0.375) + 8) / 13      # dotted 8th
P["delay_time_right"].raw_value = (np.log2(0.25) + 8) / 13      # 8th
dly.feedback_eq_feedback = 38.0
dly.feedback_eq_crossfeed = 20.0
dly.feedback_eq_low_cut = 320.0
dly.feedback_eq_high_cut = 6500.0
dly.output_mix = 100.0
P["output_width"].raw_value = 0.75

ret_hall = run(hall, send_hall, comp=False) * duck_ret
ret_plate = run(plate, send_plate, comp=False) * duck_ret
ret_delay = run(dly, send_delay, comp=False) * duck_ret
log(f"returns: hall {dsp.rms_db(ret_hall):.1f} plate {dsp.rms_db(ret_plate):.1f} delay {dsp.rms_db(ret_delay):.1f} dBFS")
returns = dsp.normalize_rms(ret_hall, -30.0, 6.0, 8.0) + dsp.normalize_rms(ret_plate, -32.0, 2.0, 6.0) \
    + dsp.normalize_rms(ret_delay, -33.0, 2.0, 6.0)

# ---------------------------------------------------------------- sidechain + buses
for k in ("bass", "stab", "pad", "pluck"):
    stem[k] *= duck
drums = stem["kick"] + stem["clap"] + stem["hats"] + stem["perc"]
drums_t = run(tape(35.0, 0.62, 0.55), drums)
drums_t = np.asarray(Compressor(threshold_db=-14, ratio=3.0, attack_ms=6, release_ms=90).process(drums_t, SR), np.float32)
bassbus = stem["bass"] + stem["sub"]
bass_t = dsp.mono(run(tape(60.0, 0.7, 0.6), bassbus))
music = stem["stab"] + stem["pluck"] + stem["pad"] + stem["glock"]
fxbus = stem["fx"] + stem["crash"]


# ---------------------------------------------------------------- stutter edit (pre-master)
def stutter(x, t0, length):
    y = x.copy()
    i0 = int(t0 * SR)
    pos = i0
    segs = [(0.0625, 0.125), (0.03125, 0.125)]     # (slice, span) 1/32 then 1/64 note repeats
    for sl, span in segs:
        n_sl = int(sl * SR)
        src = x[:, i0:i0 + n_sl].copy()
        f = int(0.002 * SR)
        src[:, :f] *= np.linspace(0, 1, f)
        src[:, -f:] *= np.linspace(1, 0, f)
        end = pos + int(span * SR)
        while pos < end:
            k = min(n_sl, end - pos)
            y[:, pos:pos + k] = src[:, :k]
            pos += k
    return y


for e in by["stutter"]:
    drums_t = stutter(drums_t, e["t"], e["len"])
    bass_t = stutter(bass_t, e["t"], e["len"])
    stem["stab"] = stutter(stem["stab"], e["t"], e["len"])
    music = stem["stab"] + stem["pluck"] + stem["pad"] + stem["glock"]

mix = drums_t + bass_t + music + fxbus + returns
log(f"pre-master: peak {dsp.peak_db(mix):.1f} dBFS, lufs {dsp.lufs(mix[:, :int(DURATION * SR)]):.1f}")

# ---------------------------------------------------------------- master
m = np.asarray(HighpassFilter(cutoff_frequency_hz=28).process(mix, SR), np.float32)
m = run(tape(25.0, 0.45, 0.5), m)
m = np.asarray(Compressor(threshold_db=-12, ratio=2.0, attack_ms=12, release_ms=140).process(m, SR), np.float32)
m = dsp.fade_out(m[:, :int(DURATION * SR)], 0.8)
target = -12.0


def limit(x, gain_db):
    """Limiter run at 4x oversampling so inter-sample peaks are caught, then a TP safety trim."""
    up = resample_poly(x * db(gain_db), 4, 1, axis=1).astype(np.float32)
    lim = Limiter(threshold_db=-1.4, release_ms=90)
    y = resample_poly(np.asarray(lim.process(up, SR * 4), np.float32), 1, 4, axis=1).astype(np.float32)
    tp = dsp.true_peak_db(y)
    if tp > -1.0:
        y *= db(-1.0 - tp - 0.02)
    return y


gain = target - dsp.lufs(m)
for it in range(6):
    out = limit(m, gain)
    L = dsp.lufs(out)
    log(f"limiter pass {it}: in gain {gain:+.2f} dB -> {L:.2f} LUFS, TP {dsp.true_peak_db(out):.2f}")
    if abs(L - target) < 0.25:
        break
    gain += (target - L) * 1.5
log(f"master: {dsp.lufs(out):.2f} LUFS, true peak {dsp.true_peak_db(out):.2f} dBTP")

# ---------------------------------------------------------------- outputs
OUT.mkdir(parents=True, exist_ok=True)
adir = BUILD / "audio"
adir.mkdir(parents=True, exist_ok=True)
dsp.write_wav(OUT / "opus_soundtrack.wav", out, "PCM_24")
cut = int(DURATION * SR)
final_stems = {"drums": drums_t, "bass": bass_t, "music": music, "fx": fxbus, "returns": returns}
for k, v in {**{f"raw_{k}": v for k, v in stem.items()}, **final_stems}.items():
    dsp.write_wav(adir / f"stem_{k}.wav", v[:, :cut], "FLOAT")


def env(x):
    e = dsp.env_follow(x[:, :cut], NFRAMES)
    return e / (e.max() + 1e-9)


# 48-band log spectrum per video frame
f, t, Z = stft(out.mean(0), SR, nperseg=4096, noverlap=4096 - SR // FPS, boundary=None, padded=True)
edges = np.geomspace(35, 16000, 49)
spec = np.zeros((NFRAMES, 48), np.float32)
P = np.abs(Z) ** 2
for bnd in range(48):
    sel = (f >= edges[bnd]) & (f < edges[bnd + 1])
    v = P[sel].mean(axis=0) if sel.any() else np.zeros(P.shape[1])
    spec[:, bnd] = 10 * np.log10(v[:NFRAMES] + 1e-12) if v.size >= NFRAMES else \
        np.pad(10 * np.log10(v + 1e-12), (0, NFRAMES - v.size), constant_values=-120)
spec = np.clip((spec - spec.max() + 70) / 70, 0, 1)
np.savez_compressed(
    adir / "analysis.npz",
    kick=env(stem["kick"]), clap=env(stem["clap"]), hats=env(stem["hats"]), bass=env(bass_t),
    fx=env(stem["fx"]), crash=env(stem["crash"]), music=env(music), master=env(out), spec=spec,
    fps=FPS, nframes=NFRAMES)

mixlog = {"lufs": dsp.lufs(out), "true_peak": dsp.true_peak_db(out), "sections": {}, "stems_rms": {}}
for sid, name, b0, b1, *_ in SCENES:
    a, b = b0 * BEAT, b1 * BEAT
    mixlog["sections"][f"{sid} {name}"] = {"lufs": round(dsp.lufs(out, a, b), 2) if b - a >= 0.4 else None,
                                           "rms": round(dsp.rms_db(out, a, b), 2)}
    mixlog["stems_rms"][sid] = {k: round(dsp.rms_db(v, a, b), 1) for k, v in final_stems.items()}
json.dump(mixlog, open(adir / "mixlog.json", "w"), indent=1, default=float)
json.dump(mixlog, open(OUT / "mixlog.json", "w"), indent=1, default=float)
log("section RMS/LUFS:")
for k, v in mixlog["sections"].items():
    print(f"   {k:12s} lufs {v['lufs']}  rms {v['rms']}   stems {mixlog['stems_rms'][k.split()[0]]}")
log("done")
