#!/usr/bin/env python3
"""Car-seat extraction clip -> organic Reels/TikTok edit for "סיירת ניקיון".

    python3 build_reels.py --input car_seat_31s.mp4 --output ../output_reels.mp4

Pipeline (FFmpeg + Chromium for the Hebrew text):
  1. render_overlays.cjs  -> transparent PNG layers (banner, 4 Hebrew captions, end card)
  2. audio: replace the English voice-over window with clean suction ambience, speed-match every
     segment (atempo), two-pass loudnorm to -14 LUFS
  3. video: cut + speed ramp, 1080x1920 lanczos, contrast +10 %, saturation +12 %, unsharp,
     opaque Hebrew banner over the burned-in English caption, timed overlays, end card
  4. libx264 CRF 18, 30 fps, yuv420p, AAC 192k, faststart
"""
import argparse, json, os, re, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FPS = 30

# (src_start, src_end, speed, note) -- source seconds.  Gaps (12-14 s, 5-22.4 s tails, 26-28 s) are cut out.
SEGMENTS = [
    (0.0,  2.0,  1.0, "hook, normal speed (sharp foam/dirt contrast)"),
    (2.0,  2.5,  1.2, "ramp 1.0x -> 1.4x"),
    (2.5,  5.0,  1.4, "first pull, right side"),
    (5.0, 12.0,  1.6, "centre of seat, vertical pulls, murky water in the clear nozzle"),
    (14.0, 22.0, 1.8, "seams / seat-belt area (12-14 s cut)"),
    (22.4, 26.0, 1.8, "seat side by the console -> exactly 2.0 s"),
    (28.0, 31.0, 1.1, "final clean, even seat"),
]
# English voice-over window in the source (user spec: 00:00-00:02). Replaced by clean suction ambience
# lifted from this later, speech-free source window so the hook is not dead-silent.
VOICE_END = 2.0
AMBIENCE_SRC = 3.0
XFADE = 0.12          # ambience -> original-audio cross-fade at the end of the voice-over window
JOIN_XFADE = 0.03     # cross-fade at every other cut
LOUDNESS = dict(I=-14, TP=-1.5, LRA=11)


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd)[:240], flush=True)
    return subprocess.run(cmd, check=True, **kw)


def seg_out_durations():
    return [(e - s) / sp for s, e, sp, _ in SEGMENTS]


def build_audio(src, wav):
    """Every join is an equal-power cross-fade (no fade-to-silence dips). Each segment is extended by the
    overlap length (in source time) so the cross-fades consume exactly the extra audio and the total
    duration stays equal to the video."""
    durs = seg_out_durations()
    parts = []
    # 0..VOICE_END : ambience instead of the English voice-over; flows into the original audio from VOICE_END on
    parts.append(f"[0:a]atrim={AMBIENCE_SRC}:{AMBIENCE_SRC + VOICE_END + XFADE},asetpts=PTS-STARTPTS,aresample=48000[c0]")
    for i in range(1, len(SEGMENTS)):
        s, e, sp, _ = SEGMENTS[i]
        tail = 0.0 if i == len(SEGMENTS) - 1 else JOIN_XFADE * sp          # source seconds of overlap tail
        parts.append(f"[0:a]atrim={s}:{e + tail},asetpts=PTS-STARTPTS,aresample=48000,atempo={sp}[c{i}]")
    # segment 0's own audio (with the English voice) is never used; the ambience bed replaces it.
    # join 1 (ambience -> segment 1) uses XFADE, every later join JOIN_XFADE.
    prev = "c0"
    for i in range(1, len(SEGMENTS)):
        d = XFADE if i == 1 else JOIN_XFADE
        parts.append(f"[{prev}][c{i}]acrossfade=d={d}:c1=qsin:c2=qsin[x{i}]")
        prev = f"x{i}"
    total = sum(durs)
    graph = (";".join(parts) +
             f";[{prev}]atrim=0:{total:.4f},afade=t=in:d=0.01,afade=t=out:st={total - 0.15:.4f}:d=0.15,highpass=f=35[araw]")
    L = LOUDNESS
    meas = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-i", str(src), "-filter_complex",
         f"{graph};[araw]loudnorm=I={L['I']}:TP={L['TP']}:LRA={L['LRA']}:print_format=json[a]",
         "-map", "[a]", "-f", "null", "-"], capture_output=True, text=True, check=True).stderr
    m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", meas, re.S).group(0))
    ln = (f"loudnorm=I={L['I']}:TP={L['TP']}:LRA={L['LRA']}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex",
         f"{graph};[araw]{ln},aresample=48000[a]", "-map", "[a]", "-ac", "2", "-ar", "48000", str(wav)])
    return total


