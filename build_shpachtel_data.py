"""Timeline + captions for the Kolortek plastering clip -> remotion/src/data_shpachtel.json.
Times are seconds on remotion/public/shpachtel_edit.mp4 (edit_shpachtel.sh); lines follow the blade strokes."""
import json, subprocess

FPS = 30
EDIT = "remotion/public/shpachtel_edit.mp4"
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                     "stream=duration", "-of", "csv=p=0", EDIT]).decode())
frames = round(dur * FPS)

# (start, end, [(word, is_keyword)])  max 3 words per chunk
LINES = [
    (0.00, 1.50, [("תראו", 0), ("את", 0), ("הקיר", 1)]),
    (1.50, 3.00, [("מעבר", 1), ("אחד...", 0)]),
    (3.20, 5.00, [("חלק", 1), ("כמו", 0), ("מראה", 1)]),
    (5.20, 6.90, [("בלי", 0), ("גלים", 1)]),
    (7.00, 8.60, [("בלי", 0), ("סימנים", 1)]),
    (8.70, 10.70, [("גימור", 1), ("של", 0), ("מקצוענים", 1)]),
    (11.30, dur - 0.1, [("רוצים", 0), ("קיר", 1), ("כזה?", 1)]),
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

INTRO = 3 * FPS
beats = [c[0]["startFrame"] for c in chunks if c[0]["startFrame"] >= INTRO]
data = {
    "fps": FPS, "width": 1080, "height": 1920, "durationInFrames": frames,
    "captionSource": "build_shpachtel_data.py", "chunks": chunks, "beats": beats, "audioBeats": [],
    "video": "shpachtel_edit.mp4", "logo": "logo.jpg", "logoRound": True,
    "introFrames": INTRO, "introZoomTo": 1.12, "highlightActive": False,
    "outroFrames": 90,  # default Kolortek end card: logo + "להצעת מחיר" + 053-323-7036
}
json.dump(data, open("remotion/src/data_shpachtel.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"{dur:.3f}s = {frames} frames; beats {beats}")
