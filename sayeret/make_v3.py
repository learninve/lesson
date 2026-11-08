#!/usr/bin/env python3
"""Sayeret Detailing v3 (= v2 + 3 fixes) - rebuilt from the sharpest still of each raw segment (stills/sNN.png).
Order: dirty -> before/after wipe -> clean -> CTA -> end card. Run: python3 make_v3.py"""
import os, sys, json, math, subprocess
os.environ.setdefault("PHONE", "055-7718519")
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_video as mv          # reuse fonts / text rendering / logo (no side effects beyond setup)

HERE = mv.HERE; OUT = mv.OUT
W, H, FPS, CX = mv.W, mv.H, 30, mv.CX
RAW = mv.RAW
CAP_CY = 1330                      # caption centre: box bottom stays < y=1500
XF = 0.15
END_START, TOTAL = 9.2, 12.0       # end card: 2.5s fully on screen after a 0.3s cross-fade
MAIN_END = 9.5

# ------------------------------------------------------------------ stills
TEXT_STILLS = set(range(0, 12))    # raw frames that carry the burned-in English "Detailing."
def load(i):
    im = cv2.imread(os.path.join(HERE, "stills", f"s{i:02d}.png"))
    if i in TEXT_STILLS:           # remove the burned-in text by inpainting only the glyph pixels
        roi = (slice(494, 556), slice(258, 462))
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); m = np.zeros(g.shape, np.uint8)
        sub = g[roi]; bg = cv2.medianBlur(sub, 31)
        m[roi] = ((sub.astype(int) - bg.astype(int)) > 28).astype(np.uint8) * 255
        m = cv2.dilate(m, np.ones((7, 7), np.uint8))
        im = cv2.inpaint(im, m, 5, cv2.INPAINT_TELEA)
    return Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))

STILLS = {}
def still(i):
    if i not in STILLS: STILLS[i] = load(i)
    return STILLS[i]

SHARP = ImageFilter.UnsharpMask(radius=1.4, percent=45, threshold=2)
def render(i, z):
    src = still(i)
    cw, ch = 720 / z, 1280 / z
    x0, y0 = (720 - cw) / 2, (1280 - ch) / 2
    im = src.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch)).filter(SHARP)
    return mv.grade(im, "before" if i % 2 == 0 else "after")

# ------------------------------------------------------------------ timeline
# (kind, start, end, still(s))   dirty -> wipe -> clean
SHOTS = [
    ("s", 0.00, 1.80, 0),      # hook: dirtiest floor, Ken Burns
    ("s", 1.80, 2.55, 12),     # dirty steering wheel
    ("s", 2.55, 3.30, 20),     # dirty rear floor
    ("s", 3.30, 4.00, 4),      # dirty front floor
    ("w", 4.00, 6.00, (8, 9)), # wipe: pedals / mat before -> after
    ("s", 6.00, 6.85, 13),     # clean wheel + cluster
    ("s", 6.85, 7.70, 17),     # clean rear floor
    ("s", 7.70, 8.40, 21),     # clean rear floor 2
    ("s", 8.40, MAIN_END, 23), # clean hold under the CTA
]
WIPE_T0, WIPE_T1 = 4.0, 6.0

def ease(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)
def wipe_pos(u):
    if u < 0.3: return 0.02
    if u < 1.0: return 0.02 + 0.48 * ease((u - 0.3) / 0.7)
    if u < 1.6: return 0.5
    if u < 2.2: return 0.5 + 0.485 * ease((u - 1.6) / 0.6)
    return 0.985

def label_pill(txt, col):
    t = mv.line_img(txt, 56, sw=0)
    bw, bh = t.width + 64, t.height + 36
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, bw - 1, bh - 1), bh // 2, fill=col)
    im.alpha_composite(t, (32, 18)); return im
PILL_B = label_pill("לפני", (229, 57, 53, 255))
PILL_A = label_pill("אחרי", (46, 158, 79, 255))

