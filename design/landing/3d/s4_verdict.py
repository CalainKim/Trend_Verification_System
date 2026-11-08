"""04 판정: 앞에서 굴러온 구슬이 확정, 보류, 기각 세 고리로 갈라져 들어간다."""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

sc = setup('s4_verdict')
random.seed(41)

if PORTRAIT:
    tgt = (0, 2.4, 0)
    cam = camera((0, -6.2, 7.2), tgt, lens=34, fstop=3.2, focus=11.0)
    cam.keyframe_insert('location', frame=1)
    cam.location = (0.3, -5.6, 6.6)
else:
    tgt = (0, 1.3, 0)
    cam = camera((0, -7.6, 4.2), tgt, lens=36, fstop=3.2, focus=9.0)
    cam.keyframe_insert('location', frame=1)
    cam.location = (0.25, -7.0, 3.85)
cam.keyframe_insert('location', frame=FRAMES)
aim(cam, tgt)

area_light((-6, -3, 9), (0, 2, 0), 1000, 9, '#fff4e8')
area_light((6, 8, 5), (0, 2, 0), 500, 8, COL['verify'])
floor(0.0, '#161513', rough=0.2)

RINGS = [((-1.15, 5.6), COL['ok'], 0.45), ((1.2, 3.4), COL['hold'], 0.35), ((-1.0, 1.0), COL['err'], 0.20)] if PORTRAIT else \
        [((-3.3, 3.0), COL['ok'], 0.45), ((0.0, 3.8), COL['hold'], 0.35), ((3.3, 3.0), COL['err'], 0.20)]
for (x, y), col, _ in RINGS:
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0 if PORTRAIT else 1.25, minor_radius=0.07, major_segments=96, minor_segments=16, location=(x, y, 0.06))
    t = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    t.data.materials.append(mat_emit('ring' + col, col, 5))
    point_light((x, y, 0.5), 80, col, 0.4)

ball_mats = {col: mat_principled('ball' + col, col, rough=0.18, coat=0.8, emit=col, emit_str=0.6) for _, col, _ in RINGS}
bmesh = sphere_mesh(1.0, 24, 12)
N = 220
weights = [r[2] for r in RINGS]
for i in range(N):
    k = random.choices(range(3), weights)[0]
    (rx, ry), col, _ = RINGS[k]
    o = bpy.data.objects.new(f'b{i}', bmesh.copy())
    sc.collection.objects.link(o)
    o.data.materials.append(ball_mats[col])
    r = random.uniform(0.06, 0.12)
    born = int(2 + random.random() * 55)
    dur = int(30 + random.random() * 26)
    start = Vector((random.uniform(-3, 3), random.uniform(-3.5, -2.0), r)) if PORTRAIT else Vector((random.uniform(-7, 7), random.uniform(-5.5, -3.5), r))
    a0 = random.random() * 6.28
    rad = random.uniform(0.15, 0.8) if PORTRAIT else random.uniform(0.2, 1.0)
    sp = random.uniform(0.05, 0.1) * (1 if k != 2 else -1)

    def inside(f):
        a = a0 + f * sp
        return Vector((rx + math.cos(a) * rad, ry + math.sin(a) * rad, r))

    end_f = born + dur
    end = inside(end_f)
    ctrl = Vector(((start.x + end.x) / 2 + random.uniform(-1.5, 1.5), (start.y + end.y) / 2, r))
    o.scale = (0, 0, 0)
    o.location = start
    o.keyframe_insert('scale', frame=1)
    o.keyframe_insert('location', frame=1)
    o.keyframe_insert('scale', frame=max(1, born - 1))
    for f in range(born, FRAMES + 2, 2):
        if f <= end_f:
            u = ease((f - born) / dur)
            p = (1 - u) ** 2 * start + 2 * (1 - u) * u * ctrl + u * u * end
        else:
            p = inside(f)
        o.location = p
        o.keyframe_insert('location', frame=f)
        s = r * min(1.0, (f - born + 1) / 4)
        o.scale = (s, s, s)
        o.keyframe_insert('scale', frame=f)

linear_all()
render()
