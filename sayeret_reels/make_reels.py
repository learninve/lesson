#!/usr/bin/env python3
"""Sayeret Nikayon – car-seat vacuum ASMR  ->  3 x 21 s Reels/TikTok edits (1080x1920).

Stage A (Python + ffmpeg pipes): cut / speed-ramp / zoom / lanczos upscale -> lossless base video
Stage B (ffmpeg): colour (contrast +10 %, saturation +15 %, light sharpen) + Hebrew PNG overlays,
                  audio cut/ramped from the original, loudnorm -14 LUFS, H.264 high CRF 18, AAC 192k.

usage:  python3 make_reels.py SOURCE.mp4 OUTDIR WORKDIR
"""
import json
import math
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

import text_layers as TL

SRC, OUT, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
os.makedirs(WORK, exist_ok=True)
SW, SH, OW, OH, FPS = 720, 1280, 1080, 1920, 30

# --------------------------------------------------------------------------- edit decision list
# (label, src_start, src_end [cut = end of the pull], target speed, zoom)
# Source analysis: front seat 0-36 s, rear seat from 37 s. Darkest/most saturated water: 6.5-7.1 s.
HOOK = ("hook", 6.5, 8.5, 1.0)                     # 2.0 s, darkest brown frame first, fast zoom-in
MID = [                                             # 2-14 s, 7 pulls, x1.5-x2, alternating zoom
    ("M1", 8.4, 10.5, 1.5, 1.00),
    ("M2", 10.6, 13.0, 1.5, 1.15),
    ("M3", 13.6, 16.3, 1.7, 1.00),
    ("M4", 20.0, 23.5, 1.8, 1.15),
    ("M5", 23.75, 27.5, 1.8, 1.00),
    ("M6", 28.0, 30.75, 1.6, 1.15),
    ("M7", 32.5, 35.25, 1.6, 1.00),
]
REAR = [                                            # 14-18 s, switch to the rear seat
    ("T", 37.0, 38.5, 2.0, 1.00),
    ("R1", 42.4, 43.55, 1.5, 1.15),
    ("R2", 48.9, 53.5, 1.8, 1.00),
]
# 18-21 s: one pull where the water goes brown -> clear (clearest at ~41.25 s). The last 0.65 s of the
# source pull is slowed to x0.5 so the clear water is on screen *before* the loop dissolve starts.
RESULT = [("result_a", 38.9, 40.9, 48, 1.00), ("result_b", 40.9, 41.6, 42, 1.00)]
MID_FRAMES, REAR_FRAMES, HOOK_FRAMES, RESULT_FRAMES = 360, 120, 60, 90
assert sum(r[3] for r in RESULT) == RESULT_FRAMES
ZOOM_END, ZOOM_FRAMES = 1.15, 36
DISSOLVE = 12                                       # last 0.4 s melts into the very first frame
AUDIO_FADE = 0.006


def sized(clips, total):
    """frames per clip from the target speed; the last clip absorbs rounding so the block is exact."""
    n = [round((c[2] - c[1]) * FPS / c[3]) for c in clips]
    n[-1] += total - sum(n)
    return n


def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        raise SystemExit("command failed: " + " ".join(map(str, cmd))[:300])
    return r


def decode(s0, n):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{s0:.4f}", "-i", SRC, "-frames:v", str(n),
         "-vf", "format=rgb24", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    arr = np.frombuffer(raw, np.uint8).reshape(-1, SH, SW, 3)
    return arr


