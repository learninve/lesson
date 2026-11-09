#!/usr/bin/env bash
# Step 1 for the plasterboard clip (board_input.mp4): cut the idle stretches,
# 720x1280 -> 1080x1920 lanczos, 30 fps, gentle compression (the audio is only sparse
# knife strokes over silence, so a purely linear gain cannot reach -14 LUFS under
# the -1.5 dBTP ceiling), then two-pass loudnorm to -14 LUFS.
# usage: ./edit_board.sh board_input.mp4 remotion/public/board_clean.mp4
# Cut plan (source seconds, measured on the file – see README):
#   0.00-0.55  static opening (nothing moves yet)        -> cut
#   0.55-6.10  bead + first long pull + wide-knife pass  -> keep
#   6.10-7.30  knife parked at the bottom, repositioning  -> cut
#   7.30-8.40  upward stroke                               -> keep
#   8.40-9.05  knife out of frame, wall only               -> cut
#   9.05-13.10 finishing strokes, then the smooth result   -> keep
#   13.10-14.42 knife comes back in from the left          -> cut
set -euo pipefail
IN=${1:?input}; OUT=${2:?output}
SEGS=("0.55 6.10" "7.30 8.40" "9.05 13.10")

V=""; A=""; CAT=""
for i in "${!SEGS[@]}"; do
  read -r s e <<<"${SEGS[$i]}"
  V+="[0:v]trim=${s}:${e},setpts=PTS-STARTPTS,scale=1080:1920:flags=lanczos,unsharp=5:5:0.5,setsar=1,fps=30[v$i];"
  D=$(awk -v s="$s" -v e="$e" 'BEGIN{printf "%.4f",(e-s)-0.012}')
  A+="[0:a]atrim=${s}:${e},asetpts=PTS-STARTPTS,aresample=48000,acompressor=threshold=-24dB:ratio=3:attack=4:release=150:makeup=4,afade=t=in:d=0.012,afade=t=out:st=${D}:d=0.012[a$i];"
  CAT+="[v$i][a$i]"
done
GRAPH="${V}${A}${CAT}concat=n=${#SEGS[@]}:v=1:a=1[v][araw]"

M=$(ffmpeg -nostdin -hide_banner -i "$IN" -filter_complex "${GRAPH};[araw]loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[a]" \
    -map "[v]" -map "[a]" -f null - 2>&1 | sed -n '/^{/,/^}/p')
g() { echo "$M" | python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
LN="loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true"

ffmpeg -nostdin -hide_banner -y -i "$IN" -filter_complex "${GRAPH};[araw]${LN},aresample=48000[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUT"
