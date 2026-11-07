#!/usr/bin/env python3
"""Builds transparent 1080x1920 PNG text/logo layers (Hebrew RTL via Pillow+raqm)."""
import sys, os
from PIL import Image, ImageDraw, ImageFont, features
assert features.check('raqm'), "Pillow needs raqm for Hebrew shaping/RTL"
logo_path, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
W, H = 1080, 1920
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'Heebo-Bold.ttf')
F = lambda s: ImageFont.truetype(FONT, s)
canvas = lambda: Image.new('RGBA', (W, H), (0, 0, 0, 0))

def text(d, cy, s, size, fill, shadow=False):
    f = F(size)
    kw = dict(font=f, direction='rtl', language='he', anchor='mm')
    if shadow:
        for dx, dy in [(4, 4), (3, 5), (5, 3)]:
            d.text((W/2+dx, cy+dy), s, fill=(0, 0, 0, 230), **kw)
        d.text((W/2, cy), s, fill=fill, stroke_width=0, **kw)
    else:
        d.text((W/2, cy), s, fill=fill, **kw)

logo = Image.open(logo_path).convert('RGBA')
def place_logo(img, w, x=None, y=0, alpha=1.0):
    l = logo.resize((w, round(logo.height*w/logo.width)), Image.LANCZOS)
    if alpha < 1: l.putalpha(l.getchannel('A').point(lambda v: int(v*alpha)))
    img.alpha_composite(l, (x if x is not None else (W-w)//2, y)); return l.height

# 1 title (centre-top, below IG top UI)
im = canvas(); text(ImageDraw.Draw(im), 480, 'החלקת קירות ברמה אחרת', 72, (255,255,255,255), True); im.save(f'{out}/title.png')
# 2 corner logo, 180px wide, 85%, 40px from right edge, below the ~250px IG top area
im = canvas(); place_logo(im, 180, x=W-180-40, y=270, alpha=0.85); im.save(f'{out}/logo_corner.png')
# 3 caption bar (bottom, above ~400px IG bottom area)
im = canvas(); d = ImageDraw.Draw(im); y0, y1 = 1420, 1420+90
d.rectangle([0, y0, W, y1], fill=(0,0,0,150))
text(d, (y0+y1)//2, 'קולורטק | שפכטל · צבע · החלקת קירות', 44, (255,255,255,255)); im.save(f'{out}/caption.png')
# 4 end screen elements, centred stack
lh = round(logo.height*400/logo.width)
im = canvas(); place_logo(im, 400, y=500); im.save(f'{out}/end1_logo.png')
y = 500 + lh + 110
for i, (s, size, col) in enumerate([('לקבלת הצעת מחיר ללא התחייבות', 64, (255,255,255,255)),
                                    ('ליאב 053-323-7036', 80, (255,176,32,255))], start=2):
    im = canvas(); text(ImageDraw.Draw(im), y, s, size, col); im.save(f'{out}/end{i}.png'); y += 120
# WhatsApp line + colour emoji (rendered separately, scaled)
im = canvas(); d = ImageDraw.Draw(im)
f = F(48); s = 'שלחו הודעה בוואטסאפ'
tw = d.textlength(s, font=f, direction='rtl', language='he')
em = Image.new('RGBA', (160, 160), (0,0,0,0))
ImageDraw.Draw(em).text((0,0), '📲', font=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', 109), embedded_color=True)
em = em.crop(em.getbbox()).resize((56, 56), Image.LANCZOS)
total = tw + 16 + 56; x0 = (W-total)/2
d.text((x0+56+16+tw/2, y), s, font=f, fill=(255,255,255,255), direction='rtl', language='he', anchor='mm')
im.alpha_composite(em, (int(x0), int(y-28))); im.save(f'{out}/end4.png')