def nozzle_anchor(frames):
    """median centre of the orange/brown water (the nozzle) -> zoom anchor (fractions)."""
    xs, ys = [], []
    for f in frames[:: max(1, len(frames) // 12)]:
        s = f[::4, ::4].astype(int)
        r, g, b = s[..., 0], s[..., 1], s[..., 2]
        m = (r > 110) & (r - b > 70) & (g - b > 30) & (r >= g)
        if m.sum() > 150:
            yy, xx = np.nonzero(m)
            xs.append(xx.mean() / m.shape[1])
            ys.append(yy.mean() / m.shape[0])
    return (float(np.median(xs)), float(np.median(ys))) if xs else (0.5, 0.5)


def crop_scale(frame, z, anchor):
    w, h = SW / z, SH / z
    x0 = min(max(anchor[0] * SW - w / 2, 0), SW - w)
    y0 = min(max(anchor[1] * SH - h / 2, 0), SH - h)
    im = Image.fromarray(frame)
    return np.asarray(im.resize((OW, OH), Image.LANCZOS, box=(x0, y0, x0 + w, y0 + h)))


def ease_out(t):
    return 1 - (1 - t) ** 3


def smooth(t):
    return t * t * (3 - 2 * t)


def build_base(path):
    plan = []   # (label, s0, s1, n_out, zoom)
    hn = HOOK_FRAMES
    plan.append((HOOK[0], HOOK[1], HOOK[2], hn, None))
    for c, n in zip(MID, sized(MID, MID_FRAMES)):
        plan.append((c[0], c[1], c[2], n, c[4]))
    for c, n in zip(REAR, sized(REAR, REAR_FRAMES)):
        plan.append((c[0], c[1], c[2], n, c[4]))
    for r in RESULT:
        plan.append((r[0], r[1], r[2], r[3], r[4]))

    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
         "-r", str(FPS), "-i", "-", "-c:v", "ffv1", "-pix_fmt", "gbrp", path], stdin=subprocess.PIPE)
    info, first_frame, timeline = [], None, 0
    for label, s0, s1, n_out, zoom in plan:
        speed = (s1 - s0) * FPS / n_out
        frames = decode(s0, int(math.ceil((s1 - s0) * FPS)) + 3)
        anchor = nozzle_anchor(frames)
        out_clip = []
        for k in range(n_out):
            fr = frames[min(int(round(k * speed)), len(frames) - 1)]
            if label == "hook":
                z = 1 + (ZOOM_END - 1) * ease_out(min(1.0, k / ZOOM_FRAMES))
            else:
                z = zoom
            img = crop_scale(fr, z, anchor)
            if label == "T" and k < 6:                       # white flash into the rear seat
                a = 0.6 * (1 - k / 6)
                img = (img * (1 - a) + 255 * a).astype(np.uint8)
            out_clip.append(img)
        if label == "hook":
            first_frame = out_clip[0].copy()
        if label == RESULT[-1][0]:                          # loop: dissolve into frame 0
            for i in range(DISSOLVE):
                a = smooth((i + 1) / DISSOLVE)
                idx = n_out - DISSOLVE + i
                out_clip[idx] = (out_clip[idx] * (1 - a) + first_frame * a).round().astype(np.uint8)
        for img in out_clip:
            enc.stdin.write(img.tobytes())
        info.append(dict(label=label, start_s=round(timeline / FPS, 3), out_s=round(n_out / FPS, 3),
                         src=f"{s0}-{s1}", speed=round(speed, 3), zoom=zoom if zoom else f"1.00->{ZOOM_END}",
                         anchor=[round(anchor[0], 2), round(anchor[1], 2)]))
        timeline += n_out
        print(f"  {label:<7} t={timeline / FPS - n_out / FPS:5.2f}s  src {s0:>5}-{s1:<5} x{speed:.2f}  {n_out} fr  anchor {anchor[0]:.2f},{anchor[1]:.2f}")
    enc.stdin.close()
    enc.wait()
    assert timeline == HOOK_FRAMES + MID_FRAMES + REAR_FRAMES + RESULT_FRAMES, timeline
    json.dump(info, open(os.path.join(WORK, "edl.json"), "w"), indent=1)
    return plan


