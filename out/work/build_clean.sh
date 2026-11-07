#!/bin/bash
set -e
cd "$(dirname "$0")"
CB="colorbalance=rm=-0.012:rh=-0.018:bm=0.012:bh=0.022,eq=contrast=1.05:saturation=1.04:gamma=1.0,unsharp=5:5:0.6:5:5:0.0"
# segments: [0,1.5] 1x | [1.5,4.5] 1.4x | [4.5,end] 1x
ffmpeg -v error -y -i stab.mp4 -i src.mp4 -filter_complex "
[0:v]scale=-2:1920:flags=lanczos,crop=1080:1920,$CB,fps=30,split=3[a][b][c];
[a]trim=0:1.5,setpts=PTS-STARTPTS[v1];
[b]trim=1.5:4.5,setpts=(PTS-STARTPTS)/1.4[v2];
[c]trim=4.5:8.1333,setpts=PTS-STARTPTS[v3];
[v1][v2][v3]concat=n=3:v=1:a=0[v];
[1:a]aresample=48000,asplit=3[x][y][z];
[x]atrim=0:1.5,asetpts=PTS-STARTPTS[a1];
[y]atrim=1.5:4.5,asetpts=PTS-STARTPTS,atempo=1.4[a2];
[z]atrim=4.5:8.1333,asetpts=PTS-STARTPTS[a3];
[a1][a2][a3]concat=n=3:v=0:a=1,afftdn=nr=9:nf=-32:tn=0,afade=t=in:d=0.03[a]
" -map "[v]" -map "[a]" -c:v libx264 -crf 10 -preset medium -pix_fmt yuv420p -c:a pcm_s16le edit_raw.mkv
ffprobe -v error -show_entries format=duration -of csv=p=0 edit_raw.mkv
# loudnorm pass 1
ffmpeg -hide_banner -y -i edit_raw.mkv -vn -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p' > ln.json
cat ln.json
