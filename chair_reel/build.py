#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py - one-file builder for the Hebrew car-seat cleaning reel (1080x1920, 30fps).

    python3 build.py all          # everything: text -> video -> audio -> final -> cover -> storyboard -> qa
    python3 build.py video        # only the picture engine (work/base.mkv)
    python3 build.py audio        # only the sound (work/audio_final.wav)
    python3 build.py final        # burn Hebrew text + mux -> out/reel_main.mp4, reel_A.mp4, reel_B.mp4
    python3 build.py cover|storyboard|qa

Everything that changes between edits lives in the CONFIG block below (segments, speeds, texts,
SFX, grade).  All other code derives cut times, text timings and audio lengths from it.

Pipeline
  1. video : source frames are decoded as raw YUV420, cropped (title removal) + zoomed + scaled with ONE
             Lanczos resample per plane (no RGB round trip, so colours stay exactly as filmed), then the
             same grade (eq + unsharp) is applied to every frame; 2-frame white flash on the turn.
             Lossless intermediate: work/base.mkv.
  2. text  : ASS files (libass + fribidi, Rubik 800 static instance made with fontTools), sizes auto-fitted
             to <= 900 px per line, positions calibrated by rendering, pop-in animation, soft shadow.
  3. audio : original ASMR sound, atempo on sped-up parts, highpass/afftdn/acompressor, synthesized SFX
             (ffmpeg lavfi), 2-pass loudnorm -> -14 LUFS / -1 dBTP.
  4. final : libx264 High, yuv420p, CRF 18, slow, maxrate 12M, AAC 192k/48k, +faststart.
