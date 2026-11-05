#!/usr/bin/env bash
# Step 1 for the car-seat clip: cuts + speed ramps + 1080x1920 upscale + -14 LUFS.
# usage: ./edit_car_seat.sh raw.mp4 remotion/public/car_seat_edit.mp4
# Edit plan (source seconds -> speed); gaps between segments are cut out:
#   0-4 @1x | 4-17 @2.5x | 21-30 @2.5x | 33-40 @1.5x | 42-48 @1.5x
set -euo pipefail
IN=${1:?input}; OUT=${2:?output}
SEGS=("0 4 1" "4 17 2.5" "21 30 2.5" "33 40 1.5" "42 48 1.5")

V=""; A=""; CAT=""
for i in "${!SEGS[@]}"; do
  read -r s e sp <<<"${SEGS[$i]}"
  V+="[0:v]trim=${s}:${e},setpts=(PTS-STARTPTS)/${sp},scale=1080:1920:flags=lanczos,eq=contrast=1.05:saturation=1.12,unsharp=5:5:0.6,setsar=1,fps=30[v$i];"
  # 12 ms fades avoid clicks at the joins
  D=$(awk -v s="$s" -v e="$e" -v sp="$sp" 'BEGIN{printf "%.4f",(e-s)/sp-0.012}')
  A+="[0:a]atrim=${s}:${e},asetpts=PTS-STARTPTS,aresample=48000,atempo=${sp},afade=t=in:d=0.012,afade=t=out:st=${D}:d=0.012[a$i];"
  CAT+="[v$i][a$i]"
done
GRAPH="${V}${A}${CAT}concat=n=${#SEGS[@]}:v=1:a=1[v][araw]"

# pass 1: measure loudness
M=$(ffmpeg -nostdin -hide_banner -i "$IN" -filter_complex "${GRAPH};[araw]loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[a]" \
    -map "[v]" -map "[a]" -f null - 2>&1 | sed -n '/^{/,/^}/p')
g() { echo "$M" | python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
LN="loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true"

# pass 2: encode
ffmpeg -nostdin -hide_banner -y -i "$IN" -filter_complex "${GRAPH};[araw]${LN},aresample=48000[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUT"
