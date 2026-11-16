#!/usr/bin/env python3
"""Cover for reel B (1080x1920). Key content kept inside the centre 4:5 crop (y 285..1635) used by the profile grid."""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
sys.argv = [sys.argv[0], "x", sys.argv[1], "x", "x"]  # reuse helpers without running the pipeline
import importlib.util, os
spec = importlib.util.spec_from_file_location("mw", "/home/user/lesson/make_wall_reels.py")
FREEZE, LOGO, OUT = os.environ["FREEZE"], "/home/user/lesson/remotion/public/logo.jpg", os.environ["OUT"]
FONT = "/home/user/lesson/remotion/public/fonts/Heebo-900.ttf"
W, H = 1080, 1920
bg = Image.open(FREEZE).convert("RGB").resize((W, H))
bg = ImageEnhance.Brightness(bg).enhance(0.62)
d = ImageDraw.Draw(bg, "RGBA")
f = ImageFont.truetype(FONT, 118, layout_engine=ImageFont.Layout.RAQM)
lines = ["שלב אחד", "שהצבעי שלך", "דילג עליו."]
lh = 150
total = lh * len(lines)
y0 = 760 - total // 2
for i, l in enumerate(lines):
    cy = y0 + i * lh + lh // 2
    d.text((540, cy), l, font=f, fill=(255, 255, 255, 255), anchor="mm", direction="rtl", language="he",
           stroke_width=10, stroke_fill=(0, 0, 0, 255))
# sub line in a dark box
f2 = ImageFont.truetype(FONT, 66, layout_engine=ImageFont.Layout.RAQM)
s = "תגלה רק אחרי ששילמת."
b = d.textbbox((0, 0), s, font=f2, direction="rtl", language="he")
w, h = b[2] - b[0], 90
d.rounded_rectangle((540 - w / 2 - 34, 1010, 540 + w / 2 + 34, 1010 + h + 30), radius=26, fill=(8, 8, 10, 215))
d.text((540, 1010 + (h + 30) / 2), s, font=f2, fill=(255, 255, 255, 255), anchor="mm", direction="rtl", language="he")
# logo (same badge, round crop) bottom-right inside the 4:5 crop
im = Image.open(LOGO).convert("RGB"); px = im.load(); w0, h0 = im.size
xs = [x for x in range(w0) for y in range(0, h0, 4) if sum(px[x, y]) < 700]
ys = [y for y in range(h0) for x in range(0, w0, 4) if sum(px[x, y]) < 700]
im = im.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1)); sz = min(im.size)
im = im.crop(((im.width - sz) // 2, (im.height - sz) // 2, (im.width - sz) // 2 + sz, (im.height - sz) // 2 + sz))
m = Image.new("L", (sz * 4, sz * 4), 0); ImageDraw.Draw(m).ellipse((6, 6, sz * 4 - 7, sz * 4 - 7), fill=255)
im = im.convert("RGBA"); im.putalpha(m.resize((sz, sz), Image.LANCZOS)); im = im.resize((260, 260), Image.LANCZOS)
bg.paste(im, (700, 1340), im)
bg.save(OUT)
