#!/bin/bash
# usage: build.sh NAME HOOK_START
cd /home/user/lesson
N=B; K=$1; H=$2; HE=$(python3 -c "print($H+1.05)")
ffmpeg -v error -y -i work/up1.mp4 -i steam.mp4 -filter_complex "
[0:v]trim=$H:$HE,setpts=(PTS-STARTPTS)/0.7,fps=30[v1];
[1:a]atrim=$H:$HE,asetpts=PTS-STARTPTS,atempo=0.7[a1];
[0:v]trim=2:7.5,setpts=PTS-STARTPTS,fps=30[v2];
[1:a]atrim=2:7.5,asetpts=PTS-STARTPTS[a2];
[0:v]trim=0:2,setpts=PTS-STARTPTS,fps=30[v3];
[1:a]atrim=0:2,asetpts=PTS-STARTPTS[a3];
[v1][a1][v2][a2][v3][a3]concat=n=3:v=1:a=1[v][a]" -map "[v]" -map "[a]" -c:v libx264 -crf 14 -preset veryfast -pix_fmt yuv420p -c:a aac work/cat_$K.mp4
ffmpeg -v error -y -i work/cat_$K.mp4 -loop 1 -i work/fire.png -filter_complex "
[0:v]subtitles=work/t_$K.ass:fontsdir=/usr/share/fonts/truetype/dejavu[s];
[s][1:v]overlay=(W-w)/2:H*0.34:enable='between(t,0,2.2)'[o]" -map "[o]" -map 0:a -t 9 -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart out/steam_$K.mp4