"""
import json
import math
import os
import re
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)  # every path below is relative to the project folder (also fine on Windows)

# ============================================================================================
# CONFIG
# ============================================================================================
INPUT = "input.mp4"
FPS = 30
OUT_W, OUT_H = 1080, 1920
SRC_W, SRC_H = 720, 1280
# Removes the burned-in English title (measured: y=65..202).  x, y, w, h in the 720x1280 source.
CROP = dict(x=61, y=216, w=598, h=1064)

# One grade for the whole reel (incl. before/after - the "after" is never brightened more than the "before").
GRADE = "eq=contrast=1.06:saturation=1.12,unsharp=5:5:0.6:5:5:0.0"

# Timeline.  `src` = source seconds, `frames` = output frames (30 fps), `speed` = constant factor or
# (from, to, ramp_seconds) for a smooth ramp followed by a hold at `to`.  `zoom` = (start, end) push-in
# about `anchor` (normalised x, y in the output frame).  Cut times are DERIVED from these frame counts.
SEGMENTS = [
    # beat 1 - hook 0.0-2.2: source 1.8-4.0 at 1x, push-in 1.0 -> 1.12 towards the transparent head
    dict(id="hook", beat="hook", src=1.8, frames=66, speed=1.0, zoom=(1.0, 1.12), anchor=(0.26, 0.49)),
    # beat 2 - clean strip vs dirty strip 2.2-4.7: source 23.5-27.25 at 1.5x
    dict(id="stripe", beat="stripe", src=23.5, frames=75, speed=1.5),
    # beat 3 - dirtiest water 4.7-10.3: 1x (so the real suction sound works) then ramp to 3x
    dict(id="dirty1x", beat="dirty", src=27.2, frames=75, speed=1.0),
    dict(id="montage", beat="dirty", src=29.7, frames=93, speed=(1.0, 3.0, 0.2)),
    # beat 5 - the turn at 10.3 (hard cut + whoosh + 2-frame white flash) and the rinse: 49.4-63.0 at 2x
    dict(id="rinse", beat="rinse", src=49.4, frames=204, speed=2.0, flash_frames=2, flash_opacity=0.60),
    # beat 6 - before/after split, each half 1080x960 centred on the cushion, slow zoom 1.0 -> 1.04
    dict(id="ba", beat="ba", kind="split", frames=75, zoom=(1.0, 1.04), audio_src=63.0,
         before=dict(window=(0.0, 0.4), cy=460),       # sharpest frame in the window; wide shot of the dirty cushion
         after=dict(window=(66.0, 66.3), cy=430),      # sharpest frame WITHOUT the tool (65.9-66.3 are tool-free)
         divider_px=6),
    # beat 7 - CTA + loop: source 0.0-1.8 at 1x; ends exactly where the hook starts (1.8) -> seamless loop
    dict(id="cta", beat="cta", src=0.0, frames=54, speed=1.0),
]

# On-screen text.  *words* between asterisks are yellow (#FFD60A), the rest white.  One list item = one line.
TEXTS = {
    "T1": ["אל תנקו את הכיסא", "*לפני שתראו את זה*"],
    "T2": ["יש שלב אחד", "*שכולם מפספסים*"],
    "T3": ["ופה כמעט כולם", "*עוצרים...*"],
    "T4": ["השלב שחסר:", "*שטיפה*"],
    "T5": ["עד שהמים", "*יוצאים נקיים*"],
    "T6": ["אחרת הלכלוך שבספוג", "*עולה בחזרה כשמתייבש*"],
    "T8": ["שלחו למישהו", "*שהאוטו שלו נראה ככה*"],
}
HANDLE = "@sayeret.detailing"
LABELS = dict(before="לפני", after="אחרי")
# Hook variants: only T1 and T2 change.
VARIANTS = {
    "main": {},
    "A": {"T1": ["ניקיתם את הכיסא", "*והכתם חזר?*"], "T2": ["זה בגלל שלב אחד", "*שכולם מפספסים*"]},
    "B": {"T1": ["תסתכלו מה יצא", "*מכיסא אחד באוטו*"], "T2": ["ויש שלב אחד", "*שכולם מפספסים*"]},
}
COVER_HEADLINE = ["*למה הכתם חוזר?*"]

# When each text shows: beat id, start/end in seconds from the beat start (negative = from the beat end,
# None end = until the beat end).  px = font size (CSS-like em size) on the 1080x1920 canvas.
TEXT_EVENTS = [
    dict(key="T1", beat="hook", t0=0.0, t1=None, px=100),
    dict(key="T2", beat="stripe", t0=0.0, t1=None, px=86),
    dict(key="T3", beat="dirty", t0=-1.6, t1=None, px=86),
    dict(key="T4", beat="rinse", t0=0.0, t1=2.2, px=86),
    dict(key="T5", beat="rinse", t0=2.2, t1=4.2, px=86),
    dict(key="T6", beat="rinse", t0=4.2, t1=None, px=86),
    dict(key="T7", beat="ba", t0=0.0, t1=None, px=86),   # before / after labels
    dict(key="T8", beat="cta", t0=0.0, t1=None, px=86),  # + HANDLE underneath
]

# Text style / layout
FONT_FILE = "fonts/RubikReel-800.ttf"          # static instance of Rubik (wght 800), built with fontTools
FONT_FAMILY = "Rubik Reel 800"
RUBIK_VF_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/rubik/Rubik%5Bwght%5D.ttf"
YELLOW = "&H0AD6FF&"                            # ASS is BGR: FFD60A
WHITE = "&HFFFFFF&"
OUTLINE_PX = 8
MAX_LINE_W = 900                                # per line, incl. the outline
BLOCK_TOP_Y = 330                               # top of the (tallest glyph of the) first line
HANDLE_PX, HANDLE_OUTLINE, HANDLE_GAP = 52, 6, 56
LABEL_COLORS = dict(before="&H3539E5&", after="&H5EC522&")   # red E53935, green 22C55E (BGR)
LABEL_TOP = dict(before=300, after=1000)        # top edge of each pill in the video
COVER_LABEL_TOP = dict(before=300, after=1100)
POP_MS = (120, 200)                             # 85% -> 106% in 120 ms -> 100% at 200 ms
FORBIDDEN = dict(top=250, bottom=400, right=140, right_y=(1000, 1700))   # Instagram UI zones

# Audio
SR = 48000
PREROLL_S = 0.5            # real audio that precedes the loop point; processed then trimmed (seamless loop)
TAIL_S = 0.05            # real audio that FOLLOWS the loop point (= start of the hook); lets the AAC encoder close the last frame cleanly
FADE_S = 0.008             # tiny fades only at hard cuts where the source audio is discontinuous
AUDIO_CHAIN = ("highpass=f=80,afftdn=nr=6:nf=-45,"
               "acompressor=threshold=0.125:ratio=2.5:attack=15:release=200:makeup=1")
LOUDNORM = dict(I=-14, TP=-1, LRA=20)
# catches the few loud transients so the 2-pass loudnorm can stay in LINEAR mode (no pumping)
PEAK_LIMITER = "alimiter=limit=0.58:attack=2:release=40:level=disabled"
SFX = [  # kind, beat, offset seconds from beat start, gain
    dict(kind="pop", beat="hook", at=0.0, gain=0.15),
    dict(kind="whoosh", beat="rinse", at=-0.42, gain=0.28),
    dict(kind="pop", beat="rinse", at=0.0, gain=0.15),
    dict(kind="ding", beat="ba", at=0.0, gain=0.16),
    dict(kind="pop", beat="cta", at=0.0, gain=0.15),
]

# Export
X264 = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-maxrate", "12M", "-bufsize", "24M",
        "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p", "-g", "60"]
AAC = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
COLOR_TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]

WORK = "work"
OUTD = "out"

# ============================================================================================
# helpers
# ============================================================================================


def sh(cmd, **kw):
    cmd = [str(c) for c in cmd]
    print("$", " ".join(cmd)[:260] + (" ..." if len(" ".join(cmd)) > 260 else ""), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def ensure_dirs():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUTD, exist_ok=True)
    os.makedirs("fonts", exist_ok=True)


def ensure_font():
    """Rubik is a variable font; libass renders variable fonts too thin, so make a static wght=800 instance."""
    if os.path.exists(FONT_FILE):
        return
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    vf_path = os.path.join(WORK, "Rubik-VF.ttf")
    if not os.path.exists(vf_path):
        sh(["curl", "-fsSL", "-m", "90", "-o", vf_path, RUBIK_VF_URL])
    f = instancer.instantiateVariableFont(TTFont(vf_path), {"wght": 800}, inplace=False)
    name = f["name"]
    for rec in list(name.names):
        if rec.nameID in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25):
            name.removeNames(nameID=rec.nameID)
    for nid, val in ((1, FONT_FAMILY), (2, "Regular"), (3, "RubikReel800;static"),
                     (4, FONT_FAMILY), (6, "RubikReel800-Regular")):
        name.setName(val, nid, 3, 1, 0x409)
        name.setName(val, nid, 1, 0, 0)
    f["OS/2"].usWeightClass = 400
    f["OS/2"].fsSelection = (f["OS/2"].fsSelection & ~0b100001) | 0b1000000
    f["head"].macStyle = 0
    if "STAT" in f:
        del f["STAT"]
    f.save(FONT_FILE)


def ass_cs(frame):
    """Frame -> ASS timestamp, floored to a centisecond with integer maths (so an event never leaks 1 frame)."""
    cs = (frame * 100) // FPS
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


# ----------------------------------------------------------------------------------------------
# timeline
# ----------------------------------------------------------------------------------------------

def speed_at(seg, tau):
    sp = seg.get("speed", 1.0)
    if isinstance(sp, (int, float)):
        return float(sp)
    s0, s1, r = sp
    if tau >= r:
        return s1
    x = tau / r
    return s0 + (s1 - s0) * (x * x * (3 - 2 * x))   # smoothstep ramp


def seg_source_consumption(seg):
    """Source seconds consumed by a clip segment (integral of speed)."""
    n = seg["frames"] * 50
    dt = seg["frames"] / FPS / n
    return sum(speed_at(seg, (i + 0.5) * dt) for i in range(n)) * dt


def source_indices(seg):
    """Source frame index for every output frame of a clip segment."""
    out = []
    dt = 1.0 / 600
    acc, tau = 0.0, 0.0
    for j in range(seg["frames"]):
        target = j / FPS
        while tau < target - 1e-9:
            acc += speed_at(seg, tau + dt / 2) * dt
            tau += dt
        out.append(int(round((seg["src"] + acc) * FPS)))
    return out


def build_timeline():
    t = []
    start = 0
    for s in SEGMENTS:
        seg = dict(s)
        seg["start"] = start
        seg["end"] = start + seg["frames"]
        if seg.get("kind", "clip") == "clip":
            seg["consume"] = seg_source_consumption(seg)
            seg["a_src"] = seg["src"]
        else:
            seg["consume"] = seg["frames"] / FPS
            seg["a_src"] = seg["audio_src"]
        seg["a_end"] = seg["a_src"] + seg["consume"]
        t.append(seg)
        start = seg["end"]
    return t


TIMELINE = build_timeline()
TOTAL_FRAMES = TIMELINE[-1]["end"]
DURATION = TOTAL_FRAMES / FPS


def beat_range(beat):
    segs = [s for s in TIMELINE if s["beat"] == beat]
    return segs[0]["start"], segs[-1]["end"]


def event_frames(ev):
    b0, b1 = beat_range(ev["beat"])
    f0 = b0 + int(round(ev["t0"] * FPS)) if ev["t0"] >= 0 else b1 + int(round(ev["t0"] * FPS))
    if ev["t1"] is None:
        f1 = b1
    else:
        f1 = b0 + int(round(ev["t1"] * FPS)) if ev["t1"] >= 0 else b1 + int(round(ev["t1"] * FPS))
    return f0, f1


# ============================================================================================
# 1. PICTURE ENGINE  (raw YUV420 planes, one Lanczos resample per plane)
# ============================================================================================
FRAME_BYTES = SRC_W * SRC_H * 3 // 2


def read_source_frames(indices):
    """Yield (idx, (Y, U, V)) for the requested ascending frame indices, decoded by ffmpeg as raw yuv420p."""
    first = indices[0]
    ss = max(0.0, (first - 0.5) / FPS)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{ss:.5f}", "-i", INPUT, "-an", "-fps_mode", "passthrough",
           "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    cur, last = first, None
    try:
        for want in indices:
            while cur <= want:
                buf = p.stdout.read(FRAME_BYTES)
                if len(buf) < FRAME_BYTES:
                    raise RuntimeError(f"source ended before frame {want}")
                last = buf
                cur += 1
            y = np.frombuffer(last, np.uint8, SRC_W * SRC_H).reshape(SRC_H, SRC_W)
            u = np.frombuffer(last, np.uint8, SRC_W * SRC_H // 4, SRC_W * SRC_H).reshape(SRC_H // 2, SRC_W // 2)
            v = np.frombuffer(last, np.uint8, SRC_W * SRC_H // 4, SRC_W * SRC_H * 5 // 4).reshape(SRC_H // 2, SRC_W // 2)
            yield want, (y, u, v)
    finally:
        p.stdout.close()
        p.kill()
        p.wait()


def warp(planes, Ax, Bx, Ay, By, out_w, out_h):
    """
    Resample planes with  u_src = Ax*u_dst + Bx ,  v_src = Ay*v_dst + By   (luma-pixel EDGE coordinates).
    Chroma planes use the source's 'left' siting (x at luma sample centre, y between rows), consistent with
    H.264 4:2:0, so the colour stays registered with the luma.
    """
    y, u, v = planes
    fl = cv2.INTER_LANCZOS4
    my = np.float32([[Ax, 0, 0.5 * Ax + Bx - 0.5], [0, Ay, 0.5 * Ay + By - 0.5]])
    mc = np.float32([[Ax, 0, (Ax * 0.5 + Bx - 0.5) / 2], [0, Ay, (Ay * 1.0 + By - 1.0) / 2]])
    fy = cv2.warpAffine(y, my, (out_w, out_h), flags=fl | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    fu = cv2.warpAffine(u, mc, (out_w // 2, out_h // 2), flags=fl | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    fv = cv2.warpAffine(v, mc, (out_w // 2, out_h // 2), flags=fl | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    return fy, fu, fv


def ease(x):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(x, 0.0), 1.0))   # sine ease-in-out


def full_frame_warp(planes, z, anchor):
    """crop (title removal) + scale to 1080x1920 + push-in by z about `anchor` (fixed point of the zoom)."""
    kx, ky = OUT_W / CROP["w"], OUT_H / CROP["h"]
    px, py = anchor[0] * OUT_W, anchor[1] * OUT_H
    Ax, Ay = 1.0 / (kx * z), 1.0 / (ky * z)
    Bx = CROP["x"] + px / kx - px * Ax
    By = CROP["y"] + py / ky - py * Ay
    return warp(planes, Ax, Bx, Ay, By, OUT_W, OUT_H)


def half_warp(planes, cy, z, cx=CROP["w"] / 2):
    """1080x960 window of the cropped frame, full crop-width at z=1, centred on (cx, cy) (crop coordinates)."""
    k = OUT_W / CROP["w"]
    A = 1.0 / (k * z)
    Bx = CROP["x"] + cx - (OUT_W / 2) * A
    By = CROP["y"] + cy - (OUT_H / 4) * A
    return warp(planes, A, Bx, A, By, OUT_W, OUT_H // 2)


def stack_split(top, bottom, divider_px):
    y = np.vstack([top[0], bottom[0]])
    u = np.vstack([top[1], bottom[1]])
    v = np.vstack([top[2], bottom[2]])
    if divider_px:
        mid = OUT_H // 2
        a, b = mid - divider_px // 2, mid + divider_px // 2
        y[a:b, :] = 235
        u[a // 2:(b + 1) // 2, :] = 128
        v[a // 2:(b + 1) // 2, :] = 128
    return y, u, v


def pick_sharpest(window, cy, cache=None):
    """Sharpest frame (variance of the Laplacian over the half-window) inside window=(t0,t1) seconds."""
    i0, i1 = int(round(window[0] * FPS)), int(round(window[1] * FPS))
    best = None
    for idx, planes in read_source_frames(list(range(i0, i1 + 1))):
        c = planes[0][CROP["y"] + int(cy - 266):CROP["y"] + int(cy + 266), CROP["x"]:CROP["x"] + CROP["w"]]
        score = cv2.Laplacian(np.ascontiguousarray(c), cv2.CV_64F).var()
        if best is None or score > best[0]:
            best = (score, idx, tuple(p.copy() for p in planes))
    return best


def pick_split_frames():
    cfg = [s for s in TIMELINE if s.get("kind") == "split"][0]
    res = {}
    for k in ("before", "after"):
        score, idx, planes = pick_sharpest(cfg[k]["window"], cfg[k]["cy"])
        print(f"  {k}: source frame {idx} (t={idx / FPS:.3f}s) sharpness {score:.0f}")
        res[k] = dict(idx=idx, planes=planes, cy=cfg[k]["cy"])
    return res


def build_video():
    ensure_dirs()
    split = pick_split_frames()
    json.dump({k: dict(idx=v["idx"], t=v["idx"] / FPS) for k, v in split.items()},
              open(f"{WORK}/split_frames.json", "w"))
    flash = [s for s in TIMELINE if s.get("flash_frames")][0]
    vf = GRADE
    f0 = flash["start"]
    vf += (f",drawbox=x=0:y=0:w=iw:h=ih:color=white@{flash['flash_opacity']}:t=fill:"
           f"enable='between(n,{f0},{f0 + flash['flash_frames'] - 1})'")
    enc = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{OUT_W}x{OUT_H}",
           "-r", str(FPS), "-i", "-", "-vf", vf, "-c:v", "ffv1", "-level", "3", "-g", "1", "-pix_fmt", "yuv420p",
           *COLOR_TAGS, f"{WORK}/base.mkv"]
    print("$", " ".join(enc))
    pipe = subprocess.Popen(enc, stdin=subprocess.PIPE)
    n_written = 0

    def emit(planes):
        nonlocal n_written
        pipe.stdin.write(planes[0].tobytes() + planes[1].tobytes() + planes[2].tobytes())
        n_written += 1

    for seg in TIMELINE:
        print(f"[video] {seg['id']:8s} frames {seg['start']:4d}-{seg['end']:4d}  "
              f"({seg['start'] / FPS:5.2f}-{seg['end'] / FPS:5.2f}s)", flush=True)
        if seg.get("kind", "clip") == "clip":
            idxs = source_indices(seg)
            z0, z1 = seg.get("zoom", (1.0, 1.0))
            anchor = seg.get("anchor", (0.5, 0.5))
            print(f"          source {idxs[0] / FPS:.2f}s -> {idxs[-1] / FPS:.2f}s (consumes {seg['consume']:.2f}s)")
            for j, (idx, planes) in enumerate(read_source_frames(idxs)):
                z = z0 + (z1 - z0) * ease(j / max(1, seg["frames"] - 1))
                emit(full_frame_warp(planes, z, anchor))
        else:
            z0, z1 = seg.get("zoom", (1.0, 1.0))
            for j in range(seg["frames"]):
                z = z0 + (z1 - z0) * ease(j / max(1, seg["frames"] - 1))
                top = half_warp(split["before"]["planes"], split["before"]["cy"], z)
                bot = half_warp(split["after"]["planes"], split["after"]["cy"], z)
                emit(stack_split(top, bot, seg.get("divider_px", 0)))
    pipe.stdin.close()
    if pipe.wait() != 0:
        raise RuntimeError("base video encode failed")
    assert n_written == TOTAL_FRAMES, (n_written, TOTAL_FRAMES)
    print(f"[video] base.mkv written: {n_written} frames = {n_written / FPS:.3f}s")


# ============================================================================================
# 2. TEXT  (ASS + libass/fribidi)
# ============================================================================================
_font_cache = {}


def font_metrics():
    if not _font_cache:
        from fontTools.ttLib import TTFont
        f = TTFont(FONT_FILE)
        _font_cache.update(cmap=f.getBestCmap(), hmtx=f["hmtx"], upm=f["head"].unitsPerEm,
                           win=f["OS/2"].usWinAscent + f["OS/2"].usWinDescent)
    return _font_cache


def ass_fs(px):
    """libass sizes fonts so that (winAscent+winDescent) == Fontsize; convert a CSS-like em size (px)."""
    m = font_metrics()
    return round(px * m["win"] / m["upm"], 2)


def adv_width(txt, px):
    m = font_metrics()
    return sum(m["hmtx"][m["cmap"][ord(c)]][0] for c in txt) * px / m["upm"]


def parse_markup(line):
    """'a *b* c' -> [('a ', False), ('b', True), (' c', False)]"""
    out = []
    for i, part in enumerate(line.split("*")):
        if part:
            out.append((part, i % 2 == 1))
    return out


def plain(line):
    return line.replace("*", "")


RLM = "\u200f"   # RIGHT-TO-LEFT MARK


def rtl(s):
    """libass resolves the paragraph direction as LTR here, which strands trailing punctuation (? : ...) on the
    wrong side of a Hebrew line.  A zero-width RLM at the end of every Hebrew line fixes it (verified against an
    independent RTL engine in `qa`)."""
    return s + RLM if re.search("[\u0590-\u05ff]", s) else s


def ass_color_line(line):
    return rtl("".join(f"{{\\c{YELLOW if y else WHITE}}}{t}" for t, y in parse_markup(line)))


ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T,{FONT_FAMILY},60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,{OUTLINE_PX},0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def pop_tags(pop):
    if not pop:
        return ""
    a, b = POP_MS
    return rf"\fscx85\fscy85\t(0,{a},\fscx106\fscy106)\t({a},{b},\fscx100\fscy100)"


def dlg(layer, f0, f1, tags, body):
    """Dialogue line. End = floor(cs of first frame WITHOUT the event) - 1 cs so it never leaks into the next cut."""
    end_cs = (f1 * 100) // FPS - 1
    h, rem = divmod(end_cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    end = f"{h}:{m:02d}:{s:02d}.{c:02d}"
    return f"Dialogue: {layer},{ass_cs(f0)},{end},T,,0,0,0,,{tags}{body}"


def text_events(f0, f1, lines, px, yc, pop=True, outline=OUTLINE_PX, x=OUT_W // 2):
    """Soft shadow (layer 0, blurred black copy) + main text (layer 1)."""
    anim = pop_tags(pop)
    shadow = (rf"{{\an5\pos({x + 3},{yc + 9:.1f})\fs{ass_fs(px)}\bord{outline + 4}\blur14\1c&H000000&\3c&H000000&"
              rf"\1a&H58&\3a&H58&{anim}}}")
    main = rf"{{\an5\pos({x},{yc:.1f})\fs{ass_fs(px)}\bord{outline}\3c&H000000&{anim}}}"
    plain_body = r"\N".join(rtl(plain(l)) for l in lines)
    color_body = r"\N".join(ass_color_line(l) for l in lines)
    return [dlg(0, f0, f1, shadow, plain_body), dlg(1, f0, f1, main, color_body)]


def rrect_path(w, h, r):
    return (f"m {r} 0 l {w - r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h - r} b {w} {h} {w} {h} {w - r} {h} "
            f"l {r} {h} b 0 {h} 0 {h} 0 {h - r} l 0 {r} b 0 0 0 0 {r} 0")


def pill_events(f0, f1, text, px, top, color, pill_w, pill_h, ink_dy, pop=True, x=OUT_W // 2):
    """Rounded colour pill (drawing, layer 1) + label text (layer 2) + soft shadow (layer 0)."""
    anim = pop_tags(pop)
    yc = top + pill_h / 2
    shadow = rf"{{\an5\pos({x + 3},{yc + 10:.1f})\bord4\blur14\1c&H000000&\3c&H000000&\1a&H58&\3a&H58&{anim}\p1}}"
    pill = rf"{{\an5\pos({x},{yc:.1f})\bord{OUTLINE_PX}\1c{color}\3c&H000000&{anim}\p1}}"
    path = rrect_path(int(pill_w), int(pill_h), int(pill_h * 0.28)) + r"{\p0}"
    txt = (rf"{{\an5\pos({x},{yc - ink_dy:.1f})\fs{ass_fs(px)}\bord{OUTLINE_PX}\3c&H000000&"
           rf"\c{WHITE}{anim}}}{rtl(text)}")
    label_tags, label_body = txt.split("}", 1)
    return [dlg(0, f0, f1, shadow, path), dlg(1, f0, f1, pill, path), dlg(2, f0, f1, label_tags + "}", label_body)]


def render_static(ass_body, n_frames, fps=10):
    """Render an ASS script over black at `fps`; returns uint8 array (n, H, W) of luma."""
    path = f"{WORK}/measure.ass"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(ASS_HEADER + ass_body)
    cmd = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
           f"color=c=black:s={OUT_W}x{OUT_H}:r={fps}:d={n_frames / fps:.3f}",
           "-vf", f"subtitles=filename={path}:fontsdir=fonts,format=gray", "-frames:v", str(n_frames),
           "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, check=True, stdout=subprocess.PIPE).stdout
    arr = np.frombuffer(raw, np.uint8)
    return arr.reshape(n_frames, OUT_H, OUT_W)


def bbox(frame, thr=40):
    ys, xs = np.where(frame > thr)
    if len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1   # x0, y0, x1, y1


def static_line(i, lines, px, yc, outline=OUTLINE_PX):
    """measurement event i (shown 0.1*i .. 0.1*i+0.09 s), no pop, no shadow"""
    body = r"\N".join(ass_color_line(l) for l in lines)
    tags = rf"{{\an5\pos({OUT_W // 2},{yc})\fs{ass_fs(px)}\bord{outline}\3c&HFFFFFF&}}"
    return f"Dialogue: 1,0:00:{i // 10:02d}.{(i % 10) * 10:02d},0:00:{i // 10:02d}.{(i % 10) * 10 + 9:02d},T,,0,0,0,,{tags}{body}"


class Layout:
    """Measured text layout: fitted font sizes + calibrated y positions for every text of every variant."""

    def __init__(self):
        ensure_font()
        self.top_off = {}     # n_lines -> (ink_top - yc) at 100 px for the tallest glyph on the first line
        self.items = {}       # (variant,key) -> dict(px, yc, lines, bbox)
        self.labels = {}
        self.handle = None
        self._calibrate()

    def _calibrate(self):
        yc = 960
        body = "\n".join(static_line(n - 1, ["ל" * 3] * n, 100, yc) for n in (1, 2, 3))
        frames = render_static(body, 30)
        for n in (1, 2, 3):
            b = bbox(frames[n - 1])
            # first-line glyph top relative to the anchor; remove the outline so it is the glyph's own top
            self.top_off[n] = (b[1] + OUTLINE_PX) - yc
        print("[text] calibrated first-line top offsets @100px:", self.top_off)

    def fit_and_place(self):
        """Fit each text to <= MAX_LINE_W (measured through libass) and position the block's top at BLOCK_TOP_Y."""
        todo = []
        for var, over in VARIANTS.items():
            for ev in TEXT_EVENTS:
                k = ev["key"]
                if k == "T7":
                    continue
                lines = over.get(k, TEXTS[k])
                todo.append((var, k, lines, ev["px"]))
        px = {}
        for var, k, lines, base in todo:
            p = float(base)
            while max(adv_width(plain(l), p) for l in lines) + 2 * OUTLINE_PX > MAX_LINE_W:
                p -= 1
            px[(var, k)] = p
        for it in range(4):   # measure with libass and shrink until every line really fits
            frames = render_static("\n".join(static_line(i, t[2], px[(t[0], t[1])], 960) for i, t in enumerate(todo)),
                                   len(todo))
            bad = False
            for i, (var, k, lines, base) in enumerate(todo):
                b = bbox(frames[i])
                w = b[2] - b[0]
                if w > MAX_LINE_W:
                    px[(var, k)] = round(px[(var, k)] * MAX_LINE_W / w - 0.5, 1)
                    bad = True
            if not bad:
                break
        for i, (var, k, lines, base) in enumerate(todo):
            n = len(lines)
            p = px[(var, k)]
            yc = BLOCK_TOP_Y - self.top_off[n] * p / 100.0
            self.items[(var, k)] = dict(px=p, yc=yc, lines=lines, n=n, base_px=base)
        # final measurement of the actual placement
        frames = render_static("\n".join(static_line(i, t[2], px[(t[0], t[1])], self.items[(t[0], t[1])]["yc"])
                                         for i, t in enumerate(todo)), len(todo))
        for i, (var, k, lines, base) in enumerate(todo):
            self.items[(var, k)]["bbox"] = bbox(frames[i])

        # T8 handle (small, under the main block) and T7 labels (pills)
        t8 = self.items[("main", "T8")]
        gap_y = t8["bbox"][3] - OUTLINE_PX + HANDLE_GAP     # glyph bottom of the block + gap
        hl = [HANDLE]
        fr = render_static(static_line(0, hl, HANDLE_PX, 960, HANDLE_OUTLINE), 1)
        hb = bbox(fr[0])
        ink_top_off = hb[1] + HANDLE_OUTLINE - 960
        hyc = gap_y - ink_top_off
        fr = render_static(static_line(0, hl, HANDLE_PX, hyc, HANDLE_OUTLINE), 1)
        self.handle = dict(px=HANDLE_PX, yc=hyc, bbox=bbox(fr[0]))
        for k, txt in LABELS.items():
            lpx = 86
            fr = render_static(static_line(0, [txt], lpx, 960), 1)
            b = bbox(fr[0])
            ink_w, ink_h = b[2] - b[0] - 2 * OUTLINE_PX, b[3] - b[1] - 2 * OUTLINE_PX
            ink_cy = (b[1] + b[3]) / 2
            self.labels[k] = dict(text=txt, px=lpx, ink_dy=ink_cy - 960,
                                  pill_w=ink_w + 150, pill_h=ink_h + 96)
        return self