def build_audio(plan, path):
    """cut the same source ranges, time-compress with atempo (pitch kept), join, -14 LUFS."""
    parts, labels = [], []
    for i, (label, s0, s1, n_out, _) in enumerate(plan):
        dur = n_out / FPS
        speed = (s1 - s0) / dur
        parts.append(
            f"[0:a]atrim={s0}:{s1},asetpts=PTS-STARTPTS,atempo={speed:.5f},"
            f"afade=t=in:d={AUDIO_FADE},afade=t=out:st={dur - AUDIO_FADE:.4f}:d={AUDIO_FADE}[a{i}]")
        labels.append(f"[a{i}]")
    total = sum(p[3] for p in plan) / FPS
    fc = ";".join(parts) + f";{''.join(labels)}concat=n={len(labels)}:v=0:a=1,aresample=48000," \
        f"aformat=channel_layouts=stereo,afade=t=in:d=0.02,afade=t=out:st={total - 0.12:.3f}:d=0.12[aout]"
    raw = os.path.join(WORK, "audio_raw.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-filter_complex", fc, "-map", "[aout]", raw])
    # two-pass loudnorm
    p1 = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw, "-af",
                         "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1, re.S).group(0))
    print("  loudnorm pass1:", {k: m[k] for k in ("input_i", "input_tp", "input_lra")})
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", af, "-ar", "48000", path])


def render_variant(v, base, wav, layers):
    out = os.path.join(OUT, f"reel_{v}.mp4")
    d = 0.12
    # (png, start, end, fade_in?, fade_out?)  — windows from the brief
    wins = [
        (f"hook_{v}", 0.0, 2.0, False, True),
        ("c1", 3.0, 8.0, True, True),
        ("c2", 8.0, 14.0, True, True),
        ("c3", 14.0, 18.0, True, True),
        ("cta", 18.0, 20.6, True, True),
        (f"hook_{v}", 20.6, 21.0, True, False),          # loop: last frame == first frame (+ hook)
    ]
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", base, "-i", wav]
    for name, *_ in wins:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", "21", "-i", layers[name]]
    cmd += ["-loop", "1", "-framerate", str(FPS), "-t", "21", "-i", layers["wm"]]
    fc = ("[0:v]scale=out_color_matrix=bt709:out_range=tv:flags=lanczos+accurate_rnd,format=yuv444p,"
          "eq=contrast=1.10:saturation=1.15,unsharp=5:5:0.5:5:5:0.0[v0]")
    prev = "v0"
    for i, (name, a, b, fi, fo) in enumerate(wins):
        ch = f"[{i + 2}:v]format=rgba"
        if fi:
            ch += f",fade=t=in:st={a}:d={d}:alpha=1"
        if fo:
            ch += f",fade=t=out:st={b - d}:d={d}:alpha=1"
        fc += f";{ch}[o{i}];[{prev}][o{i}]overlay=0:0:format=yuv444:eof_action=pass[v{i + 1}]"
        prev = f"v{i + 1}"
    k = len(wins) + 2
    fc += f";[{k}:v]format=rgba[wm];[{prev}][wm]overlay=0:0:format=yuv444:eof_action=pass,format=yuv420p[vout]"
    cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", "1:a",
            "-t", "21", "-r", str(FPS), "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-color_range", "tv", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out]
    run(cmd)
    return out


def main():
    print("[1/4] text layers")
    ldir = os.path.join(WORK, "layers")
    TL.build_all(ldir)
    layers = {n[:-4]: os.path.join(ldir, n) for n in os.listdir(ldir) if n.endswith(".png")}
    print("[2/4] base video")
    base = os.path.join(WORK, "base.mkv")
    plan = build_base(base)
    print("[3/4] audio")
    wav = os.path.join(WORK, "audio_ln.wav")
    build_audio(plan, wav)
    print("[4/4] final encodes")
    with ThreadPoolExecutor(3) as ex:
        for p in ex.map(lambda v: render_variant(v, base, wav, layers), "ABC"):
            print("  ->", p)


if __name__ == "__main__":
    main()
