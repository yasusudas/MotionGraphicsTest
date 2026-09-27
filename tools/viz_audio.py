"""One image: master waveform + log spectrogram + stem lanes + section grid."""
import sys

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw
from scipy.signal import stft

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))
from config import BEAT, BUILD, OUT, SCENES, SR  # noqa: E402

W = 1800
master, _ = sf.read(OUT / "opus_soundtrack.wav", always_2d=True)
m = master.mean(1)
dur = len(m) / SR
lanes = ["drums", "bass", "music", "fx", "returns", "raw_kick", "raw_clap", "raw_hats", "raw_pad", "raw_pluck"]

rows = []
# waveform (peak per column)
wf = np.zeros((140, W), np.uint8)
cols = np.array_split(np.abs(m), W)
for x, c in enumerate(cols):
    h = int(min(1, c.max()) * 68)
    wf[70 - h:70 + h + 1, x] = 220
rows.append(("master", wf))
# spectrogram
f, t, Z = stft(m, SR, nperseg=2048, noverlap=2048 - 256)
P = 20 * np.log10(np.abs(Z) + 1e-9)
logf = np.geomspace(30, 18000, 260)
idx = np.searchsorted(f, logf).clip(0, len(f) - 1)
P = P[idx][::-1]
P = np.clip((P - P.max() + 90) / 90, 0, 1)
spec = np.array(Image.fromarray((P * 255).astype(np.uint8)).resize((W, 260)))
rows.append(("spectrogram", spec))
for k in lanes:
    try:
        x, _ = sf.read(BUILD / "audio" / f"stem_{k}.wav", always_2d=True)
    except Exception:
        continue
    e = np.array([np.sqrt(np.mean(c ** 2)) for c in np.array_split(x.mean(1), W)])
    edb = np.clip((20 * np.log10(e + 1e-9) + 60) / 60, 0, 1)
    lane = np.zeros((46, W), np.uint8)
    for xx, v in enumerate(edb):
        lane[46 - int(v * 44):, xx] = 170
    rows.append((k, lane))
H = sum(r[1].shape[0] + 16 for r in rows)
img = Image.new("RGB", (W, H), (12, 12, 13))
d = ImageDraw.Draw(img)
y = 0
for name, arr in rows:
    img.paste(Image.fromarray(arr).convert("RGB"), (0, y + 14))
    d.text((4, y + 1), name, fill=(255, 72, 28))
    y += arr.shape[0] + 16
for sid, name, b0, b1, *_ in SCENES:
    x = int(b0 * BEAT / dur * W)
    d.line([(x, 0), (x, H)], fill=(28, 58, 255), width=1)
    d.text((x + 3, 0), f"{sid} {name}", fill=(205, 255, 36))
for b in range(0, 33):
    x = int(b * BEAT / dur * W)
    d.line([(x, H - 6), (x, H)], fill=(241, 236, 226))
out = BUILD / "viz_audio.png"
img.save(out)
print(out)