def build_ass(layout, variant):
    lines = [ASS_HEADER.rstrip("\n")]
    over = VARIANTS[variant]
    for ev in TEXT_EVENTS:
        k = ev["key"]
        f0, f1 = event_frames(ev)
        if k == "T7":
            for lab in ("before", "after"):
                L = layout.labels[lab]
                lines += pill_events(f0, f1, L["text"], L["px"], LABEL_TOP[lab], LABEL_COLORS[lab],
                                     L["pill_w"], L["pill_h"], L["ink_dy"])
            continue
        it = layout.items[(variant, k)]
        lines += text_events(f0, f1, it["lines"], it["px"], it["yc"])
        if k == "T8":
            h = layout.handle
            lines += text_events(f0, f1, [HANDLE], h["px"], h["yc"], outline=HANDLE_OUTLINE)
    path = f"{WORK}/text_{variant}.ass"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def build_cover_ass(layout):
    lines = [ASS_HEADER.rstrip("\n")]
    # headline fitted to <= 900 px on one line, centred on the split line (y=960)
    hl = COVER_HEADLINE
    p = 140.0
    while max(adv_width(plain(l), p) for l in hl) + 20 > MAX_LINE_W:
        p -= 1
    for _ in range(4):
        fr = render_static(static_line(0, hl, p, 960, 10), 1)
        b = bbox(fr[0])
        if b[2] - b[0] <= MAX_LINE_W:
            break
        p = round(p * MAX_LINE_W / (b[2] - b[0]) - 0.5, 1)
    ink_cy = (b[1] + b[3]) / 2
    yc = 960 - (ink_cy - 960)           # put the ink centre exactly on the split line
    lines += text_events(0, 90, hl, p, yc, pop=False, outline=10)
    for lab in ("before", "after"):
        L = layout.labels[lab]
        lines += pill_events(0, 90, L["text"], L["px"], COVER_LABEL_TOP[lab], LABEL_COLORS[lab],
                             L["pill_w"], L["pill_h"], L["ink_dy"], pop=False)
    path = f"{WORK}/text_cover.ass"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path, p


