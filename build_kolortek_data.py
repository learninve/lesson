"""Timeline + captions for the Kolortek drywall-niche clip -> remotion/src/data_kolortek.json.
All times are seconds on the EDITED clip (public/kolortek_edit.mp4, produced by edit_kolortek.sh).
Segments (source -> edited):
  39-40.4 1x (finished niche, result-first hook) | 0-6.5 2.5x | 6.5-10 1.5x (corner bead) |
  10-17.5 2.5x | 17.5-22 2x | 22-38 2.6x | 38-40.47 1x (last stroke -> wide reveal at source 39.0)
"""
import json, subprocess

FPS = 30
EDIT = "remotion/public/kolortek_edit.mp4"
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                                     "-of", "csv=p=0", EDIT]).decode())
frames = round(dur * FPS)
segs = [(39, 40.4, 1), (0, 6.5, 2.5), (6.5, 10, 1.5), (10, 17.5, 2.5), (17.5, 22, 2), (22, 38, 2.6), (38, 40.47, 1)]
bounds, t = [], 0.0
for s, e, sp in segs:
    bounds.append(round(t, 4)); t += (e - s) / sp
reveal = bounds[6] + 1.0  # source 39.0 = wide shot of the finished niche
end_main = frames / FPS

# (start, end, [(word, is_keyword)])  max 3 words per chunk
LINES = [
    (0.00, 0.70, [("רוצים", 0), ("נישה", 1)]),                       # hook over the finished result
    (0.70, bounds[1] - 0.05, [("כזאת?", 1)]),
    (bounds[1] + 0.05, 2.70, [("ככה", 0), ("זה", 0), ("מתחיל", 0)]),
    (2.70, bounds[2] - 0.10, [("שכבה", 0), ("ראשונה", 1)]),
    (bounds[2] + 0.05, 5.20, [("פינת", 0), ("מתכת", 1)]),            # corner bead pressed in
    (5.20, bounds[3] - 0.05, [("ישרה", 0), ("כמו", 0), ("סרגל", 1)]),
    (bounds[3] + 0.05, 7.90, [("החלקה", 0), ("עד", 0), ("המילימטר", 1)]),
    (7.90, bounds[4] - 0.10, [("חכו", 0), ("לסוף", 1)]),
    (bounds[4] + 0.05, 10.50, [("כל", 0), ("חיבור", 1)]),
    (10.50, bounds[5] - 0.10, [("נסגר", 0), ("חלק", 1)]),
    (bounds[5] + 0.10, 14.20, [("בלי", 0), ("קיצורי", 1), ("דרך", 1)]),
    (14.20, 15.90, [("עבודה", 0), ("עברית", 1)]),
    (15.90, bounds[6] - 0.15, [("עסק", 0), ("של", 0), ("מילואימניק", 1)]),
    (bounds[6] + 0.05, reveal - 0.05, [("והתוצאה...", 0)]),
    (reveal + 0.05, end_main - 0.05, [("מושלמת", 1)]),
]

chunks = []
for a, b, toks in LINES:
    span = (b - a) / len(toks)
    ch = []
    for i, (w, kw) in enumerate(toks):
        st, en = a + i * span, a + (i + 1) * span
        ch.append({"text": w, "start": round(st, 3), "end": round(en, 3), "keyword": bool(kw),
                   "startFrame": round(st * FPS), "endFrame": max(round(en * FPS), round(st * FPS) + 1)})
    chunks.append(ch)

INTRO = round(bounds[1] * FPS)  # push-in only over the 1.4 s hook
cands = sorted({round(x * FPS) for x in bounds[1:]} | {round(reveal * FPS)} |
               {c[0]["startFrame"] for c in chunks if c[0]["startFrame"] >= INTRO})
beats = []
for b in cands:
    if not beats or b - beats[-1] >= 8:
        beats.append(b)

data = {
    "fps": FPS, "width": 1080, "height": 1920, "durationInFrames": frames,
    "captionSource": "build_kolortek_data.py", "chunks": chunks, "beats": beats, "audioBeats": [],
    "video": "kolortek_edit.mp4", "logo": "logo.jpg", "logoRound": True,
    "introFrames": INTRO, "introZoomTo": 1.08, "zoomOrigin": "50% 50%", "highlightActive": False,
    "outroFrames": 105,
    "outro": {"line1": "להצעת מחיר", "line2": "שלחו וואטסאפ", "phone": "053-323-7036", "whatsapp": True,
              "footer": "קולורטק · עסק של מילואימניק · עבודה עברית"},
}
json.dump(data, open("remotion/src/data_kolortek.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"edited duration {dur:.3f}s = {frames} frames; segment starts {bounds}; reveal {reveal:.2f}s; beats(s) {[round(b/FPS,2) for b in beats]}")
for c in chunks:
    print(f"{c[0]['start']:6.2f}-{c[-1]['end']:6.2f}", " ".join(('*' if w['keyword'] else '') + w['text'] for w in c))