def shot_image(shot, t):
    kind, a, b, ref = shot
    z = 1.0 + 0.07 * min(1.0, max(0.0, (t - a) / (b - a)))
    if kind == "s":
        return render(ref, z)
    before, after = render(ref[0], z), render(ref[1], z)
    x = int(wipe_pos((t - a) * 1.3) * W)   # v2 motion compressed from 2.6s to 2.0s
    im = before.copy()
    if x > 0: im.paste(after.crop((0, 0, x, H)), (0, 0))
    d = ImageDraw.Draw(im); d.rectangle((x - 3, 0, x + 3, H), fill=(255, 255, 255))
    d.ellipse((x - 28, H // 2 - 28, x + 28, H // 2 + 28), fill=(255, 255, 255), outline=(30, 30, 30), width=3)
    # fixed labels (after = left, before = right), clear of the logo and the right-hand UI strip
    rgba = im.convert("RGBA")
    rgba.alpha_composite(PILL_A, (50, 250)); rgba.alpha_composite(PILL_B, (960 - PILL_B.width, 250))
    return rgba.convert("RGB")

def main_frame(t):
    k = max(i for i, s in enumerate(SHOTS) if s[1] <= t)
    im = shot_image(SHOTS[k], t)
    if k > 0 and t < SHOTS[k][1] + XF:
        prev = shot_image(SHOTS[k - 1], t)
        im = Image.blend(prev, im, (t - SHOTS[k][1]) / XF)
    return im

# ------------------------------------------------------------------ captions
def card(text, emoji=None, size=66, alpha=200, maxw=760, arrow=False, lines=None):
    if arrow:   # visual order (L->R): אחרי ⬅️ לפני
        parts = [mv.line_img("אחרי", size), mv.emoji_img("⬅️", int(size * .95)), mv.line_img("לפני", size)]
        gap = 24; w = sum(p.width for p in parts) + 2 * gap
        body = Image.new("RGBA", (w, max(p.height for p in parts)), (0, 0, 0, 0)); x = 0
        for p in parts:
            body.alpha_composite(p, (x, (body.height - p.height) // 2)); x += p.width + gap
    else:
        if lines is None: lines = mv.wrap(text, mv.font(size), maxw)
        body = mv.stack([mv.line_img(l, size, emoji if i == len(lines) - 1 else None) for i, l in enumerate(lines)])
    bw, bh = max(560, body.width + 90), max(150, body.height + 60)
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, bw - 1, bh - 1), 40, fill=(10, 10, 12, alpha))
    im.alpha_composite(body, ((bw - body.width) // 2, (bh - body.height) // 2))
    assert CAP_CY + bh // 2 <= 1500 and CX + bw // 2 <= 960, (text, bh, bw)
    return im

CAPS = [
    (0.0, 1.8, card("", "😅", size=92, alpha=215, lines=["הבעלים אמר:", "'זה כבר לא יוצא'"])),
    (1.8, 4.0, card("בוץ, חול, עלים – בכל פינה")),
    (6.0, 8.0, card("ניקוי עמוק במכונת שאיבה מקצועית – כאילו חדש")),
    (8.0, 9.5, card("רוצים ככה? המספר בסוף", "👇")),
]
LOGO_IM = mv.LOGO.resize((int(W * .13),) * 2, Image.LANCZOS)
LOGO_IM.putalpha(LOGO_IM.getchannel("A").point(lambda v: int(v * .85)))

def put(frame, im, cx, cy, alpha=1.0, scale=1.0):
    if alpha <= 0: return
    if scale != 1.0: im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    if alpha < 1.0: im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    frame.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))

def caption_alpha(t, a, b, f=0.12):
    return max(0.0, min(1.0, (t - a) / f, (b - t) / f)) if a <= t < b else 0.0

# ------------------------------------------------------------------ end card
def make_end():
    e = {}
    e["logo"] = mv.LOGO.resize((420, 420), Image.LANCZOS)
    e["name"] = mv.line_img("סיירת דיטיילינג", 104)
    e["sub"] = mv.line_img("ניקוי פנים רכב וחידוש ריפודים", 54)
    size = 150
    while mv.ltr_text(mv.PHONE, size, fill=(18, 18, 18), sw=0).width > 820: size -= 6
    t = mv.ltr_text(mv.PHONE, size, fill=(18, 18, 18), sw=0)
    pill = Image.new("RGBA", (t.width + 90, t.height + 56), (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle((0, 0, pill.width - 1, pill.height - 1), 46, fill=(255, 205, 50, 255))
    pill.alpha_composite(t, (45, 28)); e["phone"] = pill
    e["insta"] = mv.ltr_text(mv.INSTA, 70)
    e["tail"] = mv.line_img("מגיעים עד אליך", 72, "🚗")
    return e
END = make_end()
Y = {}
y = 250 + 210; Y["logo"] = y; y += 210 + 50
for k, gap in (("name", 30), ("sub", 60)):
    Y[k] = y + END[k].height // 2; y += END[k].height + gap
Y["phone"] = y + END["phone"].height // 2; y += END["phone"].height + 60
Y["insta"] = y + END["insta"].height // 2; y += END["insta"].height + 60
Y["tail"] = y + END["tail"].height // 2; y += END["tail"].height
assert y < H - 250, y
SCHED = {"logo": 0.0, "name": 0.15, "sub": 0.3, "phone": 0.45, "insta": 0.85, "tail": 1.05}

def pop(x):           # ease-out-back for the phone number
    x = min(1, max(0, x)); c1 = 1.70158; return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2

_end_bg = None
def end_frame(t):
    global _end_bg
    if _end_bg is None:
        bg = render(23, 1.07).filter(ImageFilter.BoxBlur(28))
        _end_bg = Image.eval(bg, lambda v: int(v * 0.6))
    f = _end_bg.convert("RGBA"); e = t - END_START
    for k, t0 in SCHED.items():
        u = (e - t0) / 0.4
        if u <= 0: continue
        a = min(1.0, u)
        if k == "phone": sc = 0.8 + 0.2 * pop(u) + (0.025 * math.sin((e - t0 - 0.4) * 6) if e - t0 > 0.4 else 0)
        else: sc = 0.92 + 0.08 * ease(u)
        put(f, END[k], CX, Y[k], a, sc)
    return f.convert("RGB")

def full_frame(t):
    if t >= MAIN_END: im = end_frame(t)
    else:
        im = main_frame(t).convert("RGBA")
        for a, b, c in CAPS:
            al = caption_alpha(t, a, b)
            if al > 0: put(im, c, CX, CAP_CY, al)
        put(im, LOGO_IM, W - 50 - LOGO_IM.width / 2, 50 + LOGO_IM.height / 2)
        im = im.convert("RGB")
        if t >= END_START: im = Image.blend(im, end_frame(t), (t - END_START) / (MAIN_END - END_START))
    return im

# ------------------------------------------------------------------ run
def run(cmd, **kw): return subprocess.run(cmd, check=True, **kw)

def cover():
    t = WIPE_T0 + 1.3
    im = shot_image(SHOTS[4], t).convert("RGBA")
    put(im, LOGO_IM, W - 50 - LOGO_IM.width / 2, 50 + LOGO_IM.height / 2)
    ttl = card("לפני / אחרי", size=104, alpha=220)
    put(im, ttl, CX, 1330)
    im.convert("RGB").save(os.path.join(OUT, "sayeret_detailing_v2_cover.png"))

def main():
    n = int(TOTAL * FPS)
    vid = os.path.join(OUT, "_v2video.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    for k in range(n): enc.stdin.write(full_frame(k / FPS).tobytes())
    enc.stdin.close(); enc.wait()
    # audio: keep original soundtrack, fade-out 0.5s at its end, loudnorm -14 LUFS, pad to full length
    adur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=duration", "-select_streams", "a", "-of", "csv=p=0", RAW],
                                capture_output=True, text=True).stdout.strip())
    adur = min(adur, TOTAL)
    base = f"[1:a]atrim=0:{adur},afade=t=out:st={adur-0.5}:d=0.5"
    ln = "loudnorm=I=-14:TP=-1.5:LRA=9"
    m = subprocess.run(["ffmpeg", "-i", RAW, "-af", base.replace("[1:a]", "") + f",{ln}:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
    ln2 = f"{ln}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
    final = os.path.join(HERE, "sayeret_detailing_v3.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", RAW, "-filter_complex",
         f"{base},{ln2},apad=whole_dur={TOTAL}[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-ar", "44100", "-t", str(TOTAL), "-movflags", "+faststart", final])
    os.remove(vid)
    print("done", final)

if __name__ == "__main__":
    main()
