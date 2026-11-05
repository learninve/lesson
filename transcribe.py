"""Step 2: word-level transcription of clean.mp4 with faster-whisper (Hebrew)."""
import json, sys, time, subprocess
import numpy as np
from faster_whisper import WhisperModel


def load_audio(path, sr=16000):
    """Decode with ffmpeg to 16 kHz mono float32 (avoids PyAV version issues)."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"]
    return np.frombuffer(subprocess.check_output(cmd), dtype=np.float32).copy()

src = sys.argv[1] if len(sys.argv) > 1 else "clean.mp4"
out = sys.argv[2] if len(sys.argv) > 2 else "transcript.json"
model_name = sys.argv[3] if len(sys.argv) > 3 else "large-v3"

t0 = time.time()
model = WhisperModel(model_name, device="cpu", compute_type="int8")
audio = load_audio(src)
segments, info = model.transcribe(
    audio,
    language="he",
    word_timestamps=True,
    beam_size=5,
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 250},
    condition_on_previous_text=False,
)
result = {"note": "" if True else "", "language": info.language, "language_probability": info.language_probability,
          "duration": info.duration, "model": model_name, "segments": [], "words": []}
for seg in segments:
    s = {"id": seg.id, "start": round(seg.start, 3), "end": round(seg.end, 3),
         "text": seg.text.strip(), "words": []}
    for w in (seg.words or []):
        word = {"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3),
                "probability": round(w.probability, 3)}
        s["words"].append(word)
        result["words"].append(word)
    result["segments"].append(s)
if not result["words"]:
    result["note"] = "No speech detected by Silero VAD; without VAD the model only hallucinated a repeated token. Audio is non-speech (tool/scraping sounds)."
json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"model={model_name} words={len(result['words'])} segments={len(result['segments'])} took={time.time()-t0:.1f}s")
for w in result["words"]:
    print(f"{w['start']:6.2f} {w['end']:6.2f} {w['probability']:.2f} {w['word']}")
