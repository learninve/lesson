#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
T=18.0; COLD_S=11.1; COLD_D=1.3; MAIN_D=14.4667
FREEZE=$(awk -v t=$T -v c=$COLD_D -v m=$MAIN_D 'BEGIN{printf "%.4f",t-c-m}')
GRADE="eq=contrast=1.05:saturation=1.1,unsharp=5:5:0.4:5:5:0.0"
# cold open: slow 7% zoom-in (single lanczos resample from 720x1280), real source frames, no spatial crop beyond the zoom
V="[0:v]trim=${COLD_S}:$(awk -v a=$COLD_S -v b=$COLD_D 'BEGIN{print a+b}'),setpts=PTS-STARTPTS,fps=30,scale=w='1080*(1+0.07*t/${COLD_D})':h='1920*(1+0.07*t/${COLD_D})':eval=frame:flags=lanczos,crop=1080:1920,setsar=1[c];"
V+="[0:v]trim=0:${MAIN_D},setpts=PTS-STARTPTS,fps=30,scale=1080:1920:flags=lanczos,setsar=1[m];"
V+="[c][m]concat=n=2:v=1:a=0,${GRADE},tpad=stop_mode=clone:stop_duration=${FREEZE}[vb];"
# overlays: PNG sequence with alpha
V+="[1:v]format=rgba[ov];[vb]format=yuv420p[vb2];[vb2][ov]overlay=0:0:format=auto:shortest=1,fade=t=out:st=$(awk -v t=$T 'BEGIN{print t-0.6}'):d=0.6,format=yuv420p[v]"
A="[0:a]atrim=${COLD_S}:$(awk -v a=$COLD_S -v b=$COLD_D 'BEGIN{print a+b}'),asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.01,afade=t=out:st=1.29:d=0.01[ac];"
A+="[0:a]atrim=0:${MAIN_D},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.01[am];"
A+="[ac][am]concat=n=2:v=0:a=1,apad=whole_dur=${T},atrim=0:${T},highpass=f=90"
echo "FREEZE=$FREEZE"
IN=(-framerate 30 -i seq/o_%04d.png)
# pass 1
M=$(ffmpeg -nostdin -hide_banner -i src.mp4 "${IN[@]}" -filter_complex "${V};${A},loudnorm=I=-15:TP=-1.5:LRA=11:print_format=json[a]" -map "[v]" -map "[a]" -t $T -f null - 2>&1 | sed -n '/^{/,/^}/p')
g(){ echo "$M" | python3 -I -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
LN="loudnorm=I=-15:TP=-1.5:LRA=11:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true"
echo "$LN"
ffmpeg -nostdin -hide_banner -y -i src.mp4 "${IN[@]}" -filter_complex "${V};${A},${LN},aresample=48000,volume=${GAIN:-1.0}dB,alimiter=limit=0.84:attack=3:release=60:level=disabled,afade=t=out:st=$(awk -v t=$T 'BEGIN{print t-1}'):d=1[a]" \
  -map "[v]" -map "[a]" -t $T -r 30 -c:v libx264 -crf 19 -preset slow -profile:v high -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart colortech_reel.mp4
