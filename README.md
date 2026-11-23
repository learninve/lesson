# Viral Reels pipeline (input.mp4 → viral_output.mp4)

9:16, 1080x1920, 30 fps. Everything was measured on the actual file; no timings are guessed.

## 1. Silence removal + loudness (Auto-Editor / FFmpeg) → `clean.mp4`
* The audio has a continuous noise floor (0.07–0.33 RMS), so Auto-Editor's default
  threshold cuts nothing. Per-frame levels (`auto-editor levels`) were used to find
  gaps ≥ 0.25 s below 0.30 RMS; 7 gaps were cut with `--cut-out`, keeping an 80 ms pad
  on each side (12.07 s → 9.90 s).
* Two-pass `loudnorm` to **-14 LUFS** (measured -14.0 LUFS, TP -1.5 dBTP), lanczos
  upscale 720x1280 → 1080x1920, 30 fps, AAC 48 kHz → `clean.mp4` (10.0 s).

## 2. Word timestamps (faster-whisper) → `transcript.json`
`python3 transcribe.py clean.mp4 transcript.json <model-dir>` (language `he`,
`word_timestamps=True`, Silero VAD, audio decoded through FFmpeg).

**Finding: the clip contains no speech.** It is a drywall-plastering ASMR shot: the
spectrogram shows only broadband scraping noise, Whisper's language ID is ~0.25
confidence, VAD finds zero speech regions, and without VAD the model only
hallucinates one repeated token. `transcript.json` therefore holds `words: []` plus a
note. `huggingface.co` is blocked by the session's network policy, so the model used
is Whisper *small* (CTranslate2 int8) fetched from npm; re-run with `large-v3` once
HF is allowed if a spoken clip is used.

## 3. Direction (Remotion) → `remotion/`
`python3 build_timeline.py clean.mp4 remotion/src/data.json` builds the timeline:
* Captions come from `transcript.json` when it has words (chunked into ≤3 words,
  current word highlighted). Because this clip has none, they fall back to
  **`captions.json`** – placeholder Hebrew hook lines written by the editor, timed to
  the plastering strokes. Edit that file and rebuild.
* `remotion/src/ViralReel.tsx`: Heebo 900, `dir="rtl"`, white text with a thick black
  stroke, max 3 words on screen, active word / keywords in `#FFE600` with a spring
  pop, centred horizontally at 65 % from the top (safe zone).
* Pattern interrupts: eased push-in 1.00 → 1.12 over the first 3 s, then jump cuts
  that toggle between 1.00 and 1.15 on every beat (audio stroke onsets ∪ caption
  line starts, deduped within 8 frames; see `beats` in `data.json`).

### Branding
* `remotion/public/logo.jpg` (Kolortek badge) is shown as a round watermark, top-centre,
  for the whole clip (springs in on frame 0).
* A 2 s end card (`OUTRO_FRAMES = 60`, frozen last frame + dark overlay) shows the badge
  large, "להצעת מחיר" and the phone number 053-323-7036 in `#FFE600`.

## 4. Render → `viral_output.mp4`
```
cd remotion && npx remotion render src/index.ts ViralReel ../viral_output.mp4 \
  --codec h264 --crf 18 --browser-executable /opt/pw-browsers/chromium
```
Output: 1080x1920, 30 fps, 12.0 s (10 s clip + 2 s end card), -14 LUFS.

## Kolortek drywall-seam reel → `kolortek_seam_final.mp4`
52 s raw clip (knife opening a cracked drywall seam, no speech) → 18.6 s reel.
```
./edit_cuts.sh raw.mp4 remotion/public/seam_edit.mp4 "0 1.25 1" "2 8.8 2" "11.4 15.9 1.5" \
    "19.3 25.3 2.5" "38.7 42.7 1.25" "49.95 51.8 1"      # source seconds + speed, -14 LUFS
python3 build_seam_data.py                               # captions/beats -> remotion/src/data_seam.json
cd remotion && npx remotion render src/index.ts KolortekSeam ../kolortek_seam_final.mp4 \
    --codec h264 --crf 18 --browser-executable /opt/pw-browsers/chromium
```
Captions are written copy (edit `LINES` in `build_seam_data.py`); the 3.5 s end card shows the
Kolortek badge, "להצעת מחיר" and 053-323-7036. `edit_cuts.sh` is the generic form of
`edit_car_seat.sh` (segments passed as arguments).
The Remotion output is full-range `yuvj420p` (21 MB), which some phones/apps refuse to load, so the
delivered file is re-encoded to standard `yuv420p` bt709 TV-range, CRF 21 (max 6 Mbps), AAC 44.1 kHz, faststart.
