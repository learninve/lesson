#!/usr/bin/env bash
# Usage: ./render.sh input.mp4 logo.png [output.mp4]
# Colortech reel: 1080x1920@30, Hebrew overlays (Pillow/raqm PNG layers), end screen, audio fade-out.
set -euo pipefail
cd "$(dirname "$0")"
IN="${1:?input video}"; LOGO="${2:?logo png}"; OUT="${3:-colortech_shpachtel_reel.mp4}"
EXTRA=3 STEP=0.3 TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Heebo Bold font (Hebrew+Latin merged) — built once from @fontsource/heebo
if [ ! -f fonts/Heebo-Bold.ttf ]; then
  mkdir -p fonts && (cd "$TMP" && npm pack @fontsource/heebo >/dev/null && tar xzf *.tgz && pip install -q fonttools &&
    python3 - <<'PY'
from fontTools.ttLib import TTFont; from fontTools import merge
for n in ('hebrew','latin'):
    f=TTFont(f'package/files/heebo-{n}-700-normal.woff'); f.flavor=None; f.save(f'{n}.ttf')
merge.Merger().merge(['hebrew.ttf','latin.ttf']).save('Heebo-Bold.ttf')
PY
  ) && cp "$TMP/Heebo-Bold.ttf" fonts/
fi
python3 -I layers.py "$LOGO" "$TMP"

D=$(ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 "$IN")
TOT=$(python3 -c "print($D+$EXTRA)")
FO=$(python3 -c "print($TOT-1.5)")
L="-loop 1 -framerate 30 -t $TOT -i $TMP"
ffmpeg -y -v error -stats -i "$IN" $L/title.png $L/logo_corner.png $L/caption.png \
  $L/end1_logo.png $L/end2.png $L/end3.png $L/end4.png -filter_complex "
[0:v]scale=1080:1920:flags=lanczos,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=$EXTRA,format=yuv420p[b0];
[b0]drawbox=x=0:y=0:w=iw:h=ih:color=black@0.6:t=fill:enable='gte(t,$D)'[b1];
[1:v]format=rgba,fade=in:st=0:d=0.4:alpha=1,fade=out:st=2.6:d=0.4:alpha=1[ti];
[b1][ti]overlay=0:0:eof_action=pass[b2];
[b2][2:v]overlay=0:0:enable='lt(t,$D)'[b3];
[b3][3:v]overlay=0:0:enable='between(t,3,$D)'[b4];
[4:v]format=rgba,fade=in:st=0:d=0.4:alpha=1,setpts=PTS+($D+0*$STEP)/TB[e1];
[5:v]format=rgba,fade=in:st=0:d=0.4:alpha=1,setpts=PTS+($D+1*$STEP)/TB[e2];
[6:v]format=rgba,fade=in:st=0:d=0.4:alpha=1,setpts=PTS+($D+2*$STEP)/TB[e3];
[7:v]format=rgba,fade=in:st=0:d=0.4:alpha=1,setpts=PTS+($D+3*$STEP)/TB[e4];
[b4][e1]overlay=0:0:eof_action=repeat[c1];[c1][e2]overlay=0:0:eof_action=repeat[c2];
[c2][e3]overlay=0:0:eof_action=repeat[c3];[c3][e4]overlay=0:0:eof_action=repeat,format=yuv420p[v];
[0:a]apad,atrim=0:$TOT,afade=t=out:st=$FO:d=1.5[a]" \
  -map "[v]" -map "[a]" -t "$TOT" -c:v libx264 -preset slow -crf 18 -r 30 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart "$OUT"

# review frames: start, middle, two from end screen
mkdir -p review
for spec in "start:0.5" "mid:8" "end_a:$(python3 -c "print($D+1.0)")" "end_b:$(python3 -c "print($TOT-0.3)")"; do
  ffmpeg -y -v error -ss "${spec#*:}" -i "$OUT" -frames:v 1 "review/${spec%%:*}.png"
done
echo "done: $OUT"
