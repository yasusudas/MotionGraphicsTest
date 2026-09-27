"""A/V sync check on the final MP4.

Extracts a small grey video stream and the audio (f32le) independently with ffmpeg, detects
(a) frames where mean luminance / frame difference jumps and (b) audio onsets from the
log-RMS envelope, then reports, for each scheduled cut in the timeline, the nearest detected
video event and audio onset.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import BUILD, FPS, OUT, SCENES, BEAT  # noqa: E402

mp4 = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "OPUS_motion_16s.mp4"
w, h = 96, 54
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"scale={w}:{h},format=gray",
                      "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
v = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32) / 255
diff = np.r_[0, np.abs(np.diff(v, axis=0)).mean(axis=(1, 2))]
sr = 48000
aud = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-ac", "1", "-ar", str(sr),
                                    "-f", "f32le", "-"], capture_output=True, check=True).stdout, np.float32)
hop = sr // 200
n = len(aud) // hop
rms = np.sqrt((aud[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-10)
lr = 20 * np.log10(rms)
onset = np.maximum(0, np.diff(lr, prepend=lr[0]))          # 5 ms resolution


def peak_near(sig, t, rate, win):
    i0, i1 = int(max(0, (t - win) * rate)), int(min(len(sig), (t + win) * rate + 1))
    i = i0 + int(np.argmax(sig[i0:i1]))
    return i / rate, float(sig[i])


rows = []
for sid, name, b0, *_ in SCENES[1:]:
    t = b0 * BEAT
    tv, sv = peak_near(diff, t, FPS, 0.12)
    ta, sa = peak_near(onset, t, 200, 0.06)
    rows.append({"cut": f"{sid} {name}", "t": t, "video_event": round(tv, 3), "audio_onset": round(ta, 3),
                 "av_offset_ms": round((tv - ta) * 1000, 1), "video_strength": round(sv, 3)})
for r in rows:
    print(f"{r['cut']:10s} sched {r['t']:6.3f}s  video {r['video_event']:6.3f}s  audio {r['audio_onset']:6.3f}s"
          f"  offset {r['av_offset_ms']:+6.1f} ms")
off = [abs(r["av_offset_ms"]) for r in rows]
print(f"frames {len(v)}  audio {len(aud) / sr:.3f}s  max |offset| {max(off):.1f} ms  (1 frame = {1000 / FPS:.1f} ms)")
json.dump(rows, open(BUILD / "qa_sync.json", "w"), indent=1)
