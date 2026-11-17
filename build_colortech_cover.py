#!/usr/bin/env python3
"""Reel cover (1080x1920) for the ColorTech reel. Reuses the RTL pill/logo helpers of build_colortech_reel.py.
    python3 build_colortech_cover.py --input RAW.mp4 [--t 5.6] [--out colortech_cover.jpg]
Keep text/logo inside the centre 3:4 (y 240-1680) so the profile-grid crop never cuts them."""
import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

import build_colortech_reel as b

ap = argparse.ArgumentParser()
ap.add_argument("--input", required=True)
ap.add_argument("--t", type=float, default=5.6)
ap.add_argument("--out", default="colortech_cover.jpg")
ap.add_argument("--hook", default="למה הכתמים *חוזרים*?")
ap.add_argument("--sub", default="ככה מנקים מושב באמת 🧽")
ap.add_argument("--no-scrim", action="store_true", help="clip has no burned-in caption")
a = ap.parse_args()
W, H, S = b.W, b.H, b.S

with tempfile.TemporaryDirectory() as td:
    fr = Path(td) / "f.png"
    # same upscale + grade as the reel
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(a.t), "-i", a.input, "-frames:v", "1",
                    "-vf", f"scale={W}:{H}:flags=lanczos,colorbalance=bs=0.04:bm=0.03,"
                           "eq=contrast=1.08:brightness=0.02:saturation=0.95,unsharp=5:5:0.8:5:5:0.0", str(fr)], check=True)
    base = Image.open(fr).convert("RGB")

# scrim over the burned-in English caption (same idea as the reel)
top = ImageEnhance.Brightness(base.crop((0, 0, W, 560)).filter(ImageFilter.GaussianBlur(28))).enhance(0.72)
m = np.array([255 if y <= 470 else int(255 * max(0, (560 - y) / 90)) for y in range(560)], np.uint8)
if not a.no_scrim:
    base.paste(top, (0, 0), Image.fromarray(np.repeat(m[:, None], W, 1), "L"))
# soft bottom vignette so the logo pops
g = np.array([int(150 * max(0, (y - 1250) / 670)) for y in range(H)], np.uint8)
base = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), base, Image.fromarray(np.repeat(g[:, None], W, 1), "L"))

c = b.new_canvas()
bottom = b.draw_pill(c, 330, (a.hook, b.WHITE, b.YELLOW), 104, 800, pad=(56, 30), border=4, yellow_border=True)
b.draw_pill(c, bottom + 26, (a.sub, b.CYAN, b.YELLOW), 58, 800, pad=(46, 22))
logo = b.circular_logo(250 * S)
lx, ly = 70 * S, 1290 * S
sh = Image.new("RGBA", c.size, (0, 0, 0, 0))
ImageDraw.Draw(sh).ellipse((lx, ly + 12 * S, lx + logo.width, ly + logo.height + 12 * S), fill=(0, 0, 0, 170))
c.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20 * S)))
c.alpha_composite(logo, (lx, ly))
out = base.convert("RGBA")
out.alpha_composite(c.resize((W, H), Image.LANCZOS))
out.convert("RGB").save(a.out, quality=95)
print("saved", a.out)
