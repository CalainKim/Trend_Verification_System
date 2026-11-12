"""02 판별: 들쭉날쭉한 회색 리본들 사이로 주황빛 관 하나가 꾸준히 솟는다."""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

sc = setup('s2_detect')
random.seed(23)

cam = camera((-2.2, -9.4, 0.9), (0.2, 2.5, 0.35), lens=35, fstop=2.8, focus=9.6)
cam.keyframe_insert('location', frame=1)
cam.location = (1.4, -8.8, 0.75)
cam.keyframe_insert('location', frame=FRAMES)

area_light((-5, -4, 6), (0, 2, 0), 700, 8, '#fff4e8')
area_light((6, 10, 3), (0, 2, 0), 600, 8, COL['analyze'])
floor(-3.2 if PORTRAIT else -1.6, '#151412', rough=0.18)


def ribbon(name, pts, depth, mat):
    """점들을 이어 두께 있는 리본(추세선)을 만든다."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = depth
    cu.bevel_resolution = 4
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, v in zip(sp.points, pts):
        p.co = (v[0], v[1], v[2], 1)
    o = bpy.data.objects.new(name, cu)
    sc.collection.objects.link(o)
    cu.materials.append(mat)
    return o, cu


# 잡음 리본: 뾰족하게 튀었다 금방 꺼지는 모양
grey_near = mat_principled('grey', '#cfcdc4', rough=0.45, emit='#cfcdc4', emit_str=0.03)
grey_far = mat_principled('grey_far', '#807d72', rough=0.5)
for i in range(30):
    y = random.uniform(-1.5, 12)
    base = random.uniform(-2.6, 2.8) if PORTRAIT else random.uniform(-1.2, 1.6)
    amp = random.uniform(0.05, 0.22)
    f1, ph = random.uniform(0.3, 0.9), random.random() * 6
    spikes = [(random.uniform(-9, 9), random.uniform(0.6, 2.2) * (1.6 if PORTRAIT else 1)) for _ in range(random.randint(1, 3))]
    pts = []
    for k in range(441):
        x = -11 + k * 22 / 440
        z = base + math.sin(x * f1 + ph) * amp + math.sin(x * 2.3 + ph * 2) * amp * 0.4
        for sx, sh in spikes:
            d = x - sx
            z += sh * math.exp(-d * d * 6) if d > 0 else sh * math.exp(-d * d * 30)
        pts.append((x, y, z))
    ribbon(f'r{i}', pts, 0.012 if y < 5 else 0.018, grey_near if y < 5 else grey_far)

# 진짜 신호: 왼쪽 아래에서 오른쪽 위로 꾸준히 오른다
sig = []
for k in range(161):
    u = k / 160
    if PORTRAIT:
        x = -3.0 + u * 6.0
        z = -2.9 + 5.6 * u ** 1.7 + math.sin(u * 20) * 0.04
    else:
        x = -7.5 + u * 15
        z = -1.25 + 3.2 * u ** 1.7 + math.sin(u * 20) * 0.04
    sig.append((x, 0.3, z))
so, scu = ribbon('signal', sig, 0.045, mat_emit('sig', COL['pri'], 4.5))
scu.bevel_factor_mapping_end = 'SEGMENTS'
for f in range(1, FRAMES + 1, 3):
    scu.bevel_factor_end = ease((f - 6) / 92) if f > 6 else 0.0
    scu.keyframe_insert('bevel_factor_end', frame=f)

# 끝을 따라가는 빛 구슬과 조명
tip = bpy.data.objects.new('tip', sphere_mesh(0.11, 32, 16))
add(tip, mat_emit('tip', COL['pri'], 9))
tl = point_light(sig[0], 120, COL['pri'], 0.2)
for f in range(1, FRAMES + 1, 3):
    u = ease((f - 6) / 92) if f > 6 else 0.0
    p = sig[min(160, int(u * 160))]
    for o in (tip, tl):
        key_loc(o, f, p)
    key_scale(tip, f, 0.0 if f <= 6 else 1.0)

render()
