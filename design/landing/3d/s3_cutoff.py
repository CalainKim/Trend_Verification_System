"""03 누수 차단: 시점 왼쪽 막대만 차례로 솟고, 유리벽 너머 미래 쪽은 흐리게 가려진다."""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

sc = setup('s3_cutoff')
random.seed(37)
CUT = 1.6

if PORTRAIT:
    tgt = (CUT - 0.3, 0.5, 0.75)
    cam = camera((-2.4, -6.6, 2.1), tgt, lens=32, fstop=3.2, focus=7.6)
    cam.keyframe_insert('location', frame=1)
    cam.location = (-1.7, -6.9, 1.8)
else:
    tgt = (0.4, 0.6, 0.7)
    cam = camera((-6.8, -7.6, 3.4), tgt, lens=38, fstop=3.2, focus=10.5)
    cam.keyframe_insert('location', frame=1)
    cam.location = (-5.2, -8.2, 2.9)
cam.keyframe_insert('location', frame=FRAMES)
aim(cam, tgt)

area_light((-6, -5, 8), (0, 0, 0), 1100, 9, '#fff4e8', hide_reflect=False)
area_light((7, 6, 4), (1, 0, 0), 700, 7, COL['analyze'], hide_reflect=False)
floor(0.0, '#161513', rough=0.2)

past = mat_principled('past', COL['strong'], rough=0.42, coat=0.4)
future = mat_principled('future', COL['analyze'], rough=0.38, trans=0.95, ior=1.3)
cols = 34
for r, y in enumerate((0.0, 0.5, 1.0)):
    v = random.uniform(0.4, 0.9)
    for i in range(cols):
        x = -7.0 + i * 0.42
        v = min(2.4, max(0.25, v + random.uniform(-0.28, 0.36)))
        h = v * (1 - r * 0.15)
        is_past = x < CUT
        b = rounded_box(f'b{r}_{i}', (0.32, 0.32, 1.0), 0.04, past if is_past else future, segments=3)
        # 바닥에서 자라도록 원점을 밑면으로 옮긴다
        for vert in b.data.vertices:
            vert.co.z += 0.5
        b.location = (x, y, 0)
        if is_past:
            start = 4 + i * 1.7 + r * 3
            key_scale(b, 1, (1, 1, 0.001))
            key_scale(b, int(start), (1, 1, 0.001))
            for k in range(1, 7):
                key_scale(b, int(start) + k * 2, (1, 1, h * ease(k / 6)))
        else:
            b.scale = (1, 1, h)

# 시점 벽: 서리 낀 유리판
wall = rounded_box('wall', (0.05, 3.2, 3.4), 0.02, mat_principled('wall', '#e9eef7', rough=0.22, trans=1.0, ior=1.2, emit=COL['analyze'], emit_str=0.12), segments=2)
wall.location = (CUT + 0.0, 0.5, 1.7)
# 벽 밑의 주황 띠와 표시 구슬
strip = rounded_box('strip', (0.06, 3.2, 0.03), 0.01, mat_emit('strip', COL['pri'], 6), segments=1)
strip.location = (CUT, 0.5, 0.02)
mark = bpy.data.objects.new('mark', sphere_mesh(0.09, 24, 12))
add(mark, mat_emit('mark', COL['pri'], 10))
mark.location = (CUT, -1.25, 0.09)
point_light((CUT, -1.2, 0.4), 60, COL['pri'], 0.2)

render()
