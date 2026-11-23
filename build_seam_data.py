"""Timeline + captions for the Kolortek drywall-seam clip -> remotion/src/data_seam.json.
All times are seconds on the EDITED clip (remotion/public/seam_edit.mp4), produced by:
  ./edit_cuts.sh raw.mp4 remotion/public/seam_edit.mp4 "0 1.25 1" "2 8.8 2" "11.4 15.9 1.5" \
      "19.3 25.3 2.5" "38.7 42.7 1.25" "49.95 51.8 1"
The clip has no speech (knife-on-drywall ASMR), so the captions are written copy, not a transcript.
"""
import json, subprocess

FPS = 30
EDIT = "remotion/public/seam_edit.mp4"
SEGS = [(0, 1.25, 1), (2, 8.8, 2), (11.4, 15.9, 1.5), (19.3, 25.3, 2.5), (38.7, 42.7, 1.25), (49.95, 51.8, 1)]
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                                     "-of", "csv=p=0", EDIT]).decode())
frames = round(dur * FPS)
b, t = [], 0.0  # segment starts on the edited timeline
for s, e, sp in SEGS:
    b.append(round(t, 4)); t += (e - s) / sp
end_main = frames / FPS

# (start, end, [(word, is_keyword)])  max 3 words per chunk
LINES = [
    (0.00, b[1], [("אל", 0), ("תצבעו", 0)]),                                   # static crack: the hook
    (b[1], 2.50, [("על", 0), ("סדק", 1), ("כזה!", 1)]),                         # knife enters on the cut
    (2.50, 3.55, [("שפכטל", 0), ("מעל?", 0)]),
    (3.55, b[2] - 0.05, [("הסדק", 0), ("יחזור", 1)]),
    (b[2] + 0.05, 6.10, [("אנחנו", 0), ("פותחים", 0)]),                         # close-up: strip pulled out
    (6.10, b[3] - 0.05, [("עד", 1), ("הסוף", 1)]),
    (b[3] + 0.05, b[4] - 0.05, [("מוציאים", 0), ("את", 0), ("הישן", 1)]),       # second seam, 2.5x
    (b[4] + 0.05, b[5] - 0.05, [("בלי", 0), ("קיצורי", 1), ("דרך", 1)]),        # long peel + dust
    (b[5] + 0.05, end_main - 0.05, [("ככה", 0), ("מתקנים", 0), ("נכון", 1)]),   # opened seam, wide
]

chunks = []
for a, z, toks in LINES:
    span = (z - a) / len(toks)
    ch = []
    for i, (w, kw) in enumerate(toks):
        st, en = a + i * span, a + (i + 1) * span
        ch.append({"text": w, "start": round(st, 3), "end": round(en, 3), "keyword": bool(kw),
                   "startFrame": round(st * FPS), "endFrame": max(round(en * FPS), round(st * FPS) + 1)})
    chunks.append(ch)

INTRO = round(b[1] * FPS)  # slow push-in on the crack, then the first cut lands with the knife
cands = sorted({round(x * FPS) for x in b[1:]} | {c[0]["startFrame"] for c in chunks if c[0]["startFrame"] >= INTRO})
beats = []
for x in cands:
    if not beats or x - beats[-1] >= 8:
        beats.append(x)

data = {
    "fps": FPS, "width": 1080, "height": 1920, "durationInFrames": frames,
    "captionSource": "build_seam_data.py", "chunks": chunks, "beats": beats, "audioBeats": [],
    "video": "seam_edit.mp4", "logo": "logo.jpg", "logoRound": True,
    "introFrames": INTRO, "introZoomTo": 1.15, "zoomOrigin": "50% 45%", "highlightActive": False,
    "outroFrames": 105,
    "outro": {"line1": "סדקים בבית?", "line2": "להצעת מחיר", "phone": "053-323-7036",
              "footer": "קולורטק · עבודה עברית"},
}
json.dump(data, open("remotion/src/data_seam.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"edited duration {dur:.3f}s = {frames} frames; segment starts {b}; beats(s) {[round(x/FPS,2) for x in beats]}")
for c in chunks:
    print(f"{c[0]['start']:6.2f}-{c[-1]['end']:6.2f}", " ".join(('*' if w['keyword'] else '') + w['text'] for w in c))
