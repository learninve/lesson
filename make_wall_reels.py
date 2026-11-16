#!/usr/bin/env python3
"""Colortek drywall reels: 3 hook variants (A/B/C), 1080x1920, 30fps, 20.0s.

usage: make_wall_reels.py <src.mp4> <logo-image> <outdir> <workdir>

Timeline (identical for all variants except 0-3s):
  0-3   hook (A rough seams / B frozen close-up / C finished wall -> cut to "before")
  3-15  body: 7 jump cuts, each starting on a trowel pull
  15-17 result: slow motion + freeze on the last source frame
  17-20 end card (dark, logo, CTA)
Overlay logo top-left on the whole 20s at 70% opacity.
"""
import subprocess, sys, os, json
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC, LOGO, OUT, WORK = sys.argv[1:5]
os.makedirs(OUT, exist_ok=True); os.makedirs(WORK, exist_ok=True)
FONT = "/home/user/lesson/remotion/public/fonts/Heebo-900.ttf"
W, H = 1080, 1920
BR = os.environ.get("LOGO_BR") == "1"
LOGO_XY = (684, 1600) if BR else (44, 130)
VARIANTS = os.environ.get("VARIANTS", "ABC")
CX = 540                    # text is centred here, max width 760 -> x in [160, 920]
MAXW = 760                  # keeps clear of the right-hand button column
# safe vertical zone: 10%..80% (192..1536)

# ---------------------------------------------------------------- body plan
# (src_start, src_end, speed)  -> out duration = (end-start)/speed
BODY = [
    (3.00, 5.25, 1.5),    # pull 1, long            1.5s
    (5.25, 6.25, 0.5),    # pull that kills the seam, slow-mo  2.0s
    (6.25, 8.25, 1.0),    # return pass, normal     2.0s
    (9.00, 12.00, 1.5),   # long pull               2.0s
    (13.60, 15.85, 1.5),  # long pull               1.5s
    (15.85, 18.10, 1.5),  # long pull               1.5s
    (18.20, 20.45, 1.5),  # long pull               1.5s
]
assert abs(sum((e - s) / v for s, e, v in BODY) - 12.0) < 1e-6
RES_SRC = (20.10, 20.80)   # result: slow-mo x0.5, then freeze on the last frame
LAST_T = 20.70             # last source frame lives in [20.70, 20.80)
TXT_MID = (4.60, 6.40)
TXT_RES = (15.10, 16.45)


def run(cmd):
    print(" ".join(map(str, cmd))[:300], "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-3000:]); sys.exit(1)
    return r


# ---------------------------------------------------------------- assets
def font(sz):
    return ImageFont.truetype(FONT, sz, layout_engine=ImageFont.Layout.RAQM)

def tw(d, s, f):
    b = d.textbbox((0, 0), s, font=f, direction="rtl", language="he")
    return b[2] - b[0]

def caption_png(lines, path, size=84, pad=(38, 26), alpha=0.80):
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    while True:
        f = font(size)
        widths = [tw(d0, l, f) for l in lines]
        if max(widths) + 2 * pad[0] <= MAXW or size <= 40:
            break
        size -= 2
    lh = int(size * 1.25)
    bw, bh = max(widths) + 2 * pad[0], lh * len(lines) + 2 * pad[1] - int(size * 0.1)
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=30, fill=(8, 8, 10, int(255 * alpha)))
    for i, l in enumerate(lines):
        d.text((bw / 2, pad[1] + i * lh + lh / 2 - size * 0.05), l, font=f, fill=(255, 255, 255, 255),
               anchor="mm", direction="rtl", language="he")
    im.save(path)
    return im.size, size

