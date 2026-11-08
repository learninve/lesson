#!/usr/bin/env python3
"""Sayeret Detailing - before/after Reels/TikTok edit.

Usage:
  PHONE=050-1234567 python3 make_video.py [raw.mp4]

Optional env: LOGO=path/to/logo.png (RGBA). If missing, a stand-in logo is generated.
"""
import os, re, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "raw.mp4")
PHONE = os.environ.get("PHONE", "05X-XXXXXXX")
INSTA = "@sayeret.detailing"
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
W, H, FPS = 1080, 1920, 30
FONT = os.path.join(HERE, "fonts", "Heebo.ttf")
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
CX = 510                      # centre of the safe area (right 120px reserved for TikTok buttons)
SAFE_L, SAFE_R = 60, 960
CAP_Y = 765                   # centre of the burned-in "Detailing." text after scaling
END_DUR, XFADE = 3.3, 0.3

# ---------------------------------------------------------------- cut detection
def detect_cuts():
    r = subprocess.run(["ffmpeg", "-i", RAW, "-vf", "select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]

CUTS = detect_cuts()
DUR = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", RAW],
                           capture_output=True, text=True).stdout.strip())
BOUNDS = [0.0] + CUTS + [DUR]
# Visual review of every segment: the raw clip alternates dirty / clean from the very first segment
# (segment 0 = dirty "before", 1 = clean "after", ...). Verified by eye on all 24 segments.
assert len(BOUNDS) - 1 == 24, f"unexpected number of segments {len(BOUNDS)-1}"
SEGS = [(BOUNDS[i], BOUNDS[i + 1], "after" if i % 2 else "before") for i in range(len(BOUNDS) - 1)]

def seg_kind(t):
    for a, b, k in SEGS:
        if a <= t < b:
            return k
    return SEGS[-1][2]

# ---------------------------------------------------------------- text helpers
_fc = {}
def font(size, w=800):
    k = (size, w)
    if k not in _fc:
        f = ImageFont.truetype(FONT, size, layout_engine=ImageFont.Layout.RAQM)
        f.set_variation_by_axes([w])
        _fc[k] = f
    return _fc[k]

def text_w(s, f, rtl=True):
    return f.getlength(s, direction="rtl" if rtl else "ltr", language="he" if rtl else None)

def emoji_img(ch, height):
    f = ImageFont.truetype(EMOJI_FONT, 109)
    im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((int(im.width * height / im.height), height), Image.LANCZOS)