def build_text():
    ensure_dirs()
    layout = Layout().fit_and_place()
    report = {}
    for var in VARIANTS:
        build_ass(layout, var)
        for k in [e["key"] for e in TEXT_EVENTS if e["key"] != "T7"]:
            it = layout.items[(var, k)]
            report[f"{var}.{k}"] = dict(px=it["px"], base_px=it["base_px"], bbox=it["bbox"], lines=it["lines"])
    report["handle"] = layout.handle
    report["labels"] = layout.labels
    cover_path, cover_px = build_cover_ass(layout)
    report["cover_headline_px"] = cover_px
    json.dump(report, open(f"{WORK}/text_layout.json", "w"), ensure_ascii=False, indent=1)
    for key, v in report.items():
        if isinstance(v, dict) and "px" in v and "bbox" in v:
            b = v["bbox"]
            print(f"[text] {key:8s} px={v['px']:6.1f} (asked {v.get('base_px', '-')}) ink w={b[2] - b[0]:4d} "
                  f"y={b[1]}..{b[3]}")
    print("[text] cover headline px", cover_px)
    return layout


# ============================================================================================
# 3. AUDIO
# ============================================================================================

def audio_filtergraph():
    """Original sound per segment (atempo where sped up) -> chain -> + SFX -> trimmed to the exact length."""
    segs = TIMELINE
    n = len(segs)
    pre_src = max(0.0, segs[0]["a_src"] - PREROLL_S)
    pre_len = segs[0]["a_src"] - pre_src
    parts = [f"[0:a]aresample={SR},aformat=channel_layouts=stereo,asplit={n + 2}" +
             "".join(f"[a{i}]" for i in range(n + 2))]
    parts.append(f"[a{n}]atrim=start={pre_src:.4f}:end={segs[0]['a_src']:.4f},asetpts=PTS-STARTPTS[pre]")
    parts.append(f"[a{n + 1}]atrim=start={segs[0]['a_src']:.4f}:end={segs[0]['a_src'] + TAIL_S:.4f},asetpts=PTS-STARTPTS[tail]")
    labels = ["[pre]"]
    for i, s in enumerate(segs):
        L = s["frames"] / FPS
        tempo = s["consume"] / L
        f = f"[a{i}]atrim=start={s['a_src']:.4f}:end={s['a_src'] + s['consume'] + 0.05:.4f},asetpts=PTS-STARTPTS"
        if abs(tempo - 1.0) > 1e-3:
            f += f",atempo={tempo:.5f}"
        f += f",atrim=end={L:.5f},apad=whole_dur={L:.5f},asetpts=PTS-STARTPTS"
        prev = segs[i - 1] if i > 0 else None
        nxt = segs[i + 1] if i + 1 < n else None
        if prev is not None and abs(prev["a_end"] - s["a_src"]) > 0.15:       # discontinuous join -> micro fade
            f += f",afade=t=in:d={FADE_S}"
        if nxt is not None and abs(s["a_end"] - nxt["a_src"]) > 0.15:
            f += f",afade=t=out:st={L - FADE_S:.5f}:d={FADE_S}"
        parts.append(f + f"[s{i}]")
        labels.append(f"[s{i}]")
    labels.append("[tail]")
    parts.append("".join(labels) + f"concat=n={n + 2}:v=0:a=1,{AUDIO_CHAIN}[voice]")

    # --- SFX, synthesized with ffmpeg lavfi sources -------------------------------------------------
    pop = ("aevalsrc='sin(2*PI*(380*t+700*0.018*(1-exp(-t/0.018))))*exp(-t/0.045)*(1-exp(-t/0.002))'"
           f":d=0.2:s={SR}:c=mono")
    ding = ("aevalsrc='(sin(2*PI*1318.5*t)*exp(-t/0.55)+0.45*sin(2*PI*2637*t)*exp(-t/0.30)"
            "+0.25*sin(2*PI*3640*t)*exp(-t/0.18)+0.12*sin(2*PI*5400*t)*exp(-t/0.10))*(1-exp(-t/0.002))*0.55'"
            f":d=1.4:s={SR}:c=mono")
    def whoosh_graph(i):
        s = f"anoisesrc=d=0.85:c=white:r={SR}:a=0.9:seed=11,asplit=3[wn0_{i}][wn1_{i}][wn2_{i}];"
        s += (f"[wn0_{i}]lowpass=f=900,asetnsamples=n=128:p=0,volume='exp(-pow((t-0.30)/0.17,2))':eval=frame[wl_{i}];"
              f"[wn1_{i}]highpass=f=1000,lowpass=f=4200,asetnsamples=n=128:p=0,"
              f"volume='exp(-pow((t-0.43)/0.14,2))':eval=frame[wm_{i}];"
              f"[wn2_{i}]highpass=f=4500,asetnsamples=n=128:p=0,volume='0.7*exp(-pow((t-0.52)/0.12,2))':eval=frame[wh_{i}];"
              f"[wl_{i}][wm_{i}][wh_{i}]amix=inputs=3:normalize=0,afade=t=in:d=0.25,afade=t=out:st=0.5:d=0.35,"
              "aformat=channel_layouts=mono")
        return s

    sfx_labels = []
    for i, e in enumerate(SFX):
        b0, b1 = beat_range(e["beat"])
        t = b0 / FPS + e["at"] + pre_len
        delay_ms = max(0, int(round(t * 1000)))
        if e["kind"] == "whoosh":
            parts.append(whoosh_graph(i) + f"[raw_{i}]")
        else:
            parts.append({"pop": pop, "ding": ding}[e["kind"]] + f"[raw_{i}]")
        parts.append(f"[raw_{i}]aformat=channel_layouts=stereo,volume={e['gain']},adelay={delay_ms}|{delay_ms}[x{i}]")
        sfx_labels.append(f"[x{i}]")
    total = pre_len + DURATION + TAIL_S
    mix = (f"[voice]{''.join(sfx_labels)}amix=inputs={len(sfx_labels) + 1}:normalize=0:duration=first,"
           f"atrim=start={pre_len:.4f}:end={total:.4f},asetpts=PTS-STARTPTS,apad=whole_dur={DURATION + TAIL_S:.5f},"
           f"atrim=end={DURATION + TAIL_S:.5f},{PEAK_LIMITER}[mix]")
    parts.append(mix)
    return ";".join(parts)


