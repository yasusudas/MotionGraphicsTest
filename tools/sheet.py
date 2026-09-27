"""Contact sheet: tools/sheet.py DIR PREFIX f1,f2,... OUT.png [cols] [thumb_w]"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

d, prefix, frames, out = Path(sys.argv[1]), sys.argv[2], [int(x) for x in sys.argv[3].split(",")], sys.argv[4]
cols = int(sys.argv[5]) if len(sys.argv) > 5 else 4
tw = int(sys.argv[6]) if len(sys.argv) > 6 else 480
th = tw * 9 // 16
rows = (len(frames) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (tw + 6) + 6, rows * (th + 24) + 6), (40, 40, 40))
dr = ImageDraw.Draw(sheet)
for i, f in enumerate(frames):
    p = d / f"{prefix}{f:04d}.png"
    x, y = 6 + (i % cols) * (tw + 6), 6 + (i // cols) * (th + 24)
    if p.exists():
        sheet.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y + 18))
    dr.text((x, y + 3), f"f{f}  {f / 30:5.2f}s  b{f / 15:5.2f}", fill=(255, 200, 60))
sheet.save(out)
print(out)