def wrap(s, f, maxw):
    lines, cur = [], ""
    for wd in s.split(" "):
        t = (cur + " " + wd).strip()
        if text_w(t, f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = wd
    lines.append(cur)
    return lines

def line_img(s, size, emoji=None, fill=(255, 255, 255), stroke=(0, 0, 0), sw=6, rtl=True):
    """One RTL line; `emoji` is placed at the logical END (= visual left)."""
    f = font(size)
    tw = int(text_w(s, f, rtl)) + 2 * sw + 8
    img = Image.new("RGBA", (tw, int(size * 1.5)), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((tw - sw - 4 if rtl else sw + 4, int(size * 0.2)), s, font=f, fill=fill, stroke_width=sw,
                             stroke_fill=stroke, direction="rtl" if rtl else "ltr", language="he" if rtl else None,
                             anchor="ra" if rtl else "la")
    bb = img.getbbox()
    img = img.crop(bb)
    if emoji:
        e = emoji_img(emoji, int(size * 0.95))
        out = Image.new("RGBA", (e.width + 14 + img.width, max(e.height, img.height)), (0, 0, 0, 0))
        out.alpha_composite(e, (0, (out.height - e.height) // 2))
        out.alpha_composite(img, (e.width + 14, (out.height - img.height) // 2))
        img = out
    return img

def stack(lines, gap=14):
    w = max(l.width for l in lines)
    h = sum(l.height for l in lines) + gap * (len(lines) - 1)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = 0
    for l in lines:
        im.alpha_composite(l, ((w - l.width) // 2, y)); y += l.height + gap
    return im

def caption_card(text, emoji=None, size=70, alpha=255, min_w=640, min_h=200, maxw=780):
    """Full-frame RGBA overlay: rounded dark box + white/black-stroke Hebrew text, centred on (CX, CAP_Y)."""
    f = font(size)
    lines = wrap(text, f, maxw)
    imgs = [line_img(l, size, emoji if i == len(lines) - 1 else None) for i, l in enumerate(lines)]
    body = stack(imgs)
    bw, bh = max(min_w, body.width + 100), max(min_h, body.height + 70)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0 = CX - bw // 2, CAP_Y - bh // 2
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 44, fill=(10, 10, 12, alpha))
    layer.alpha_composite(body, (CX - body.width // 2, CAP_Y - body.height // 2))
    return layer

def ltr_text(s, size, fill=(255, 255, 255), stroke=(0, 0, 0), sw=6):
    return line_img(s, size, fill=fill, stroke=stroke, sw=sw, rtl=False)

# ---------------------------------------------------------------- logo
def get_logo():
    p = os.environ.get("LOGO") or os.path.join(HERE, "logo.png")
    if os.path.exists(p):
        return Image.open(p).convert("RGBA"), True
    # stand-in only: replace by dropping the real logo.png next to this script
    S = 600
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((10, 10, S - 10, S - 10), fill=(16, 16, 18, 255), outline=(255, 190, 40, 255), width=18)
    a = line_img("סיירת", 120, fill=(255, 255, 255), sw=0)
    b = line_img("דיטיילינג", 108, fill=(255, 190, 40), sw=0)
    st = stack([a, b], 8)
    im.alpha_composite(st, ((S - st.width) // 2, (S - st.height) // 2))
    return im, False

LOGO, REAL_LOGO = get_logo()

def logo_layer(width, x, y, opacity):
    lg = LOGO.resize((width, int(LOGO.height * width / LOGO.width)), Image.LANCZOS)
    if opacity < 1:
        a = lg.getchannel("A").point(lambda v: int(v * opacity)); lg.putalpha(a)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); layer.alpha_composite(lg, (x, y))
    return layer

# ---------------------------------------------------------------- overlays
HOOK = caption_card("הבעלים אמר 'זה כבר לא יוצא'", "😅", size=88)
CAP1 = caption_card("בוץ, חול, עלים – בכל פינה", size=78)
ARROW = None
def arrow_card():
    # visual (left->right):  אחרי  ⬅️  לפני   (RTL reading: before on the right, arrow points to "after")
    size = 80
    parts = [line_img("אחרי", size), emoji_img("⬅️", int(size * 0.95)), line_img("לפני", size)]
    gap = 26
    w = sum(p.width for p in parts) + gap * 2
    row = Image.new("RGBA", (w, max(p.height for p in parts)), (0, 0, 0, 0))
    x = 0
    for p in parts:
        row.alpha_composite(p, (x, (row.height - p.height) // 2)); x += p.width + gap
    bw, bh = max(640, row.width + 100), 200
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((CX - bw // 2, CAP_Y - bh // 2, CX + bw // 2, CAP_Y + bh // 2), 44, fill=(10, 10, 12, 255))
    layer.alpha_composite(row, (CX - row.width // 2, CAP_Y - row.height // 2))
    return layer
CAP2 = arrow_card()
CAP4 = caption_card("ניקוי עמוק במכונת שאיבה מקצועית – כאילו חדש", size=66, alpha=215)
CAP5 = caption_card("רוצים ככה? המספר בסוף", "👇", size=70, alpha=215)

def tag_layer(kind):
    txt = "לפני" if kind == "before" else "אחרי"
    col = (229, 57, 53, 255) if kind == "before" else (46, 158, 79, 255)
    t = line_img(txt, 62, sw=0)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bw, bh = t.width + 70, t.height + 40
    x, y = 50, 60
    ImageDraw.Draw(layer).rounded_rectangle((x, y, x + bw, y + bh), bh // 2, fill=col)
    layer.alpha_composite(t, (x + 35, y + 20))
    return layer
TAGS = {"before": tag_layer("before"), "after": tag_layer("after")}
LOGO_L = logo_layer(int(W * 0.13), W - 50 - int(W * 0.13), 50, 0.85)

def overlays_at(t):
    """List of overlay layers for time t (seconds)."""
    L = []
    if t < 2.5: L.append(HOOK)
    elif t < 4.0: L.append(CAP1)
    elif t < 5.5: L.append(CAP2)
    if 5.5 <= t < 7.0: L.append(TAGS[seg_kind(t)])
    if 7.0 <= t < 9.5: L.append(CAP4)
    elif 9.5 <= t: L.append(CAP5)
    L.append(LOGO_L)
    return L

# ---------------------------------------------------------------- picture pipeline
def zoom_at(t):
    base = 1.10  # hides the burned-in caption margins + crop
    if t < 4.0: return base * (1 + 0.06 * t / 4.0)
    if t < 7.0: return base
    return base * (1 + 0.06 * (t - 7.0) / (DUR - 7.0))

def grade(img, kind):
    if kind == "before":   # make the mud pop
        img = ImageEnhance.Contrast(img).enhance(1.18)
        img = ImageEnhance.Color(img).enhance(1.05)
    else:                  # glowing clean
        img = ImageEnhance.Brightness(img).enhance(1.07)
        img = ImageEnhance.Color(img).enhance(1.28)
        img = ImageEnhance.Contrast(img).enhance(1.05)
    return img

SHARP = ImageFilter.UnsharpMask(radius=1.4, percent=45, threshold=2)
def process(src, t, z=None):
    z = z or zoom_at(t)
    cw, ch = src.width / z, src.height / z
    x0, y0 = (src.width - cw) / 2, (src.height - ch) / 2
    im = src.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))
    im = im.filter(SHARP)
    return grade(im, seg_kind(t))

def comp(base, layers):
    b = base.convert("RGBA")
    for l in layers: b.alpha_composite(l)
    return b.convert("RGB")

# end card
def end_overlay():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lw = 420
    layer.alpha_composite(logo_layer(lw, CX - lw // 2, 250, 1.0))
    y = 250 + int(LOGO.height * lw / LOGO.width) + 50
    items = [
        (line_img("סיירת דיטיילינג", 104), 30),
        (line_img("ניקוי פנים רכב וחידוש ריפודים", 54), 60),
    ]
    for im, gap in items:
        layer.alpha_composite(im, (CX - im.width // 2, y)); y += im.height + gap
    # phone: shrink to fit the safe width
    size = 150
    while ltr_text(PHONE, size, sw=7).width > (SAFE_R - SAFE_L): size -= 6
    ph = ltr_text(PHONE, size, fill=(255, 205, 50), sw=7)
    pad = 36
    ImageDraw.Draw(layer).rounded_rectangle((CX - ph.width // 2 - pad, y - 8, CX + ph.width // 2 + pad, y + ph.height + 8), 40, fill=(0, 0, 0, 170))
    layer.alpha_composite(ph, (CX - ph.width // 2, y)); y += ph.height + 60
    ig = ltr_text(INSTA, 70)
    layer.alpha_composite(ig, (CX - ig.width // 2, y)); y += ig.height + 60
    tail = line_img("מגיעים עד אליך", 72, "🚗")
    layer.alpha_composite(tail, (CX - tail.width // 2, y)); y += tail.height
    assert y < H - 250, f"end card text enters bottom 250px: {y}"
    return layer

def read_frames():
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", RAW, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n = 0
    while True:
        buf = p.stdout.read(720 * 1280 * 3)
        if len(buf) < 720 * 1280 * 3: break
        yield n, Image.frombytes("RGB", (720, 1280), buf)
        n += 1

def frame_at(t):
    for n, f in read_frames():
        if n == round(t * FPS):
            return f

# ---------------------------------------------------------------- audio
def synth_audio(total, path):
    sr = 44100
    out = np.zeros(int(total * sr), dtype=np.float32)
    rng = np.random.default_rng(7)
    hits = [a for (a, b, k) in SEGS if 4.0 <= a < 7.0 and k == "after"]
    for h in hits:
        n = int(0.38 * sr); t = np.arange(n) / sr
        noise = rng.standard_normal(n).astype(np.float32)
        # band-pass sweep via moving cutoff: simple one-pole low-pass with rising cutoff, then high-passed
        y = np.zeros(n, dtype=np.float32); s = 0.0
        for i in range(n):
            a = 0.02 + 0.55 * (i / n) ** 1.5
            s += a * (noise[i] - s); y[i] = s
        y = y - np.convolve(y, np.ones(200) / 200, mode="same")
        env = np.sin(np.pi * np.clip(t / 0.38, 0, 1)) ** 2 * 0.6
        whoosh = y * env
        pt = np.arange(int(0.12 * sr)) / sr
        pop = np.sin(2 * np.pi * (700 * np.exp(-pt * 18)) * pt) * np.exp(-pt * 30) * 0.5
        s0 = max(0, int((h - 0.2) * sr))
        out[s0:s0 + n] += whoosh[:len(out) - s0]
        p0 = int(h * sr); out[p0:p0 + len(pop)] += pop[:len(out) - p0]
    pk = np.abs(out).max() or 1
    out = out / pk * 0.7
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return hits

# ---------------------------------------------------------------- main
def main():
    total = DUR + END_DUR - XFADE
    nframes = int(round(total * FPS))
    t_end0 = DUR - XFADE
    print("cuts:", [round(c, 2) for c in CUTS])
    print("segments:", [(round(a, 2), k) for a, b, k in SEGS])

    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p", "-r", str(FPS),
                            "-movflags", "+faststart", os.path.join(OUT, "_video.mp4")], stdin=subprocess.PIPE)
    endov = end_overlay()
    end_base = None
    last = None
    for n, src in read_frames():
        t = n / FPS
        base = process(src, t)
        last = (src, t)
        fr = comp(base, overlays_at(t))
        if t >= t_end0:  # cross-fade into the end card
            if end_base is None:
                z = zoom_at(DUR)
                eb = process(last[0], last[1], z=z).filter(ImageFilter.BoxBlur(28))
                eb = Image.eval(eb, lambda v: int(v * 0.6))   # 40% darker
                end_base = comp(eb, [endov])
            fr = Image.blend(fr, end_base, min(1.0, (t - t_end0) / XFADE))
        enc.stdin.write(fr.tobytes())
    nmain = n + 1
    for k in range(nmain, nframes):
        enc.stdin.write(end_base.tobytes())
    enc.stdin.close(); enc.wait()

    # audio
    wav = os.path.join(OUT, "_fx.wav")
    hits = synth_audio(total, wav)
    print("whoosh at:", [round(h, 2) for h in hits])
    mix = f"[0:a]apad=whole_dur={total},atrim=0:{total},volume=1.0[o];[1:a]volume=0.9[fx];[o][fx]amix=inputs=2:normalize=0:duration=first[m]"
    ln = "loudnorm=I=-14:TP=-1.5:LRA=9"
    meas = subprocess.run(["ffmpeg", "-i", RAW, "-i", wav, "-filter_complex", mix + f";[m]{ln}:print_format=json[x]", "-map", "[x]", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    import json
    j = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    ln2 = f"{ln}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
    fout = f"afade=t=out:st={total-0.5}:d=0.5"
    final = os.path.join(OUT, "sayeret_detailing_before_after.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(OUT, "_video.mp4"), "-i", RAW, "-i", wav,
                    "-filter_complex", mix.replace("[0:a]", "[1:a]").replace("[1:a]volume=0.9", "[2:a]volume=0.9") + f";[m]{ln2},{fout}[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", final], check=True)

    # cover: left = "before" @1s, right = "after" @8s
    fb, fa = frame_at(1.0), frame_at(8.0)
    L, R = process(fb, 1.0), process(fa, 8.0)
    cov = Image.new("RGB", (W, H))
    cov.paste(L.crop((270, 0, 810, H)), (0, 0)); cov.paste(R.crop((270, 0, 810, H)), (540, 0))
    cl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(cl)
    for kind, x0 in (("before", 0), ("after", 540)):
        t = line_img("לפני" if kind == "before" else "אחרי", 150, sw=8)
        col = (229, 57, 53, 255) if kind == "before" else (46, 158, 79, 255)
        x1 = x0 + (540 if kind == "before" else 540)
        # box spans the whole half so the burned-in "Detailing." (left half) is fully covered
        d.rectangle((x0, CAP_Y - 130, x1, CAP_Y + 130), fill=col)
        cl.alpha_composite(t, (x0 + 270 - t.width // 2, CAP_Y - t.height // 2))
    d.rectangle((537, 0, 543, H), fill=(255, 255, 255, 255))
    lw = 300
    cl.alpha_composite(logo_layer(lw, CX - lw // 2 + 30, 110, 1.0))
    ttl = line_img("לפני / אחרי", 110, sw=8)
    bw = ttl.width + 100
    d.rounded_rectangle((540 - bw // 2, 1300, 540 + bw // 2, 1300 + ttl.height + 60), 44, fill=(10, 10, 12, 235))
    cl.alpha_composite(ttl, (540 - ttl.width // 2, 1330))
    comp(cov, [cl]).save(os.path.join(OUT, "sayeret_detailing_cover.jpg"), quality=93)
    for f in ("_video.mp4", "_fx.wav"): os.remove(os.path.join(OUT, f))
    print("logo is", "REAL" if REAL_LOGO else "STAND-IN", "| phone:", PHONE)

if __name__ == "__main__":
    main()