def build_audio():
    ensure_dirs()
    graph = audio_filtergraph()
    open(f"{WORK}/audio_graph.txt", "w").write(graph.replace(";", ";\n"))
    pre = f"{WORK}/audio_premix.wav"
    sh(["ffmpeg", "-y", "-v", "error", "-i", INPUT, "-filter_complex", graph, "-map", "[mix]",
        "-c:a", "pcm_f32le", "-ar", str(SR), pre])
    ln = LOUDNORM
    p1 = subprocess.run(["ffmpeg", "-v", "info", "-i", pre, "-af",
                         f"loudnorm=I={ln['I']}:TP={ln['TP']}:LRA={ln['LRA']}:print_format=json",
                         "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1.stderr, re.S)
    meas = json.loads(m.group(0))
    print("[audio] pass-1 measurement:", {k: meas[k] for k in ("input_i", "input_tp", "input_lra", "input_thresh")})
    af = (f"loudnorm=I={ln['I']}:TP={ln['TP']}:LRA={ln['LRA']}:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}"
          f":measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}"
          ":linear=true:print_format=summary")
    p2 = subprocess.run(["ffmpeg", "-y", "-v", "info", "-i", pre, "-af", af + f",aresample={SR}",
                         "-c:a", "pcm_f32le", f"{WORK}/audio_final.wav"], capture_output=True, text=True)
    print("\n".join(l for l in p2.stderr.splitlines() if any(w in l for w in
                                                              ("Input Integrated", "Output Integrated", "Output True",
                                                               "Normalization Type", "Target Offset"))))


# ============================================================================================
# 4. FINAL EXPORT
# ============================================================================================

def encode_variant(variant):
    out = f"{OUTD}/reel_{variant}.mp4"
    vf = f"subtitles=filename={WORK}/text_{variant}.ass:fontsdir=fonts"
    sh(["ffmpeg", "-y", "-v", "error", "-i", f"{WORK}/base.mkv", "-i", f"{WORK}/audio_final.wav",
        "-vf", vf, "-map", "0:v:0", "-map", "1:a:0", *X264, *COLOR_TAGS, "-r", str(FPS), "-fps_mode", "cfr",
        *AAC, "-movflags", "+faststart", out])
    return out


def build_final():
    ensure_dirs()
    for v in VARIANTS:
        encode_variant(v)


# ============================================================================================
# 5. COVER + STORYBOARD
# ============================================================================================

def yuv_to_png(args_in, vf, out_png):
    sh(["ffmpeg", "-y", "-v", "error", *args_in, "-vf", vf, "-frames:v", "1", out_png])


def build_cover():
    ensure_dirs()
    layout = Layout().fit_and_place()
    build_cover_ass(layout)
    split = pick_split_frames()
    cfg = [s for s in TIMELINE if s.get("kind") == "split"][0]
    top = half_warp(split["before"]["planes"], split["before"]["cy"], 1.0)
    bot = half_warp(split["after"]["planes"], split["after"]["cy"], 1.0)
    y, u, v = stack_split(top, bot, cfg.get("divider_px", 0))
    raw = f"{WORK}/cover_raw.yuv"
    open(raw, "wb").write(y.tobytes() + u.tobytes() + v.tobytes())
    vf = (f"{GRADE},subtitles=filename={WORK}/text_cover.ass:fontsdir=fonts,"
          "scale=in_range=tv:in_color_matrix=bt709:out_range=pc:out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int,"
          "format=rgb24")
    png = f"{WORK}/cover.png"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{OUT_W}x{OUT_H}", "-i", raw,
        "-vf", vf, "-frames:v", "1", png])
    from PIL import Image
    Image.open(png).convert("RGB").save(f"{OUTD}/cover.jpg", quality=95, subsampling=0, optimize=True)
    print("[cover] out/cover.jpg", Image.open(f"{OUTD}/cover.jpg").size)