def round_logo(sz, opacity=1.0):
    im = Image.open(LOGO).convert("RGB")
    px = im.load(); w, h = im.size
    xs = [x for x in range(w) for y in range(0, h, 4) if sum(px[x, y]) < 700]
    ys = [y for y in range(h) for x in range(0, w, 4) if sum(px[x, y]) < 700]
    box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    im = im.crop(box)
    s = min(im.size); im = im.crop(((im.width - s) // 2, (im.height - s) // 2,
                                    (im.width - s) // 2 + s, (im.height - s) // 2 + s))
    m = Image.new("L", (s * 4, s * 4), 0)
    ImageDraw.Draw(m).ellipse((6, 6, s * 4 - 7, s * 4 - 7), fill=255)   # inset to drop the white fringe
    m = m.resize((s, s), Image.LANCZOS)
    im = im.convert("RGBA"); im.putalpha(m)
    im = im.resize((sz, sz), Image.LANCZOS)
    if opacity < 1:
        a = im.getchannel("A").point(lambda v: int(v * opacity)); im.putalpha(a)
    return im

def make_assets():
    A = {}
    A["A"] = caption_png(["הקיר שלך עקום.", "והצבעי שלך", "יודע את זה."], f"{WORK}/cap_A.png")
    A["B"] = caption_png(["שלב אחד שהצבעי", "שלך דילג עליו.", "תגלה רק אחרי", "ששילמת."], f"{WORK}/cap_B.png")
    A["C"] = caption_png(["יש פה 2 תפרים.", "לא תמצא אף אחד."], f"{WORK}/cap_C.png")
    A["mid"] = caption_png(["כאן הקיר נקבע.", "לא בצבע."], f"{WORK}/cap_mid.png")
    A["res"] = caption_png(["אותו קיר."], f"{WORK}/cap_res.png", size=96)
    if BR:   # logo bottom-right, opaque, covering the footage's own mark
        round_logo(316, 1.0).save(f"{WORK}/logo_corner.png")
    else:
        round_logo(150, 0.70).save(f"{WORK}/logo_corner.png")
    # end card
    bg = Image.new("RGB", (W, H), (14, 15, 18))
    lg = round_logo(540)
    bg.paste(lg, ((W - 540) // 2, 560), lg)
    cta = caption_png(["רוצה קיר כזה?", "הצעת מחיר בהודעה"], f"{WORK}/cap_cta.png", size=80, alpha=0.0)
    ci = Image.open(f"{WORK}/cap_cta.png")
    bg.paste(ci, ((W - ci.width) // 2, 1200), ci)
    bg.save(f"{WORK}/endcard.png")
    # B close-up still: trowel touching the wall (frozen), 1.67x crop
    run(["ffmpeg", "-v", "error", "-ss", "8.3", "-i", SRC, "-frames:v", "1",
         "-vf", "crop=432:768:0:340,scale=1080:1920:flags=lanczos,unsharp=5:5:0.6", f"{WORK}/freezeB.png", "-y"])
    return A

POS = {  # caption centre y
    "A": 640, "B": 640, "C": 640, "mid": 960, "res": 900,
}


# ---------------------------------------------------------------- audio
def audio_seg(i, s, e, v, d):
    f = f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS"
    if v != 1.0:
        f += f",atempo={v}"
    return f + f",aresample=48000,apad,atrim=0:{d}[a{i}]"

def vf_seg(src_s, src_e, v, tag, interp=False):
    n = round((src_e - src_s) / v * 30)
    f = f"[0:v]trim={src_s}:{src_e},setpts=(PTS-STARTPTS)/{v},"
    f += "scale=1080:1920:flags=lanczos,"
    if interp and v < 1:
        f += "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
    f += f"fps=30,tpad=stop_mode=clone:stop_duration=1,trim=end_frame={n},setpts=N/30/TB,format=yuv420p,setsar=1[{tag}]"
    return f


def build_base(variant):
    """17s of picture + audio, no overlays."""
    fc, vs, as_ = [], [], []
    # --- hook (0-3)
    if variant == "A":
        fc.append(vf_seg(0.0, 3.0, 1.0, "h"))
        vs.append("h")
    elif variant == "B":
        vs.append("hB")        # separate input (still), see below
    else:
        fc.append("[0:v]trim=start=%s,setpts=PTS-STARTPTS,scale=1080:1920:flags=lanczos,fps=30,format=yuv420p,setsar=1,"
                  "reverse,trim=end_frame=1,setpts=PTS-STARTPTS,split=2[lf0][lf1]" % LAST_T)
        fc.append("[lf0]loop=loop=59:size=1:start=0,trim=end_frame=60,setpts=N/30/TB[hc1]")
        fc.append(vf_seg(1.65, 2.65, 1.0, "hc2"))
        vs += ["hc1", "hc2"]
    # --- body
    for i, (s, e, v) in enumerate(BODY):
        fc.append(vf_seg(s, e, v, f"b{i}", interp=(v < 1)))
        vs.append(f"b{i}")
    # --- result
    fc.append(vf_seg(RES_SRC[0], RES_SRC[1], 0.5, "r1", interp=True))
    vs.append("r1")
    if variant == "C":
        fc.append("[lf1]loop=loop=17:size=1:start=0,trim=end_frame=18,setpts=N/30/TB[r2]")
    else:
        fc.append("[0:v]trim=start=%s,setpts=PTS-STARTPTS,scale=1080:1920:flags=lanczos,fps=30,format=yuv420p,setsar=1,"
                  "reverse,trim=end_frame=1,setpts=PTS-STARTPTS,loop=loop=17:size=1:start=0,trim=end_frame=18,"
                  "setpts=N/30/TB[r2]" % LAST_T)
    vs.append("r2")
    # pin every picture segment to an exact frame count (hook 90, body 360, result 60)
    # video concat
    fc.append("".join(f"[{t}]" for t in vs) + f"concat=n={len(vs)}:v=1:a=0[vout]")
    # --- audio: hook audio = src[0,3) for every variant, body per clip, result tail
    fc.append(audio_seg("h", 0.0, 3.0, 1.0, 3.0))
    as_.append("ah")
    for i, (s, e, v) in enumerate(BODY):
        fc.append(audio_seg(i, s, e, v, (e - s) / v)); as_.append(f"a{i}")
    fc.append(audio_seg("r", RES_SRC[0], RES_SRC[1], 0.5, 2.0)); as_.append("ar")
    fc.append("".join(f"[{t}]" for t in as_) + f"concat=n={len(as_)}:v=0:a=1[aout]")
    return ";".join(fc)


def make_base(variant):
    fc = build_base(variant)
    inputs = ["-i", SRC]
    if variant == "B":
        # frozen close-up with a very slow push-in (3%), 3.0s
        inputs += ["-loop", "1", "-framerate", "30", "-t", "3", "-i", f"{WORK}/freezeB.png"]
        fc = ("[1:v]scale=w='1080*(1+0.04*t/3)':h=-2:eval=frame,crop=1080:1920,fps=30,format=yuv420p,setsar=1[hB];" + fc)
    out = f"{WORK}/base_{variant}.mkv"
    run(["ffmpeg", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-crf", "10", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-c:a", "pcm_s16le", "-t", "17", out, "-y"])
    return out


def loudness_gain():
    """one measurement pass on the A base audio -> linear gain towards -14 LUFS (applies to all variants)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", f"{WORK}/base_{VARIANTS[0]}.mkv", "-vn", "-af",
                        "highpass=f=70,loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    j = json.loads(r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1])
    print("measured", j)
    return j


def overlay_chain(variant, A):
    """returns (filter string, extra inputs list) applying captions to [0:v] 17s and building the 20s output."""
    caps = []  # (png, name, center_y, t0, t1)
    hook_t = {"A": (0.12, 2.85), "B": (0.12, 2.85), "C": (0.25, 2.85)}[variant]
    caps.append((f"{WORK}/cap_{variant}.png", variant, POS[variant], *hook_t))
    caps.append((f"{WORK}/cap_mid.png", "mid", POS["mid"], *TXT_MID))
    caps.append((f"{WORK}/cap_res.png", "res", POS["res"], *TXT_RES))
    inputs = ["-i", f"{WORK}/base_{variant}.mkv"]
    fc = []
    last = "0:v"
    for k, (png, name, cy, t0, t1) in enumerate(caps, start=1):
        inputs += ["-loop", "1", "-framerate", "30", "-t", str(round(t1 - t0 + 0.1, 3)), "-i", png]
        w, h = Image.open(png).size
        fc.append(f"[{k}:v]format=rgba,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st={round(t1 - t0 - 0.12, 3)}:d=0.12:alpha=1,"
                  f"setpts=PTS+{t0}/TB[c{k}]")
        x, y = int(CX - w / 2), int(cy - h / 2)
        fc.append(f"[{last}][c{k}]overlay=x={x}:y={y}:eof_action=pass:format=auto[v{k}]")
        last = f"v{k}"
    n = len(caps) + 1
    inputs += ["-loop", "1", "-framerate", "30", "-t", "3", "-i", f"{WORK}/endcard.png"]   # input n
    inputs += ["-i", f"{WORK}/logo_corner.png"]                                              # input n+1
    # hard cut to the end card, its content fades in over 0.3s
    fc.append(f"[{n}:v]format=yuv420p,fade=t=in:st=0:d=0.3,setsar=1[end]")
    fc.append(f"[{last}][end]concat=n=2:v=1:a=0[vv]")
    fc.append(f"[vv][{n+1}:v]overlay=x={LOGO_XY[0]}:y={LOGO_XY[1]}:format=auto[vfinal]")
    return ";".join(fc), inputs


def render(variant, A, gain):
    fc, inputs = overlay_chain(variant, A)
    af = (f"[0:a]highpass=f=70,loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={gain['input_i']}:measured_TP={gain['input_tp']}:"
          f"measured_LRA={gain['input_lra']}:measured_thresh={gain['input_thresh']}:offset={gain['target_offset']}:linear=true,"
          "aresample=48000,apad=whole_dur=20,atrim=0:20,afade=t=in:st=0:d=0.05[aout]")
    out = f"{OUT}/colortek_wall_reel_{variant}{'_logo_br' if BR else ''}.mp4"
    run(["ffmpeg", "-v", "error", *inputs, "-filter_complex", fc + ";" + af,
         "-map", "[vfinal]", "-map", "[aout]", "-t", "20",
         "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-maxrate", "3500k", "-bufsize", "7000k",
         "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "30",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart", out, "-y"])
    return out


if __name__ == "__main__":
    A = make_assets()
    print({k: v for k, v in A.items()})
    if not os.environ.get("SKIP_BASE"):
        for v in VARIANTS:
            make_base(v)
    gain = loudness_gain()
    for v in VARIANTS:
        o = render(v, A, gain)
        print(o, os.path.getsize(o) / 1e6, "MB")
