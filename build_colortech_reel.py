#!/usr/bin/env python3
"""ColorTech (קולורטק) Reel pipeline: raw vertical clip -> 1080x1920 Reel with RTL Hebrew overlays.

    python3 build_colortech_reel.py --input RAW.mp4 [--out colortech_reel_final.mp4] [--work DIR]

Steps (all measured on the actual file, nothing guessed):
  1. ffprobe the input.
  2. Pillow -> transparent 1080x1920 RTL Hebrew PNG overlays (raqm/fribidi shaping, so no
     python-bidi is needed) + a programmatic RTL self-test.
  3. FFmpeg: 3 cuts (A 1.25x / B / C) + a 3 s end card, colour grade, ASMR audio chain
     (two-pass loudnorm), a blurred scrim that hides the clip's burned-in English caption,
     timed PNG overlays, logo + price-quote end card.
  4. Extract verification frames and print duration / resolution / size.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
W, H, S = 1080, 1920, 2                      # canvas, supersampling factor
FONT_PATH = HERE / "remotion/public/fonts/Heebo-900.ttf"   # bold modern Hebrew (project font)
EMOJI_PATH = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
LOGO_PATH = HERE / "remotion/public/logo.jpg"              # same file as the uploaded Kolortek badge

WHITE, YELLOW, GREEN, CYAN = (255, 255, 255), (255, 214, 10), (48, 209, 88), (190, 232, 245)
PHONE = "053-3237036"

# ---------------------------------------------------------------- profiles
# segments: (label, src_start, src_end, speed). tail = footage kept under the end card (then frozen),
# tail_audio = source audio window faded out under the end card, scrim = hide a burned-in caption.
# *word* = highlighted. A trailing emoji is placed after the last word, i.e. on the LEFT in RTL.
END_CARD = 3.0                   # seconds
PROFILES = {
    # attached clip #1: 31 s car-seat extraction clip (cuts re-chosen on the real footage)
    "carseat": dict(
        segments=[("A", 5.00, 9.85, 1.25), ("B", 15.00, 21.05, 1.0), ("C", 28.45, 29.80, 1.0)],
        tail=(29.80, 31.05), tail_audio=(29.80, 31.05), scrim=True,
        overlays={
            "ov1": dict(hook=("למה הכתמים במושב *חוזרים* אחרי כמה שבועות? 🤔", WHITE, YELLOW),
                        sub=("שלב 1: קצף שמפרק את הלכלוך עמוק בתוך הבד", CYAN, YELLOW)),
            "ov2": dict(hook=("לא רק לנקות — לשאוב את הלכלוך החוצה ✨", WHITE, YELLOW),
                        sub=("תגבירו רגע: *הסאונד* של השאיבה אומר הכל 🔊", CYAN, GREEN)),
            "ov3": dict(hook=("נקי עד הסיבים. אפס פשרות 👌", WHITE, YELLOW),
                        badge=("*קולורטק* | עבודה עברית", WHITE, YELLOW)),
        }),
    # attached clip #2: 14.4 s drywall joint-compound clip = the footage the original brief was written for;
    # the brief's cut points and copy are used as written (no burned-in caption -> no scrim)
    "drywall": dict(
        segments=[("A", 0.35, 5.20, 1.25), ("B", 6.40, 12.45, 1.0), ("C", 12.45, 13.80, 1.0)],
        tail=(13.75, 13.80), tail_audio=(13.80, 14.20), scrim=False,   # tail = 1 frame, frozen (no camera shake)
        overlays={
            "ov1": dict(hook=("למה רוב חיבורי הגבס *נסדקים* אחרי חצי שנה? 🤔", WHITE, YELLOW),
                        sub=("שלב 1: החדרת החומר לתוך הרשת (בלי כיסי אוויר)", CYAN, YELLOW)),
            "ov2": dict(hook=("לא סתם למרוח — לדחוס וליישר לאפס ✨", WHITE, YELLOW),
                        sub=("תגבירו רגע: *הסאונד* של הגריפה אומר הכל 🔊", CYAN, GREEN)),
            "ov3": dict(hook=("גימור חלק ברמת מראה. אפס פשרות 👌", WHITE, YELLOW),
                        badge=("*קולורטק* | עבודות צבע ושפכטל ברמה אחרת 🎨", WHITE, YELLOW)),
        }),
}


def apply_profile(name):
    global SEGMENTS, TAIL, TAIL_AUDIO, SCRIM, OVERLAYS, DUR, T1, T2, T3, TOTAL
    p = PROFILES[name]
    SEGMENTS, TAIL, TAIL_AUDIO, SCRIM, OVERLAYS = p["segments"], p["tail"], p["tail_audio"], p["scrim"], p["overlays"]
    DUR = [(e - s) / sp for _, s, e, sp in SEGMENTS]
    T1 = DUR[0]; T2 = T1 + DUR[1]; T3 = T2 + DUR[2]; TOTAL = T3 + END_CARD


apply_profile("carseat")

EMOJI_RE = re.compile("^[\U0001F000-\U0001FAFF☀-➿️]+$")


# ================================================================ helpers
def run(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, **kw)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,"
               "sample_rate,channels", "-of", "json", str(path)],
              capture_output=True).stdout
    return json.loads(out)


def font(size):
    return ImageFont.truetype(str(FONT_PATH), int(size * S))


def tlen(f, txt):
    return f.getlength(txt, direction="rtl", language="he")


_emoji_cache = {}


def emoji_img(ch, height):
    key = (ch, height)
    if key not in _emoji_cache:
        f = ImageFont.truetype(EMOJI_PATH, 109)          # CBDT bitmap strike
        im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((20, 20), ch, font=f, embedded_color=True)
        im = im.crop(im.getbbox())
        k = height / im.height
        _emoji_cache[key] = im.resize((max(1, round(im.width * k)), height), Image.LANCZOS)
    return _emoji_cache[key]


def tokenize(markup, base, hi):
    """'a *b* c 🤔' -> logical-order tokens with colour / emoji flags."""
    toks = []
    for w in markup.split():
        mt = re.match(r"^\*(.+?)\*([?!.,:;]*)$", w)        # *word* or *word*? (punctuation stays attached)
        hl = bool(mt)
        w = mt.group(1) + mt.group(2) if mt else w
        toks.append(dict(text=w, color=hi if hl else base, emoji=bool(EMOJI_RE.match(w))))
    return toks


def measure(toks, f, emoji_h):
    for t in toks:
        t["w"] = emoji_img(t["text"], emoji_h).width if t["emoji"] else tlen(f, t["text"])


def break_lines(toks, gap, max_w):
    """Greedy line count, then a balanced split (minimise the widest line) for 2 lines."""
    def width(seq):
        return sum(t["w"] for t in seq) + gap * (len(seq) - 1) if seq else 0
    if width(toks) <= max_w:
        return [toks]
    greedy, cur = [[]], []
    for t in toks:
        trial = cur + [t]
        if cur and not t["emoji"] and width(trial) > max_w:
            greedy.append([t]); cur = [t]
        else:
            greedy[-1].append(t); cur = trial
    if len(greedy) != 2:
        return greedy
    best = None
    for i in range(1, len(toks)):
        if toks[i]["emoji"]:
            continue
        a, b = toks[:i], toks[i:]
        m = max(width(a), width(b))
        if m <= max_w and (best is None or m < best[0]):
            best = (m, [a, b])
    return best[1] if best else greedy


def ink_center(f):
    l, t, r, b = f.getbbox("אלקן", anchor="ls")          # Hebrew ink box around the baseline
    return (t + b) / 2


def draw_pill(canvas, top, text_spec, size, max_w, pad=(44, 24), border=2, y_center=False,
              yellow_border=False):
    """Dark rounded pill with RTL text centred on the canvas. `top` / returns are in 1x pixels."""
    markup, base, hi = text_spec
    f = font(size)
    gap = tlen(f, " ")
    emoji_h = int(size * S * 0.98)
    toks = tokenize(markup, base, hi)
    measure(toks, f, emoji_h)
    lines = break_lines(toks, gap, max_w * S)
    line_h = int(size * S * 1.30)
    lw = [sum(t["w"] for t in ln) + gap * (len(ln) - 1) for ln in lines]
    pw = int(max(lw) + 2 * pad[0] * S)
    ph = int(line_h * len(lines) + 2 * pad[1] * S)
    r = min(ph // 2, 52 * S)
    cx = W * S // 2
    x0 = cx - pw // 2
    y0 = int(top * S) - (ph // 2 if y_center else 0)

    # soft drop shadow
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + 10 * S, x0 + pw, y0 + ph + 10 * S), r, fill=(0, 0, 0, 150))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14 * S)))
    # pill: rgba(15,15,15,215) + 2px 20 % white border composited on top
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((x0, y0, x0 + pw, y0 + ph), r, fill=(15, 15, 15, 215))
    canvas.alpha_composite(layer)
    ring = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    col = (255, 214, 10, 235) if yellow_border else (255, 255, 255, 51)
    ImageDraw.Draw(ring).rounded_rectangle((x0, y0, x0 + pw, y0 + ph), r, outline=col, width=border * S)
    canvas.alpha_composite(ring)

    # text: first logical token sits at the RIGHT edge of the line (RTL), next ones go left
    d = ImageDraw.Draw(canvas)
    off = ink_center(f)
    for li, ln in enumerate(lines):
        yc = y0 + pad[1] * S + line_h * li + line_h / 2
        x = cx + lw[li] / 2                                   # right edge of the line
        for t in ln:
            if t["emoji"]:
                e = emoji_img(t["text"], emoji_h)
                canvas.alpha_composite(e, (int(x - e.width), int(yc - e.height / 2)))
            else:
                d.text((x, yc - off), t["text"], font=f, fill=t["color"] + (255,),
                       anchor="rs", direction="rtl", language="he")
            x -= t["w"] + gap
    return (y0 + ph) / S


def new_canvas():
    return Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))


def finish(canvas, path):
    canvas.resize((W, H), Image.LANCZOS).save(path)


def circular_logo(diameter):
    """Kolortek badge cropped to its circle (the JPEG sits on a white square)."""
    im = Image.open(LOGO_PATH).convert("RGB")
    a = np.asarray(im).astype(int)
    ys, xs = np.where(a.sum(axis=2) < 3 * 238)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    r = (xs.max() - xs.min() + 1) / 2 - 2.5                    # trim the white/green JPEG fringe
    crop = im.crop((round(cx - r), round(cy - r), round(cx + r), round(cy + r))).resize(
        (diameter, diameter), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", (diameter * 4, diameter * 4), 0)
    ImageDraw.Draw(m).ellipse((0, 0, diameter * 4 - 1, diameter * 4 - 1), fill=255)
    crop.putalpha(m.resize((diameter, diameter), Image.LANCZOS))
    return crop


# ================================================================ overlays
def _glyph_x(word_img, ch, f):
    """x position where glyph `ch` best matches inside `word_img` (SSD template matching)."""
    t = Image.new("L", word_img.size, 0)
    ImageDraw.Draw(t).text((20, 100), ch, font=f, fill=255, anchor="ls", direction="rtl", language="he")
    bb = t.getbbox()
    tpl = np.asarray(t.crop((bb[0], 0, bb[2], t.height)), float)
    img = np.asarray(word_img, float)
    w = tpl.shape[1]
    scores = [((img[:, x:x + w] - tpl) ** 2).sum() for x in range(img.shape[1] - w + 1)]
    return int(np.argmin(scores))


def rtl_selftest(work):
    """Glyph-order test (kerning-proof): in a rendered Hebrew word every letter must sit to the
    LEFT of the letter that precedes it in logical order (first letter on the right); the phone
    number must read left-to-right. Uses only letters/digits that occur once in the string."""
    f = ImageFont.truetype(str(FONT_PATH), 90)
    ok = True
    for text, direction in [("קולורטק", "rtl"), ("אבגדה", "rtl"), ("הסאונד", "rtl"), ("עברית", "rtl"),
                            ("להצעת מחיר", "rtl"), (PHONE, "ltr")]:
        img = Image.new("L", (760, 160), 0)
        ImageDraw.Draw(img).text((20, 100), text, font=f, fill=255, anchor="ls", direction="rtl", language="he")
        uniq = [c for c in text if text.count(c) == 1 and c not in " -"]
        xs = [_glyph_x(img, c, f) for c in uniq]
        good = all(a > b for a, b in zip(xs, xs[1:])) if direction == "rtl" else all(a < b for a, b in zip(xs, xs[1:]))
        want = "right -> left" if direction == "rtl" else "left -> right"
        print(f"  RTL self-test {text!r}: logical order must run {want}: {''.join(uniq)} x={xs} -> {'OK' if good else 'FAIL'}")
        ok &= good
    return ok


def make_overlays(work):
    paths = {}
    for key, ov in OVERLAYS.items():
        c = new_canvas()
        bottom = draw_pill(c, 268, ov["hook"], 60, 840)                      # top hook (Y ~ 270)
        if "sub" in ov:
            draw_pill(c, bottom + 20, ov["sub"], 41, 800, pad=(38, 18))      # sub-pill right below
        if "badge" in ov:
            draw_pill(c, 1380, ov["badge"], 50, 800, y_center=True, pad=(46, 22))  # brand badge, Y = 1380
        paths[key] = work / f"{key}.png"
        finish(c, paths[key])

    # end card: logo + price quote + phone (11.28 s ->)
    c = new_canvas()
    logo = circular_logo(520 * S)
    sh = Image.new("RGBA", c.size, (0, 0, 0, 0))
    lx, ly = (W * S - logo.width) // 2, 330 * S
    ImageDraw.Draw(sh).ellipse((lx, ly + 16 * S, lx + logo.width, ly + logo.height + 16 * S), fill=(0, 0, 0, 170))
    c.alpha_composite(sh.filter(ImageFilter.GaussianBlur(26 * S)))
    c.alpha_composite(logo, (lx, ly))
    draw_pill(c, 1000, ("להצעת מחיר", WHITE, YELLOW), 84, 800, pad=(70, 26), y_center=True)
    draw_pill(c, 1195, (PHONE, YELLOW, YELLOW), 112, 900, pad=(70, 28), border=4, y_center=True, yellow_border=True)
    draw_pill(c, 1370, ("*קולורטק* · עבודה עברית", WHITE, YELLOW), 44, 800, pad=(44, 18), y_center=True)
    paths["end"] = work / "end.png"
    finish(c, paths["end"])

    # scrim mask: opaque over the burned-in caption (y 165-435), feathered below the pills
    m = np.zeros((560, W), np.uint8)
    for y in range(560):
        m[y, :] = 255 if y <= 470 else int(255 * max(0, (560 - y) / 90))
    paths["mask"] = work / "scrim_mask.png"
    Image.fromarray(m, "L").save(paths["mask"])
    return paths


# ================================================================ ffmpeg
def audio_graph():
    parts, labels = [], []
    for i, (_, s, e, sp) in enumerate(SEGMENTS):
        d = (e - s) / sp
        tempo = f",atempo={sp}" if sp != 1.0 else ""
        parts.append(f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS{tempo},aresample=48000,"
                     f"afade=t=in:d=0.01,afade=t=out:st={d - 0.01:.3f}:d=0.01[a{i}]")
        labels.append(f"[a{i}]")
    ts, te = TAIL_AUDIO
    L = te - ts
    fst = 0.35 if L > 1 else 0.0
    parts.append(f"[0:a]atrim={ts}:{te},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.01,"
                 f"afade=t=out:st={fst}:d={L - fst - 0.05:.2f},apad=whole_dur={END_CARD}[a3]")
    labels.append("[a3]")
    return parts, labels


ASMR_CHAIN = ("highpass=f=220,lowpass=f=9000,equalizer=f=3200:t=q:w=1.2:g=5,"
              "acompressor=threshold=-18dB:ratio=3:attack=10:release=100")
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"


def measure_loudness(src):
    parts, labels = audio_graph()
    g = ";".join(parts) + f";{''.join(labels)}concat=n=4:v=0:a=1[ac];[ac]{ASMR_CHAIN},{LOUDNORM}:print_format=json[ao]"
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(src), "-filter_complex", g,
                        "-map", "[ao]", "-f", "null", "-"], capture_output=True, text=True, check=True)
    return json.loads(re.search(r"\{.*\}", r.stderr, re.S).group(0))


def build_graph(m, fps):
    v = []
    for i, (_, s, e, sp) in enumerate(SEGMENTS):
        setpts = f"(PTS-STARTPTS)/{sp}" if sp != 1.0 else "PTS-STARTPTS"
        v.append(f"[0:v]trim={s}:{e},setpts={setpts},fps={fps},scale={W}:{H}:flags=lanczos,setsar=1[v{i}]")
    ts, te = TAIL
    freeze = END_CARD - (te - ts)
    v.append(f"[0:v]trim={ts}:{te},setpts=PTS-STARTPTS,fps={fps},scale={W}:{H}:flags=lanczos,setsar=1,"
             f"tpad=stop_mode=clone:stop_duration={freeze:.3f}[v3]")
    a, labels = audio_graph()
    cat = "[v0]" + labels[0] + "[v1]" + labels[1] + "[v2]" + labels[2] + "[v3]" + labels[3]
    ln = (f"{LOUDNORM}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    if SCRIM:   # blurred, darkened scrim over the top: hides a burned-in caption in the clip
        scrim_nodes = [
            "[g]split=2[g0][g1]",
            f"[g1]crop={W}:560:0:0,gblur=sigma=28:steps=2,eq=brightness=-0.22:saturation=0.85,format=yuv420p[bl]",
            "[1:v]format=gray[mk]",
            "[bl][mk]alphamerge[blm]",
            "[g0][blm]overlay=0:0:format=auto[s0]",
        ]
    else:
        scrim_nodes = ["[g]null[s0]"]
    g = v + a + [
        f"{cat}concat=n=4:v=1:a=1[vc][ac]",
        # colour grade + texture sharpening (spec)
        "[vc]colorbalance=bs=0.04:bm=0.03,eq=contrast=1.08:brightness=0.02:saturation=0.95,"
        "unsharp=5:5:0.8:5:5:0.0[g]",
        *scrim_nodes,
        # end card background: blur + dim, fading in
        "[s0]split=2[s1][s2]",
        f"[s2]gblur=sigma=22:steps=2,eq=brightness=-0.30:saturation=0.8,format=yuva420p,"
        f"fade=t=in:st={T3:.3f}:d=0.4:alpha=1[dim]",
        "[s1][dim]overlay=0:0:format=auto[s3]",
        # timed RTL overlays
        f"[2:v]format=rgba[o1]",
        f"[3:v]format=rgba,fade=t=in:st={T1:.3f}:d=0.18:alpha=1[o2]",
        f"[4:v]format=rgba,fade=t=in:st={T2:.3f}:d=0.18:alpha=1[o3]",
        f"[5:v]format=rgba,fade=t=in:st={T3 + 0.12:.3f}:d=0.30:alpha=1[o4]",
        f"[s3][o1]overlay=0:0:format=auto:enable='lt(t,{T1:.3f})'[s4]",
        f"[s4][o2]overlay=0:0:format=auto:enable='between(t,{T1:.3f},{T2:.3f})'[s5]",
        f"[s5][o3]overlay=0:0:format=auto:enable='between(t,{T2:.3f},{T3:.3f})'[s6]",
        f"[s6][o4]overlay=0:0:format=auto:enable='gte(t,{T3:.3f})',format=yuv420p[vout]",
        f"[ac]{ASMR_CHAIN},{ln},aresample=48000[aout]",
    ]
    return ";\n".join(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="video_1.mp4")
    ap.add_argument("--out", default="colortech_reel_final.mp4")
    ap.add_argument("--work", default="colortech_work")
    ap.add_argument("--frames-dir", default=".")
    ap.add_argument("--profile", default="carseat", choices=sorted(PROFILES))
    args = ap.parse_args()
    apply_profile(args.profile)
    src, out, work = Path(args.input), Path(args.out), Path(args.work)
    work.mkdir(parents=True, exist_ok=True)

    # 1. inspect
    info = probe(src)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    au = next(s for s in info["streams"] if s["codec_type"] == "audio")
    num, den = map(int, vs["r_frame_rate"].split("/"))
    src_fps = num / den
    fps = round(src_fps) if round(src_fps) in (30, 60) else 60
    print(f"[1] input: {vs['width']}x{vs['height']} @ {src_fps:g} fps, {au['codec_name']} {au['sample_rate']} Hz "
          f"{au['channels']}ch, {float(info['format']['duration']):.2f}s -> output {W}x{H} @ {fps} fps")
    print(f"    timeline: A {DUR[0]:.2f}s + B {DUR[1]:.2f}s + C {DUR[2]:.2f}s = {T3:.2f}s, end card +{END_CARD:.1f}s = {TOTAL:.2f}s")

    # 2. overlays
    print("[2] RTL self-test + overlays")
    if not rtl_selftest(work):
        sys.exit("RTL self-test failed")
    p = make_overlays(work)

    # 3. ffmpeg
    print("[3] loudness pass 1 (loudnorm measurement)")
    m = measure_loudness(src)
    print(f"    measured: I={m['input_i']} LUFS TP={m['input_tp']} dBTP LRA={m['input_lra']}")
    graph = work / "filtergraph.txt"
    graph.write_text(build_graph(m, fps))
    ovs = []
    for k in ("mask", "ov1", "ov2", "ov3", "end"):
        ovs += ["-loop", "1", "-framerate", str(fps), "-t", f"{TOTAL:.3f}", "-i", str(p[k])]
    print("[3] encoding")
    run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "warning", "-stats", "-y", "-i", str(src), *ovs,
         "-filter_complex_script", str(graph), "-map", "[vout]", "-map", "[aout]",
         "-r", str(fps), "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-t", f"{TOTAL:.3f}", "-movflags", "+faststart", str(out)])

    # 4. verification frames + stats
    fd = Path(args.frames_dir)
    for name, t in [("frame_hook.jpg", 1.5), ("frame_asmr.jpg", 6.0), ("frame_end.jpg", 10.5), ("frame_cta.jpg", 13.0)]:
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(t), "-i", str(out), "-frames:v", "1",
             "-q:v", "2", str(fd / name)])
    o = probe(out)
    ov_ = next(s for s in o["streams"] if s["codec_type"] == "video")
    print(f"[4] {out}: duration {float(o['format']['duration']):.2f}s, {ov_['width']}x{ov_['height']}, "
          f"{int(o['format']['size']) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
