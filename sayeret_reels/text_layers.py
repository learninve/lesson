"""Hebrew (RTL) text layers rendered as 1080x1920 RGBA PNGs with Pillow + python-bidi.

Each word is bidi-reordered on its own (get_display) and placed right-to-left, so the
reading order is correct and a per-word colour (the "key word") is possible.
Safe zones (1080x1920): nothing in the top 250 px, bottom 450 px, right 130 px.
"""
import itertools
import os

from bidi import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM, SAFE_RIGHT = 250, 450, 130
SAFE_X1 = W - SAFE_RIGHT            # 950
SAFE_Y0, SAFE_Y1 = SAFE_TOP, H - SAFE_BOTTOM   # 250 .. 1470
CX = (30 + SAFE_X1) // 2            # horizontal centre of the safe area (490)
MAX_W = 880

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Heebo-VariableFont_wght.ttf")
WHITE, YELLOW, BLACK = (255, 255, 255), (255, 212, 0), (0, 0, 0)


def font(size, weight=900):
    f = ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.BASIC)
    f.set_variation_by_axes([weight])
    return f


def is_ltr_token(s):
    return any(c.isdigit() for c in s) and not any("֐" <= c <= "׿" for c in s)


def disp(s):
    return s if is_ltr_token(s) else get_display(s, base_dir="R")


def words_of(text, key=None, key_color=YELLOW, color=WHITE):
    """[(word, colour)] in logical order; words in `key` (space separated) are coloured."""
    keys = set(key.split()) if key else set()
    return [(w, key_color if w in keys else color) for w in text.split()]


def _line_width(f, words, idxs, space):
    return sum(f.getlength(disp(words[i][0])) for i in idxs) + space * (len(idxs) - 1)


def fit(words, size_max, size_min, max_lines, max_w=MAX_W):
    """Largest size (and fewest, most balanced lines) that fits max_w. Returns (size, lines)."""
    n = len(words)
    for size in range(size_max, size_min - 1, -2):
        f, space = font(size), 0.26 * size
        for nl in range(1, max_lines + 1):
            best = None
            for cuts in itertools.combinations(range(1, n), nl - 1):
                edges = (0,) + cuts + (n,)
                parts = [list(range(edges[i], edges[i + 1])) for i in range(nl)]
                widths = [_line_width(f, words, p, space) for p in parts]
                if max(widths) <= max_w and (best is None or max(widths) < best[0]):
                    best = (max(widths), parts)
            if best:
                return size, best[1]
    raise ValueError("text does not fit: " + " ".join(w for w, _ in words))


def draw_block(layer, words, size_max, cy, size_min=40, max_lines=3, stroke_ratio=0.10,
               size=None, cx=CX):
    """Draw a centred block of words; returns (size, bbox_of_block)."""
    if size is None:
        size, lines = fit(words, size_max, size_min, max_lines)
    else:
        _, lines = fit(words, size, size, max_lines)
    f, space = font(size), 0.26 * size
    sw = max(2, round(size * stroke_ratio))
    lh = size * 1.16
    total_h = lh * len(lines)
    y = cy - total_h / 2 + lh / 2
    shadow = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shadow)
    d = ImageDraw.Draw(layer)
    x_min, x_max = W, 0
    for part in lines:
        lw = _line_width(f, words, part, space)
        x_right = cx + lw / 2
        x_min, x_max = min(x_min, cx - lw / 2), max(x_max, cx + lw / 2)
        for i in part:
            txt, col = words[i]
            s = disp(txt)
            wl = f.getlength(s)
            x_left = x_right - wl
            sd.text((x_left, y + size * 0.06), s, font=f, fill=200, anchor="lm", stroke_width=sw)
            d.text((x_left, y), s, font=f, fill=col + (255,), anchor="lm",
                   stroke_width=sw, stroke_fill=BLACK + (255,))
            x_right = x_left - space
        y += lh
    # soft drop shadow, composited below the glyphs by compose()
    shadow = shadow.filter(ImageFilter.GaussianBlur(size * 0.07))
    return size, (x_min - sw, cy - total_h / 2 - sw, x_max + sw, cy + total_h / 2 + sw), shadow


