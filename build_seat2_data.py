"""Timeline + captions for seat-extraction clip #2 -> remotion/src/data_seat2.json.
All times are seconds on the EDITED clip (public/seat2_edit.mp4, produced by edit_seat2.sh).
Segments (source -> edited): 12.6-15.1 1x (hook) | 0-9 2x | 15.5-23 2x | 23-29.4 1.5x
"""
import json, subprocess

FPS = 30
EDIT = "remotion/public/seat2_edit.mp4"
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                                     "-of", "csv=p=0", EDIT]).decode())
frames = round(dur * FPS)
segs = [(12.6, 15.1, 1), (0, 9, 2), (15.5, 23, 2), (23, 29.4, 1.5)]
bounds, t = [], 0.0
for s, e, sp in segs:
    bounds.append(round(t, 4)); t += (e - s) / sp
end_main = frames / FPS  

# (start, end, [(word, is_keyword)])  max 3 words per chunk (preset rule)
LINES = [
    (0.00, 1.25, [("זה", 0), ("יצא", 0), ("מהמושב", 1)]),                     # 0-2.5 s hook on the dirtiest water
    (1.25, 2.45, [("שאתם", 0), ("יושבים", 0), ("עליו", 1)]),
    (bounds[1] + 0.10, 4.70, [("מעבר", 0), ("אחד", 1), ("בלבד", 0)]),          # clean nozzle turns brown
    (4.70, bounds[2] - 0.10, [("והמים", 0), ("כבר", 0), ("חומים", 1)]),
    (bounds[2] + 0.10, 8.90, [("זיעה", 1), ("אבק", 1), ("שמן", 1)]),
    (8.90, bounds[3] - 0.10, [("שנים", 1), ("של", 1), ("לכלוך", 1)]),
    (bounds[3] + 0.10, 12.90, [("ניקוי", 0), ("עומק", 1), ("אמיתי", 1)]),
    (12.90, end_main - 0.10, [("רוצים", 0), ("מושב", 1), ("נקי?", 1)]),
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

INTRO = round(bounds[1] * FPS)
cands = sorted({round(x * FPS) for x in bounds[2:]} | {c[0]["startFrame"] for c in chunks if c[0]["startFrame"] >= INTRO})
beats = []
for b in cands:
    if not beats or b - beats[-1] >= 8:
        beats.append(b)

data = {
    "fps": FPS, "width": 1080, "height": 1920, "durationInFrames": frames,
    "captionSource": "build_car_seat_data.py", "chunks": chunks, "beats": beats, "audioBeats": [],
    "video": "seat2_edit.mp4", "logo": "logo_sayeret.png", "logoRound": False,
    "introFrames": INTRO, "introZoomTo": 1.15, "zoomOrigin": "45% 62%", "highlightActive": False,
    "outroFrames": 105,
    "outro": {"line1": "הצעת מחיר תוך דקה", "line2": "בוואטסאפ", "phone": "055-771-8519",
              "footer": "סיירת ניקיון · עבודה עברית"},
}
json.dump(data, open("remotion/src/data_seat2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"edited duration {dur:.3f}s = {frames} frames; segment starts {bounds}; beats(s) {[round(b/FPS,2) for b in beats]}")
for c in chunks:
    print(f"{c[0]['start']:6.2f}-{c[-1]['end']:6.2f}", " ".join(('*' if w['keyword'] else '') + w['text'] for w in c))