def storyboard_times():
    def mid(beat, a=0.5):
        b0, b1 = beat_range(beat)
        return (b0 + (b1 - b0) * a) / FPS
    rb0, _ = beat_range("rinse")
    d0, d1 = beat_range("dirty")
    return [
        ("1 הוק", 1.0),
        ("2 פס נקי מול מלוכלך", mid("stripe")),
        ("3 המים הכי חומים (1x)", (d0 + 40) / FPS),
        ("4 מונטאז' x3 + טקסט", (d1 - 20) / FPS),
        ("5 התפנית: פלאש", (rb0 + 1) / FPS),
        ("6 שטיפה", (rb0 + 45) / FPS),
        ("7 עד שהמים נקיים", (rb0 + 100) / FPS),
        ("8 אחרת הלכלוך חוזר", (rb0 + 170) / FPS),
        ("9 לפני / אחרי", mid("ba", 0.85)),
        ("10 CTA + לופ", mid("cta")),
    ]


def build_storyboard():
    from PIL import Image, ImageDraw, ImageFont
    ensure_dirs()
    tiles = []
    for i, (label, t) in enumerate(storyboard_times()):
        png = f"{WORK}/sb_{i}.png"
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", f"{OUTD}/reel_main.mp4", "-frames:v", "1",
            "-vf", "scale=432:768:flags=lanczos:in_range=tv:in_color_matrix=bt709,format=rgb24", png])
        tiles.append((label, t, Image.open(png).convert("RGB")))
    cols, rows, tw, th, pad, cap = 5, 2, 432, 768, 12, 70
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + cap + pad) + pad), (18, 18, 22))
    font = ImageFont.truetype(FONT_FILE, 34, layout_engine=ImageFont.Layout.RAQM)
    d = ImageDraw.Draw(sheet)
    for i, (label, t, im) in enumerate(tiles):
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + cap + pad)
        sheet.paste(im, (x, y))
        num, _, rest = label.partition(" ")
        d.text((x + tw - 6, y + th + 6), rest, font=font, fill=(255, 214, 10), anchor="ra", direction="rtl", language="he")
        d.text((x + 6, y + th + 6), f"{num}  {t:4.1f}s", font=font, fill=(255, 255, 255), anchor="la")
    sheet.save(f"{OUTD}/storyboard.jpg", quality=92)
    print("[storyboard] out/storyboard.jpg", sheet.size)



# ============================================================================================
# 6. QA  (python3 build.py qa)
# ============================================================================================
_RESULTS = []


def check(name, ok, detail=""):
    _RESULTS.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  -> {detail}" if detail else ""), flush=True)


