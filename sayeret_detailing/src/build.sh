set -e
cd "$(dirname "$0")"
LN=$(cat ln.txt)
D=15.4
ffmpeg -v error -y -i base_video.mp4 -i logo.png \
 -loop 1 -t $D -i L_hook.png -loop 1 -t $D -i L_cap1.png -loop 1 -t $D -i L_cap2.png -loop 1 -t $D -i L_cap3.png -loop 1 -t $D -i L_cap4.png \
 -loop 1 -t 3.4 -i freeze.png -loop 1 -t 3.4 -i L_endcard.png -i raw.mp4 \
 -filter_complex "
 [0:v]eq=contrast=1.12:saturation=1.22:gamma=0.97,unsharp=5:5:0.7:5:5:0.0,format=yuv420p[v0];
 [2:v]format=rgba[hook];
 [3:v]format=rgba[c1];[4:v]format=rgba[c2];[5:v]format=rgba[c3];[6:v]format=rgba[c4];
 [1:v]scale=140:140:flags=lanczos,format=rgba,colorchannelmixer=aa=0.85[logo];
 [v0][hook]overlay=0:0:enable='lt(t,2.5)'[a1];[a1][c1]overlay=0:0:enable='gte(t,2.5)*lt(t,5)'[a2];[a2][c2]overlay=0:0:enable='gte(t,5)*lt(t,8)'[a3];
 [a3][c3]overlay=0:0:enable='gte(t,8)*lt(t,11)'[a4];[a4][c4]overlay=0:0:enable='gte(t,11)'[a5];
 [a5][logo]overlay=890:50:eof_action=repeat,trim=duration=12.4,setpts=PTS-STARTPTS,fps=30,format=yuv420p[main];
 [7:v]eq=contrast=1.12:saturation=1.22,boxblur=40:4,colorchannelmixer=rr=0.6:gg=0.6:bb=0.6,format=rgba[ecbg];
 [ecbg][8:v]overlay=0:0,fps=30,format=yuv420p[endcard];
 [main][endcard]xfade=transition=fade:duration=0.3:offset=12.1,format=yuv420p[vout];
 [9:a]loudnorm=I=-14:TP=-1.5:LRA=11:$LN:linear=true,afade=t=out:st=11.9:d=0.5,apad=whole_dur=$D,aresample=48000[aout]" \
 -map "[vout]" -map "[aout]" -t $D -r 30 -c:v libx264 -preset slow -crf 17 -profile:v high -pix_fmt yuv420p -movflags +faststart \
 -c:a aac -b:a 192k -ar 48000 sayeret_detailing_tiktok.mp4
ffmpeg -v error -y -ss 1 -i sayeret_detailing_tiktok.mp4 -frames:v 1 -q:v 2 sayeret_detailing_cover.jpg
