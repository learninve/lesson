#!/bin/bash
set -e; cd "$(dirname "$0")"; AF=$(cat af.txt)
ffmpeg -v error -y -i edit_raw.mkv -loop 1 -t 2.5 -i emoji.png -filter_complex "
[1:v]format=rgba,fade=in:st=0:d=0.2:alpha=1,fade=out:st=2.3:d=0.2:alpha=1[e];
[0:v][e]overlay=x=(W-w)/2:y=590:eof_action=pass[b];
[b]ass=t.ass:fontsdir=fonts[v]" -map "[v]" -map 0:a -af "$AF,aresample=48000" -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -movflags +faststart ../colortech_reel_v1.mp4
