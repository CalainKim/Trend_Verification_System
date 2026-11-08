#!/bin/zsh
# 가로 렌더가 끝나면 폰용 세로 영상을 이어서 렌더한다
cd "${0:A:h}"
B=/Applications/Blender.app/Contents/MacOS/Blender
until grep -q "ALL DONE" render_all.log 2>/dev/null; do sleep 30; done
mkdir -p video/m
for s in s1_collect s2_detect s3_cutoff s4_verdict; do
  echo "[$(date +%H:%M:%S)] start $s (portrait)"
  $B -b -P $s.py -- portrait > log_${s}_m.txt 2>&1
  echo "[$(date +%H:%M:%S)] rendered $s ($(ls out/${s}_m/f_0*.png 2>/dev/null | wc -l | tr -d ' ') frames)"
  ffmpeg -y -loglevel error -framerate 24 -i out/${s}_m/f_%04d.png -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p -movflags +faststart -an video/m/$s.mp4
  ffmpeg -y -loglevel error -i out/${s}_m/f_0001.png -q:v 4 video/m/$s.jpg
  echo "[$(date +%H:%M:%S)] encoded $s $(du -h video/m/$s.mp4 | cut -f1)"
done
echo "[$(date +%H:%M:%S)] MOBILE DONE"
