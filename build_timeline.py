"""Step 3 (data): turn transcript.json (+ captions.json fallback) and the audio
levels of clean.mp4 into remotion/src/data.json for the ViralReel composition.

- words: word-level cues (start/end seconds -> frames), grouped into caption
  chunks of max 3 words, with keyword flags.
- beats: frames for jump cuts = audio onsets (stroke attacks) merged with the
  start of every caption chunk, deduped within 8 frames.
"""
import json, subprocess, sys, re
import numpy as np

FPS = 30
VIDEO = sys.argv[1] if len(sys.argv) > 1 else "clean.mp4"
OUT = sys.argv[2] if len(sys.argv) > 2 else "remotion/src/data.json"

def probe_duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path]).decode().strip())

def audio_levels(path, fps=FPS, sr=16000):
    pcm = np.frombuffer(subprocess.check_output(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"]),
        dtype=np.float32)
    hop = sr // fps
    n = len(pcm) // hop
    rms = np.sqrt((pcm[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    return rms / (rms.max() or 1.0)

def onsets(levels, rise=0.30, floor=0.35, min_gap=12):
    """Frames where energy jumps by >= `rise` within 2 frames from a quiet floor."""
    out = []
    for i in range(2, len(levels)):
        if levels[i] - levels[i - 2] >= rise and levels[i - 2] < floor:
            if not out or i - out[-1] >= min_gap:
                out.append(i)
    return out

def to_frame(sec):
    return int(round(sec * FPS))

def chunk_words(words, max_words=3, max_gap=0.6):
    """Group consecutive words into on-screen chunks of <= max_words, breaking on pauses."""
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w["start"] - cur[-1]["end"] > max_gap):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks

duration = probe_duration(VIDEO)
duration_frames = int(round(duration * FPS))
tr = json.load(open("transcript.json", encoding="utf-8"))
source = "transcript.json"
words = []
if tr.get("words"):
    for w in tr["words"]:
        words.append({"text": w["word"], "start": w["start"], "end": w["end"], "keyword": False})
    chunks = chunk_words(words)
else:
    source = "captions.json"
    cap = json.load(open("captions.json", encoding="utf-8"))
    chunks = []
    for line in cap["lines"]:
        toks = line["text"].split()
        assert len(toks) <= 3, f"line has more than 3 words: {line['text']}"
        span = (line["end"] - line["start"]) / len(toks)
        chunk = []
        for i, t in enumerate(toks):
            chunk.append({"text": t, "start": round(line["start"] + i * span, 3),
                          "end": round(line["start"] + (i + 1) * span, 3),
                          "keyword": t in line.get("keywords", [])})
        chunks.append(chunk)
        words.extend(chunk)

levels = audio_levels(VIDEO)
audio_beats = onsets(levels)
chunk_beats = [to_frame(c[0]["start"]) for c in chunks]
beats = []
for b in sorted(set(audio_beats + chunk_beats)):
    if not beats or b - beats[-1] >= 8:
        beats.append(b)

data = {
    "fps": FPS,
    "width": 1080, "height": 1920,
    "durationInFrames": duration_frames,
    "captionSource": source,
    "chunks": [[{**w, "startFrame": to_frame(w["start"]), "endFrame": max(to_frame(w["end"]), to_frame(w["start"]) + 1)}
                for w in c] for c in chunks],
    "beats": beats,
    "audioBeats": audio_beats,
}
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"duration={duration:.2f}s frames={duration_frames} source={source} chunks={len(chunks)} words={len(words)}")
print("audio onsets (s):", [round(b / FPS, 2) for b in audio_beats])
print("beats (s):", [round(b / FPS, 2) for b in beats])
for c in chunks:
    print(f"  {c[0]['start']:5.2f}-{c[-1]['end']:5.2f}  " + " ".join(('*' if w['keyword'] else '') + w['text'] for w in c))