def decode(path, vf, w, h, pix="rgb24", ss=None, frames=None):
    ch = {"rgb24": 3, "gray": 1}[pix]
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(ss)] if ss is not None else []) + ["-i", path, "-an", "-vf", vf + f",format={pix}"]
    if frames:
        cmd += ["-frames:v", str(frames)]
    cmd += ["-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, check=True, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, ch) if ch > 1 else np.frombuffer(raw, np.uint8).reshape(-1, h, w)


RGB_CONV = "scale=in_range=tv:in_color_matrix=bt709:out_range=pc"


def qa_title():
    title_bottom = 202   # measured: static white title occupies source y=65..202
    check("crop starts below the burned-in title", CROP["y"] > title_bottom, f"crop y={CROP['y']} > title bottom y={title_bottom}")
    fl = [s for s in TIMELINE if s.get("flash_frames")][0]
    frames = decode(f"{WORK}/base.mkv", f"fps=2,crop={OUT_W}:56:0:0,{RGB_CONV}", OUT_W, 56)
    worst = (0, 0)
    for i, f in enumerate(frames):
        t = i / 2
        if fl["start"] / FPS <= t < (fl["start"] + fl["flash_frames"]) / FPS + 0.2:
            continue
        white = (f.min(axis=2) >= 245).mean(axis=1)      # per-row fraction of near-white pixels
        if white.max() > worst[0]:
            worst = (float(white.max()), t)
    check("no white title residue in the top rows of any sampled frame (every 0.5s, all segments)",
          worst[0] < 0.5, f"max row-white fraction {worst[0]:.2f} at t={worst[1]:.1f}s (a title bar would be >0.9)")
    # visual strip for the human check
    strips = decode(f"{WORK}/base.mkv", f"fps=1.2,crop={OUT_W}:260:0:0,scale=360:87,{RGB_CONV}", 360, 87)
    cols = 6
    rows = [np.hstack(list(strips[i:i + cols]) + [np.zeros_like(strips[0])] * (cols - len(strips[i:i + cols])))
            for i in range(0, len(strips), cols)]
    cv2.imwrite(f"{WORK}/qa/top_strips.png", cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))


def qa_first_frame():
    fin = decode(f"{OUTD}/reel_main.mp4", "null", OUT_W, OUT_H, "gray", frames=1) if False else \
        decode(f"{OUTD}/reel_main.mp4", "scale=1080:1920", OUT_W, OUT_H, "gray", frames=1)
    base = decode(f"{WORK}/base.mkv", "scale=1080:1920", OUT_W, OUT_H, "gray", frames=1)
    mean = float(fin[0].mean())
    d = np.abs(fin[0].astype(int) - base[0].astype(int))
    text_px = int((d[300:620, 100:980] > 60).sum())
    check("first frame is not black", mean > 40, f"mean luma {mean:.0f}/255")
    check("T1 text is already on the first frame", text_px > 8000, f"{text_px} text pixels differ from the text-free base")


def qa_hebrew(layout):
    """Render the REAL multi-line blocks with libass and compare every line, pixel profile for pixel profile,
    with an independent bidi/shaping engine (Pillow+raqm).  Reversed order / stranded punctuation => FAIL."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        cover_px = json.load(open(f"{WORK}/text_layout.json"))["cover_headline_px"]
    except Exception:
        cover_px = 118.0
    tasks, seen = [], set()
    for var in VARIANTS:
        for k in [e["key"] for e in TEXT_EVENTS if e["key"] != "T7"]:
            it = layout.items[(var, k)]
            key = (tuple(it["lines"]), it["px"])
            if key not in seen:
                seen.add(key)
                tasks.append((it["lines"], it["px"]))
    tasks += [([v], 86) for v in LABELS.values()] + [(list(COVER_HEADLINE), cover_px)]
    frames = render_static("\n".join(static_line(i, ln, p, 960, 0) for i, (ln, p) in enumerate(tasks)), len(tasks))
    bad, n_lines = [], 0
    worst_corr, worst_ratio = 1.0, 1.0
    for i, (lines, px) in enumerate(tasks):
        f = frames[i]
        rows = np.where((f > 90).any(axis=1))[0]
        bands, start = [], rows[0]
        for a_, b_ in zip(rows[:-1], rows[1:]):
            if b_ - a_ > 3:
                bands.append((start, a_ + 1))
                start = b_
        bands.append((start, rows[-1] + 1))
        if len(bands) != len(lines):
            bad.append((lines, f"expected {len(lines)} lines, found {len(bands)}"))
            continue
        for ln, (y0, y1) in zip(lines, bands):
            t = plain(ln)
            n_lines += 1
            sub = f[y0:y1]
            cols = np.where((sub > 90).any(axis=0))[0]
            ass_img = sub[:, cols[0]:cols[-1] + 1].astype(np.float32) / 255
            font = ImageFont.truetype(FONT_FILE, int(round(px)), layout_engine=ImageFont.Layout.RAQM)
            img = Image.new("L", (1400, 400), 0)
            direction = "ltr" if t.startswith("@") else "rtl"
            ImageDraw.Draw(img).text((60, 100), t, font=font, fill=255, direction=direction,
                                     language="he" if direction == "rtl" else "en")
            pb = bbox(np.array(img), 90)
            pil_img = np.array(img)[pb[1]:pb[3], pb[0]:pb[2]].astype(np.float32) / 255
            ratio = ass_img.shape[1] / pil_img.shape[1]
            pil_r = cv2.resize(pil_img, (ass_img.shape[1], ass_img.shape[0]), interpolation=cv2.INTER_AREA)
            a_prof, b_prof = ass_img.mean(axis=0), pil_r.mean(axis=0)
            corr = float(np.corrcoef(a_prof, b_prof)[0, 1])
            flip = float(np.corrcoef(a_prof, b_prof[::-1])[0, 1])
            worst_corr, worst_ratio = min(worst_corr, corr), min(worst_ratio, ratio)
            if corr < 0.93 or flip > corr or abs(ratio - 1) > 0.04:
                bad.append((t, round(corr, 3), round(flip, 3), round(ratio, 3)))
    check("Hebrew RTL order + punctuation side identical to an independent RTL engine (every line of every block, all variants)",
          not bad, f"{n_lines} lines in {len(tasks)} blocks; worst profile correlation {worst_corr:.3f}; min width ratio {worst_ratio:.3f}"
          + (f"; BAD: {bad}" if bad else ""))


def qa_layout(layout):
    """Render the real ASS (with shadows) at each event's pop peak and check every pixel against the UI zones."""
    worst = dict(top=9999, bottom=0, right_hit=0, max_line=0)
    for var in VARIANTS:
        src = open(f"{WORK}/text_{var}.ass", encoding="utf-8").read().replace("&H000000&", "&HFFFFFF&")
        head, events = src.split("[Events]", 1)
        evs = [l for l in events.splitlines() if l.startswith("Dialogue")]
        times = sorted({int(round(e["t0"] * 0)) for e in TEXT_EVENTS})  # (placeholder, real times below)
        for ev in TEXT_EVENTS:
            f0, f1 = event_frames(ev)
            t = (f0 + 4) / FPS          # pop peak (~120 ms)
            body = "[Events]" + events
            path = f"{WORK}/qa/zone_{var}_{ev['key']}.ass"
            open(path, "w", encoding="utf-8").write(head + body)
            cmd = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={OUT_W}x{OUT_H}:r={FPS}:d={DURATION}",
                   "-ss", f"{t:.4f}", "-vf", f"subtitles=filename={path}:fontsdir=fonts,format=gray", "-frames:v", "1",
                   "-f", "rawvideo", "-"]
            fr = np.frombuffer(subprocess.run(cmd, check=True, stdout=subprocess.PIPE).stdout, np.uint8).reshape(OUT_H, OUT_W)
            ys, xs = np.where(fr > 14)
            if len(ys) == 0:
                continue
            worst["top"] = min(worst["top"], int(ys.min()))
            worst["bottom"] = max(worst["bottom"], int(ys.max()) + 1)
            y0, y1 = FORBIDDEN["right_y"]
            zone = fr[y0:y1, OUT_W - FORBIDDEN["right"]:]
            worst["right_hit"] = max(worst["right_hit"], int((zone > 14).sum()))
    check("nothing in the top 250px", worst["top"] >= FORBIDDEN["top"], f"highest text pixel y={worst['top']}")
    check("nothing in the bottom 400px", worst["bottom"] <= OUT_H - FORBIDDEN["bottom"], f"lowest text pixel y={worst['bottom']} (limit {OUT_H - FORBIDDEN['bottom']})")
    check("nothing in the right 140px between y=1000 and 1700", worst["right_hit"] == 0, f"{worst['right_hit']} pixels")
    wmax = max(it["bbox"][2] - it["bbox"][0] for it in layout.items.values())
    check("every text line <= 900px (incl. outline)", wmax <= MAX_LINE_W, f"widest block {wmax}px")


