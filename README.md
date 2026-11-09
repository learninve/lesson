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

---

# Plasterboard reel (board_input.mp4 → board_output.mp4)

Kolortek clip #2: a plasterboard standing on the floor, a thick bead of filler along
the edge, then long pulls with the wide knife until the face is smooth. 14.42 s,
720x1280, no speech (knife strokes only, peak RMS 0.26).

## 1. Cuts + loudness → `remotion/public/board_clean.mp4`
`./edit_board.sh board_input.mp4 remotion/public/board_clean.mp4`

Idle stretches were cut after reading the per-frame RMS and a 2 fps contact sheet:
0–0.55 s (static opening), 6.10–7.30 s (knife parked at the bottom), 8.40–9.05 s
(knife out of frame) and 13.10 s to the end (knife comes back in). 14.42 s → 10.70 s,
12 ms audio fades at the joins, lanczos upscale to 1080x1920, 30 fps.
A gentle compressor (−24 dB, 3:1, +4 dB makeup) runs before the two-pass `loudnorm`:
the track is sparse transients over silence, so a purely linear gain stops at −16.7 LUFS
under the −1.5 dBTP ceiling. Measured output: −14.8 LUFS, −0.7 dBTP.

## 2. Captions → `captions_board.json`
No speech, so the lines are editor-written hooks timed to the strokes (max 3 words,
keywords in yellow). Voice: a tradesman explaining to a homeowner, no selling and no
naming other painters. The file also carries an `overrides` object
(video, logo, zoom, outro…) that `build_timeline.py` merges into the data:

```
python3 build_timeline.py remotion/public/board_clean.mp4 remotion/src/data_board.json captions_board.json transcript.json
```

## 3. Direction (Remotion composition `Board`)
* Same `ViralReel` component; new `captionBox` flag draws a dark rounded box behind the
  captions because the footage is almost entirely white (brand rule: white is the hero,
  text needs a dark box or a thick outline – here it gets both).
* `highlightActive: false` – with no speech there is nothing to karaoke, only the
  keywords turn yellow.
* Push-in 1.00 → 1.10 over 2.5 s, then jump cuts on the beats (knife onsets ∪ line starts).
* Round Kolortek badge top-centre.
* 2.5 s end card: "קיר שנראה טוב / גם אחרי שנה" and "קולורטק · הפרטים בכיתוב".
  **No phone number in the video** – contact details go in the post caption and the
  first comment only (ליאב 053-3237036).

## 4. Render → `board_output.mp4`
```
cd remotion && npx remotion render src/index.ts Board ../board_output.mp4 \
  --codec h264 --crf 18 --browser-executable /opt/pw-browsers/chromium
```
Output: 1080x1920, 30 fps, 13.2 s (10.7 s clip + 2.5 s end card), −15.1 LUFS integrated
(the muted end card pulls the integrated figure ~0.3 LU below the clip itself).

## Suggested post caption (not in the video)
שפכטל על גבס, בלי קיצורים. ככה הקיר נראה לפני שהצבע בכלל מגיע.
קולורטק · שפכטל, החלקת קירות, צבע וגבס · ליאב 053-3237036