def compose(blocks, panel=None):
    """blocks: list of dict(words, size_max, cy, [size, max_lines, size_min]).
    panel: optional (x0,y0,x1,y1,alpha) rounded dark panel behind everything."""
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if panel:
        x0, y0, x1, y1, a = panel
        pd = ImageDraw.Draw(base)
        pd.rounded_rectangle((x0, y0, x1, y1), radius=44, fill=(0, 0, 0, a))
    for b in blocks:
        glyphs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _, _, shadow = draw_block(glyphs, **b)
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh.putalpha(shadow.point(lambda v: int(v * 0.55)))
        base.alpha_composite(sh)
        base.alpha_composite(glyphs)
    return base


def watermark(text="@sayeret_clean", alpha=0.55, size=34, y=268, x=52):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f = ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.BASIC)
    f.set_variation_by_axes([800])
    tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((x, y), text, font=f, fill=WHITE + (255,), anchor="lm", stroke_width=3, stroke_fill=BLACK + (255,))
    tmp.putalpha(tmp.getchannel("A").point(lambda v: int(v * alpha)))
    layer.alpha_composite(tmp)
    return layer


def check_safe(img, name):
    a = img.getchannel("A").point(lambda v: 255 if v > 8 else 0)
    bbox = a.getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        ok = x1 <= SAFE_X1 and y0 >= SAFE_Y0 and y1 <= SAFE_Y1
        print(f"  {name:<10} bbox={bbox} safe={'OK' if ok else 'VIOLATION'}")
        assert ok, f"{name} breaks the safe zone: {bbox}"
    return bbox


# ----------------------------------------------------------------------------- content
HOOKS = {
    "A": ("חושבים שהמושבים שלכם נקיים?", "נקיים?"),
    "B": ("על זה אתם יושבים כל יום", "יושבים"),
    "C": ("כמה לכלוך יוצא ממושב אחד?", "לכלוך"),
}
CAPTIONS = {
    "c1": ("זה מה שיוצא ממושב אחד", "שיוצא"),
    "c2": ("שטיפה ושאיבה מעומק הריפוד", "הריפוד"),
    "c3": ("המושב האחורי היה יותר גרוע", "גרוע"),
}
HOOK_CY = 480
CAP_CY = 1170


def build_all(outdir):
    os.makedirs(outdir, exist_ok=True)
    out = {}
    for k, (t, key) in HOOKS.items():
        img = compose([dict(words=words_of(t, key), size_max=128, cy=HOOK_CY, max_lines=2, size_min=80)])
        out[f"hook_{k}"] = img
    for k, (t, key) in CAPTIONS.items():
        out[k] = compose([dict(words=words_of(t, key), size_max=112, cy=CAP_CY, max_lines=3, size_min=60)])
    # --- end card: brand + offer + phone, on a translucent panel over the video
    brand = words_of("סיירת ניקיון", "סיירת ניקיון")
    offer = words_of("שלחו תמונה של הרכב וקבלו הצעת מחיר בוואטסאפ")
    phone = words_of("055-7718519", "055-7718519")
    y0 = 860
    blocks = [
        dict(words=brand, size_max=128, cy=y0 + 95, max_lines=1, size_min=60),
        dict(words=offer, size_max=70, cy=y0 + 285, max_lines=2, size_min=44),
        dict(words=phone, size_max=118, cy=y0 + 475, max_lines=1, size_min=60),
    ]
    out["cta"] = compose(blocks, panel=(36, y0 - 20, SAFE_X1 - 10, y0 + 585, 120))
    out["wm"] = watermark()
    for k, img in out.items():
        img.save(os.path.join(outdir, f"{k}.png"))
        check_safe(img, k)
    return out


if __name__ == "__main__":
    import sys
    build_all(sys.argv[1] if len(sys.argv) > 1 else "layers")