def qa_loop():
    g = decode(f"{WORK}/base.mkv", "scale=270:480", 270, 480, "gray").astype(np.float32)
    d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))              # consecutive-frame MAE
    seam = float(np.abs(g[-1] - g[0]).mean())
    ref = [d[i] for s in TIMELINE if s["id"] in ("hook", "cta") for i in range(s["start"], s["end"] - 1)]
    p95 = float(np.percentile(ref, 95))
    check("picture: last frame -> first frame is as smooth as any normal frame step",
          seam <= p95, f"seam MAE {seam:.2f} vs hook/cta frame-to-frame median {np.median(ref):.2f}, p95 {p95:.2f}")
    # source continuity (the real reason it loops): the CTA ends on the source frame right before the hook's first frame
    cta, hook = TIMELINE[-1], TIMELINE[0]
    last = source_indices(cta)[-1]
    first = source_indices(hook)[0]
    check("source frame after the CTA's last frame is the hook's first frame", last + 1 == first, f"{last} -> {first}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f"{OUTD}/reel_main.mp4", "-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                         check=True, stdout=subprocess.PIPE).stdout
    a = np.frombuffer(raw, np.float32)
    n = int(round(DURATION * 48000))
    body = a[:n]
    w = int(0.02 * 48000)
    rms = lambda x: 20 * math.log10(float(np.sqrt((x ** 2).mean())) + 1e-9)
    seam_a = abs(float(body[0]) - float(body[-1]))
    step = float(np.std(np.diff(body[-48000:])))
    check("audio: no click at the loop point (sample jump within normal sample-to-sample motion)",
          seam_a <= 6 * step, f"jump {seam_a:.4f} vs typical step std {step:.4f}")
    e_last, e_before = rms(body[-w:]), rms(body[-6 * w:-w])
    check("audio: no end-of-file dip (codec) - last 20 ms vs the 100 ms before it",
          abs(e_last - e_before) < 4, f"{e_last:.1f} vs {e_before:.1f} dBFS ({e_last - e_before:+.1f} dB)")
    e_start = rms(body[:w])
    check("audio: level just before the end ~ level just after the start (T1's soft pop included)",
          abs(e_last - e_start) < 6, f"{e_last:.1f} -> {e_start:.1f} dBFS ({e_start - e_last:+.1f} dB)")


def qa_encode():
    for v in VARIANTS:
        path = f"{OUTD}/reel_{v}.mp4"
        j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                                      check=True, capture_output=True, text=True).stdout)
        vs = [s for s in j["streams"] if s["codec_type"] == "video"][0]
        au = [s for s in j["streams"] if s["codec_type"] == "audio"][0]
        dur = float(j["format"]["duration"])
        ok = (vs["codec_name"] == "h264" and vs["profile"] == "High" and vs["width"] == 1080 and vs["height"] == 1920
              and vs["pix_fmt"] == "yuv420p" and vs["r_frame_rate"] == "30/1" and vs["avg_frame_rate"] == "30/1"
              and au["codec_name"] == "aac" and au["sample_rate"] == "48000" and au["channels"] == 2)
        check(f"{path}: ffprobe matches the spec", ok,
              f"h264 {vs['profile']} {vs['width']}x{vs['height']} {vs['pix_fmt']} {vs['r_frame_rate']}fps, "
              f"aac {au['sample_rate']}Hz {au['channels']}ch {int(au['bit_rate']) // 1000}k, v {int(vs['bit_rate']) / 1e6:.1f}M")
        check(f"{path}: length 20-22 s", 20 <= dur <= 22,
              f"container {dur:.3f}s (video {float(vs['duration']):.3f}s, audio {float(au['duration']):.3f}s)")
        head = open(path, "rb").read(2_000_000)
        check(f"{path}: +faststart (moov before mdat)", 0 <= head.find(b"moov") < head.find(b"mdat"))
        sei = re.search(rb"options: [^\x00]*", head)
        opts = sei.group(0).decode(errors="ignore") if sei else ""
        # `-preset slow` signature in this x264 build (ref is capped at 4 by level 4.2) + CRF 18 + maxrate 12M
        need = ("crf=18.0", "vbv_maxrate=12000", "vbv_bufsize=24000", "subme=8", "trellis=2", "rc_lookahead=50")
        check(f"{path}: x264 CRF 18, preset slow, maxrate 12M (read back from the stream)",
              all(k in opts for k in need), "found: " + " ".join(k for k in need if k in opts))
        r = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
        summ = r[r.rfind("Summary:"):]
        integ = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1))
        tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1))
        check(f"{path}: loudness {LOUDNORM['I']} LUFS (+-1) and true peak <= -1 dBTP", abs(integ - LOUDNORM["I"]) <= 1 and tp <= -1.0 + 0.05,
              f"I={integ} LUFS, true peak={tp} dBTP")


def qa_variants():
    ref = decode(f"{OUTD}/reel_main.mp4", "scale=270:480", 270, 480, "gray").astype(np.float32)
    t2_end = beat_range("stripe")[1]
    for v in ("A", "B"):
        o = decode(f"{OUTD}/reel_{v}.mp4", "scale=270:480", 270, 480, "gray").astype(np.float32)
        n = min(len(ref), len(o))
        mse = ((ref[:n] - o[:n]) ** 2).mean(axis=(1, 2))
        psnr = 10 * np.log10(255 ** 2 / np.maximum(mse, 1e-6))
        check(f"variant {v}: identical to main after T2 (only T1/T2 differ)", psnr[t2_end:].min() > 38,
              f"min PSNR frames {t2_end}.. = {psnr[t2_end:].min():.1f} dB ; hook window min {psnr[:t2_end].min():.1f} dB (text differs)")
        check(f"variant {v}: same frame count as main", len(o) == len(ref), f"{len(o)} vs {len(ref)}")


def build_qa():
    ensure_dirs()
    os.makedirs(f"{WORK}/qa", exist_ok=True)
    layout = Layout().fit_and_place()
    for v in VARIANTS:
        build_ass(layout, v)
    qa_title()
    qa_first_frame()
    qa_hebrew(layout)
    qa_layout(layout)
    qa_loop()
    qa_encode()
    qa_variants()
    fails = [r for r in _RESULTS if not r[1]]
    print(f"\nQA: {len(_RESULTS) - len(fails)}/{len(_RESULTS)} checks passed" + ("" if not fails else "  FAILED: " + "; ".join(r[0] for r in fails)))
    with open(f"{WORK}/qa/report.txt", "w", encoding="utf-8") as fh:
        for n, ok, d in _RESULTS:
            fh.write(("PASS  " if ok else "FAIL  ") + n + (f"  -> {d}" if d else "") + "\n")


# ============================================================================================
# main
# ============================================================================================
if __name__ == "__main__":
    steps = sys.argv[1:] or ["all"]
    if steps == ["all"]:
        steps = ["text", "video", "audio", "final", "cover", "storyboard", "qa"]
    for s in steps:
        {"text": build_text, "video": build_video, "audio": build_audio, "final": build_final,
         "cover": build_cover, "storyboard": build_storyboard, "qa": build_qa}[s]()
    print(f"done. {TOTAL_FRAMES} frames = {DURATION:.3f}s")
