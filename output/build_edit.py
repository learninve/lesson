"""Builds the viral cut: python3 build_edit.py <source.mp4> <out.mp4>
Run from this folder (uses assets/logo.png, assets/fonts, writes captions.ass)."""
import subprocess, sys

SRC, OUT = sys.argv[1], sys.argv[2]
LOGO = "assets/logo.png"
PHONE = "055-7718519"

BASE = "crop=622:1105:49:175"          # cuts away the burned-in English caption
ZOOM = "crop=540:960:90:260"
BLUR = BASE + ",scale=540:960,boxblur=18:2"  # end-card background
Y = r"{\c&H00D4FF&}"   # yellow
W = r"{\c&HFFFFFF&}"
POP = r"{\fscx70\fscy70\t(0,110,\fscx108\fscy108)\t(110,190,\fscx100\fscy100)}"

# (src_start, src_end, speed, video_filter, captions[(rel_start, rel_end|None, style, text)] | "cont")
segs = [
 (0.60, 3.10, 1.0, BASE, [(0, None, "Main", POP+"שאבת את המושב?\\N"+Y+"זה מה שנשאר בפנים")]),
 (18.0, 20.4, 0.7, ZOOM, [(0, None, "Main", POP+Y+"מעבר אחד.\\N"+W+"על מושב ש״נראה נקי״")]),
 (22.0, 25.0, 1.0, BASE, [(0.0, 0.6, "Big", POP+"זיעה."),
                          (0.6, 1.2, "Big", "זיעה. "+POP+"קפה."),
                          (1.2, 1.9, "Big", "זיעה. קפה.\\N"+POP+Y+"עור מת."),
                          (1.9, None, "Big", "זיעה. קפה.\\N"+Y+"עור מת. חול מהים.")]),
 (5.0, 6.3, 1.0, BASE, [(0, None, "Main", POP+"שואב רגיל מנקה\\N"+Y+"רק את השכבה העליונה")]),
 (13.0, 14.2, 1.0, BASE, "cont"),
 (26.6, 27.9, 1.0, BASE, "cont"),
 (36.15, 40.0, 1.0, BASE, [(0, 1.9, "Main", POP+"שימו לב לצבע..."),
                           (1.9, None, "Big", POP+Y+"זה הצבע\\Nהמקורי")]),
 (56.6, 60.0, 1.0, BASE, [(0, None, "Main", POP+"והרצפה?\\N"+Y+"עוד לא התחלנו...")]),
 (14.4, 17.6, 1.0, BASE, [(0, None, "Main", POP+"כמה זמן לא ניקית\\Nאת המושבים?\\N"+Y+r"{\fs80}"+"כתבו בתגובות. בכנות.")]),
 # end card: blurred footage + big logo + offer
 (0.6, 5.1, 1.0, BLUR, [(0.25, None, "Card", r"{\an5\pos(540,930)}"+POP+"שלחו תמונה של הרכב"),
                        (0.55, None, "Phone", r"{\an5\pos(540,1080)}"+POP+PHONE),
                        (0.85, None, "Card", r"{\an5\pos(540,1230)}"+POP+"וקבלו הצעת מחיר"),
                        (1.05, None, "Card", r"{\an5\pos(540,1350)}"+POP+Y+"תוך דקה!")]),
]
ENDCARD = len(segs) - 1

HEADER = r"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Rubik Black,102,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,7,3,8,60,60,370,177
Style: Big,Rubik Black,135,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,8,4,8,60,60,370,177
Style: Card,Rubik Black,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,7,3,5,40,40,0,177
Style: Phone,Rubik Black,150,&H0000D4FF,&H0000D4FF,&H00000000,&H64000000,0,0,0,0,100,100,2,0,1,9,4,5,40,40,0,177

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def ts(t):
    return f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"

def rtl(txt):  # RLM marks so libass puts Hebrew punctuation on the correct side
    return txt.replace("\\N", "‏\\N‏").replace("}", "}‏") + "‏"

fc, events, t, last, starts = [], [], 0.0, None, []
for i, (a, b, sp, vf, caps) in enumerate(segs):
    d = (b - a) / sp
    starts.append(t)
    extra = ",eq=brightness=-0.18:saturation=0.8" if i == ENDCARD else ""
    fc.append(f"[0:v]trim=start={a}:end={b},setpts=(PTS-STARTPTS)/{sp},{vf},scale=1080:1920:flags=lanczos,setsar=1,fps=30{extra}[v{i}]")
    at = f"atrim=start={a}:end={b},asetpts=PTS-STARTPTS" + (f",atempo={sp}" if sp != 1 else "")
    if i == ENDCARD:
        at += f",volume=0.35,afade=t=out:st={d-1.5:.3f}:d=1.5"
    fc.append(f"[0:a]{at},afade=t=in:d=0.02,afade=t=out:st={d-0.03:.3f}:d=0.03[a{i}]")
    if caps == "cont":
        last[1] = t + d
    else:
        for rs, re, st, txt in caps:
            ev = [t + rs, t + (re if re is not None else d), st, txt]
            events.append(ev); last = ev
    t += d
TOTAL, TC = t, starts[ENDCARD]
n = len(segs)
fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]")
fc.append("[cv]eq=contrast=1.07:saturation=1.18,unsharp=5:5:0.6[graded]")
# small watermark (top-right, clear of TikTok/Reels UI) from 2.5s until the end card
fc.append("[1:v]scale=170:170,format=rgba,colorchannelmixer=aa=0.92[wm]")
fc.append(f"[graded][wm]overlay=x=W-w-40:y=190:enable='between(t,2.5,{TC:.3f})'[g1]")
# big logo on the end card, fades in
fc.append(f"[2:v]scale=520:520,format=rgba,fade=t=in:st={TC:.3f}:d=0.35:alpha=1[big]")
fc.append(f"[g1][big]overlay=x=(W-w)/2:y=250:enable='gte(t,{TC:.3f})'[g2]")
fc.append("[g2]subtitles=captions.ass:fontsdir=assets/fonts[vout]")
fc.append("[ca]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[aout]")

with open("captions.ass", "w") as f:
    f.write(HEADER)
    for s, e, st, txt in events:
        f.write(f"Dialogue: 0,{ts(s)},{ts(e)},{st},,0,0,0,,{rtl(txt)}\n")
print(f"total {TOTAL:.2f}s, end card at {TC:.2f}s")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC,
                "-loop", "1", "-t", f"{TOTAL:.3f}", "-i", LOGO,
                "-loop", "1", "-t", f"{TOTAL:.3f}", "-i", LOGO,
                "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high",
                "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", OUT], check=True)
