import subprocess, sys
SRC = sys.argv[1]; OUT = sys.argv[2]
BASE = "crop=622:1105:49:175"
ZOOM = "crop=540:960:90:260"
Y = r"{\c&H00D4FF&}"   # yellow
POP = r"{\fscx70\fscy70\t(0,110,\fscx108\fscy108)\t(110,190,\fscx100\fscy100)}"
# (src_start, src_end, speed, crop, captions[(rel_start, rel_end|None, style, text)])
segs = [
 (0.60, 3.10, 1.0, BASE, [(0, None, "Main", POP+"שאבת את המושב?\\N"+Y+"זה מה שנשאר בפנים")]),
 (18.0, 20.4, 0.7, ZOOM, [(0, None, "Main", POP+Y+"מעבר אחד.\\N"+r"{\c&HFFFFFF&}"+"על מושב ש״נראה נקי״")]),
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
]
def ts(t):
    h=int(t//3600); m=int(t%3600//60); s=t%60
    return f"{h}:{m:02d}:{s:05.2f}"
fc=[]; events=[]; t=0.0; last=None
for i,(a,b,sp,crop,caps) in enumerate(segs):
    d=(b-a)/sp
    fc.append(f"[0:v]trim=start={a}:end={b},setpts=(PTS-STARTPTS)/{sp},{crop},scale=1080:1920:flags=lanczos,setsar=1,fps=30[v{i}]")
    at = f"atrim=start={a}:end={b},asetpts=PTS-STARTPTS" + (f",atempo={sp}" if sp!=1 else "")
    fc.append(f"[0:a]{at},afade=t=in:d=0.02,afade=t=out:st={d-0.03:.3f}:d=0.03[a{i}]")
    if caps=="cont":
        last[1]=t+d   # extend previous caption across quick cuts
    else:
        for (rs,re,st,txt) in caps:
            ev=[t+rs, t+(re if re is not None else d), st, txt]
            events.append(ev); last=ev
    t+=d
n=len(segs)
fc.append("".join(f"[v{i}][a{i}]" for i in range(n))+f"concat=n={n}:v=1:a=1[cv][ca]")
fc.append("[cv]eq=contrast=1.07:saturation=1.18,unsharp=5:5:0.6,subtitles=subs.ass:fontsdir=fonts[vout]")
fc.append("[ca]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[aout]")
with open("subs.ass") as f: head=f.read().split("[Events]")[0]
with open("subs.ass","w") as f:
    f.write(head+"[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    for s,e,st,txt in events:
        txt=txt.replace("\\N","\u200f\\N\u200f")+"\u200f"; txt=txt.replace("}","}\u200f"); f.write(f"Dialogue: 0,{ts(s)},{ts(e)},{st},,0,0,0,,{txt}\n")
print("total", round(t,2))
cmd=["ffmpeg","-v","error","-y","-i",SRC,"-filter_complex",";".join(fc),"-map","[vout]","-map","[aout]",
     "-c:v","libx264","-preset","slow","-crf","17","-profile:v","high","-pix_fmt","yuv420p","-r","30",
     "-c:a","aac","-b:a","192k","-movflags","+faststart",OUT]
subprocess.run(cmd,check=True)
