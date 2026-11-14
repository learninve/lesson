#!/usr/bin/env bash
# Step 1 for the Kolortek plastering (shpachtel) clip: 1080x1920 upscale, light grade, -14 LUFS. No cuts.
# usage: ./edit_shpachtel.sh raw.mp4 remotion/public/shpachtel_edit.mp4
set -euo pipefail
IN=${1:?input}; OUT=${2:?output}
VF="scale=1080:1920:flags=lanczos,eq=contrast=1.06:saturation=1.10,unsharp=5:5:0.6,setsar=1,fps=30"
M=$(ffmpeg -nostdin -hide_banner -i "$IN" -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
g() { echo "$M" | python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
LN="loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true"
ffmpeg -nostdin -hide_banner -loglevel error -y -i "$IN" -vf "$VF" -af "${LN},aresample=48000" \
  -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUT"