def build_video(src, wav, out, layers_cfg, manifest, png_dir, total):
    durs = seg_out_durations()
    inputs = ["-i", str(src)]
    chain = []
    # --- cut + speed ramp ---------------------------------------------------------------------
    for i, (s, e, sp, _) in enumerate(SEGMENTS):
        chain.append(f"[0:v]trim=start={s}:end={e},setpts=(PTS-STARTPTS)/{sp},fps={FPS},setsar=1[v{i}]")
    chain.append("".join(f"[v{i}]" for i in range(len(SEGMENTS))) + f"concat=n={len(SEGMENTS)}:v=1:a=0[vc]")
    # --- upscale 720x1280 -> 1080x1920, grade (+10 % contrast, +12 % saturation), light unsharp ----
    chain.append("[vc]scale=1080:1920:flags=lanczos,eq=contrast=1.10:saturation=1.12,"
                 "unsharp=5:5:0.5:5:5:0,format=yuv420p[base]")

    idx = 1
    def png_input(name):
        nonlocal idx
        inputs.extend(["-framerate", str(FPS), "-loop", "1", "-t", f"{total + 1:.3f}", "-i", str(png_dir / manifest[name]["file"])])
        idx += 1
        return idx - 1

    cur = "base"
    def overlay(label_in, name, fade_in=None, st=0.0, en=None, slide=0, fade_out=0.12, nid=None):
        """Overlay PNG `name`; alpha fades in at `st`, out before `en`; optional ease-out slide-up."""
        nonlocal cur
        k = png_input(name)
        f = f"[{k}:v]format=rgba"
        if fade_in:
            f += f",fade=t=in:st={st:.3f}:d={fade_in:.3f}:alpha=1"
        if en is not None:
            f += f",fade=t=out:st={en - fade_out:.3f}:d={fade_out:.3f}:alpha=1"
        chain.append(f + f"[p{k}]")
        m = manifest[name]
        if slide:
            y = f"{m['y']}+{slide}*pow(clip(1-(t-{st:.3f})/0.32,0,1),3)"
        else:
            y = str(m["y"])
        nxt = f"o{k}"
        chain.append(f"[{cur}][p{k}]overlay=x={m['x']}:y='{y}':eof_action=pass:format=auto[{nxt}]")
        cur = nxt

    overlay(cur, "banner")
    for l in layers_cfg["text_layers"]:
        overlay(cur, l["id"], fade_in=l["fade_in"] or None, st=l["start"], en=l["end"] if l["end"] is not None else None)
    ec = layers_cfg["end_card"]
    overlay(cur, "scrim", fade_in=0.35, st=ec["start"])
    overlay(cur, "endcard", fade_in=0.30, st=ec["start"] + 0.08, slide=34)
    chain.append(f"[{cur}]format=yuv420p[vout]")

    inputs.extend(["-i", str(wav)])
    a_idx = idx
    run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-stats", "-y", *inputs,
         "-filter_complex", ";".join(chain), "-map", "[vout]", "-map", f"{a_idx}:a",
         "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
         "-movflags", "+faststart", str(out)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default=str(HERE.parent / "output_reels.mp4"))
    ap.add_argument("--workdir", default=None, help="scratch dir (default: temp)")
    a = ap.parse_args()
    src, out = Path(a.input).resolve(), Path(a.output).resolve()
    work = Path(a.workdir or tempfile.mkdtemp(prefix="nikayon_")).resolve()
    work.mkdir(parents=True, exist_ok=True)

    cfg = json.loads((HERE / "layers.json").read_text(encoding="utf8"))
    total = sum(seg_out_durations())
    total = round(total * FPS) / FPS                      # whole number of frames
    print(f"output duration {total:.3f}s  ({total * FPS:.0f} frames @ {FPS} fps)")
    acc = 0.0
    for (s, e, sp, note), d in zip(SEGMENTS, seg_out_durations()):
        print(f"  out {acc:6.2f}-{acc + d:6.2f}s  <- src {s:5.1f}-{e:5.1f}s @{sp}x  {note}")
        acc += d
    png_dir = work / "overlays"
    env = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node-tools/node_modules"))
    run(["node", str(HERE / "render_overlays.cjs"), str(HERE / "layers.json"), str(HERE / "assets"), str(png_dir)], env=env)
    manifest = json.loads((png_dir / "manifest.json").read_text())

    wav = work / "audio_final.wav"
    build_audio(src, wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    build_video(src, wav, out, cfg, manifest, png_dir, total)
    print("done ->", out)


if __name__ == "__main__":
    main()
