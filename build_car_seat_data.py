"""Timeline + captions for the car-seat clip -> remotion/src/data_car_seat.json.
All times are seconds on the EDITED clip (public/car_seat_edit.mp4, produced by edit_car_seat.sh).
Segments (source -> edited): 0-4 1x | 4-17 2.5x | 21-30 2.5x | 33-40 1.5x | 42-48 1.5x
"""
import json, subprocess

FPS = 30
EDIT = "remotion/public/car_seat_edit.mp4"
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                                     "-of", "csv=p=0", EDIT]).decode())
frames = round(dur * FPS)
segs = [(0, 4, 1), (4, 17, 2.5), (21, 30, 2.5), (33, 40, 1.5), (42, 48, 1.5)]
bounds, t = [], 0.0
for s, e, sp in segs:
    bounds.append(round(t, 4)); t += (e - s) / sp
end_main = frames / FPS  # 21.4667 s

# (start, end, [(word, is_keyword)])  max 3 words per chunk (preset rule)
LINES = [
    (0.00, 1.50, [("הייתם", 0), ("יושבים", 0)]),
    (1.50, 3.00, [("על", 0), ("מושב", 1), ("כזה?", 1)]),                       # 0-3 s hook
    (bounds[2] + 0.10, 10.10, [("מוציאים", 0)]),                                 # rotating brush 9.2-12.8
    (10.10, bounds[3] - 0.10, [("שנים", 1), ("של", 1), ("לכלוך", 1)]),
    (bounds[3] + 0.10, 15.20, [("חכו", 0), ("לתוצאה", 1)]),                      # 2nd extraction 12.8-17.47
    (15.20, bounds[4] - 0.07, [("בסוף...", 0)]),
    (end_main - 3.0, 20.10, [("רוצים", 0), ("חידוש", 0), ("כזה?", 0)]),        # last 3 s -> end card
    (20.10, end_main, [("שלחו", 1), ("הודעה", 1)]),
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

INTRO = 4 * FPS
cands = sorted({round(x * FPS) for x in bounds[2:]} | {c[0]["startFrame"] for c in chunks if c[0]["startFrame"] >= INTRO})
beats = []
for b in cands:
    if not beats or b - beats[-1] >= 8:
        beats.append(b)

data = {
    "fps": FPS, "width": 1080, "height": 1920, "durationInFrames": frames,
    "captionSource": "build_car_seat_data.py", "chunks": chunks, "beats": beats, "audioBeats": [],
    "video": "car_seat_edit.mp4", "logo": "logo_nikayon.png", "logoRound": False,
    "introFrames": INTRO, "introZoomTo": 1.15, "zoomOrigin": "48% 60%", "highlightActive": False,
    "outro": {"line1": "רוצים חידוש כזה?", "line2": "שלחו הודעה", "footer": "סיירת ניקיון · עבודה עברית"},
}
json.dump(data, open("remotion/src/data_car_seat.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"edited duration {dur:.3f}s = {frames} frames; segment starts {bounds}; beats(s) {[round(b/FPS,2) for b in beats]}")
for c in chunks:
    print(f"{c[0]['start']:6.2f}-{c[-1]['end']:6.2f}", " ".join(('*' if w['keyword'] else '') + w['text'] for w in c))
