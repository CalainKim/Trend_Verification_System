#!/bin/zsh
# 네 장면을 Cycles 로 렌더하고 웹용 영상과 포스터로 만든다
cd "${0:A:h}"
B=/Applications/Blender.app/Contents/MacOS/Blender
mkdir -p video
for s in s1_collect s2_detect s3_cutoff s4_verdict; do
  echo "[$(date +%H:%M:%S)] start $s"
  $B -b -P $s.py > log_$s.txt 2>&1
  echo "[$(date +%H:%M:%S)] rendered $s ($(ls out/$s/f_0*.png 2>/dev/null | wc -l | tr -d ' ') frames)"
  ffmpeg -y -loglevel error -framerate 24 -i out/$s/f_%04d.png -c:v libx264 -preset slow -crf 22 -pix_fmt yuv420p -movflags +faststart -an video/$s.mp4
  ffmpeg -y -loglevel error -i out/$s/f_0001.png -q:v 4 video/$s.jpg
  echo "[$(date +%H:%M:%S)] encoded $s $(du -h video/$s.mp4 | cut -f1)"
done
echo "[$(date +%H:%M:%S)] ALL DONE"
