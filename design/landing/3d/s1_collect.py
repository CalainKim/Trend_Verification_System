"""01 수집: 채널 로고 타일에서 빛 구슬이 흘러나와 가운데 주황 코어로 모인다."""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

sc = setup('s1_collect')
random.seed(11)

cam = camera((0, -15.2, 0.35), (0, 0, 0), lens=50, fstop=2.4, focus=15.0)
cam.keyframe_insert('location', frame=1)
cam.location = (0, -13.9, 0.15)
cam.keyframe_insert('location', frame=FRAMES)

area_light((-6, -7, 7), (0, 0, 0), 900, 7, '#fff4e8', hide_reflect=False)
area_light((6, 6, 4), (0, 0, 0), 500, 6, COL['analyze'], hide_reflect=False)
area_light((0, -8, -5), (0, 0, 0), 120, 8, '#ffffff', hide_reflect=False)

# 타일: 채널마다 하나. (이름, 질감, 위치, 크기 배율, 점 색, 점 비중)
SRC_WIDE = [
    ('29cm',   '29cm.png',      (-3.35, 0.0,  1.80), 0.85,  COL['collect'], 1.3),
    ('kolon',  'kolonmall.png', ( 3.30, 0.0,  1.90), 0.85,  COL['verify'],  1.3),
    ('hiver',  'hiver.png',     ( 3.30, 0.0, -1.85), 0.85,  COL['analyze'], 1.3),
    ('naver',  'naver.png',     (-3.30, 0.0, -1.90), 0.75, COL['search'],  0.8),
    ('google', 'google.png',    ( 0.00, 4.0,  1.80), 0.7, COL['pri'],     0.6),
]
# 세로: 가운데 문구를 피해 위아래로 엇갈려 쌓는다
SRC_TALL = [
    ('29cm',   '29cm.png',      (-0.80, 0.0,  3.70), 0.8,  COL['collect'], 1.3),
    ('kolon',  'kolonmall.png', ( 0.85, 0.0,  2.35), 0.8,  COL['verify'],  1.3),
    ('hiver',  'hiver.png',     (-0.85, 0.0, -2.35), 0.8,  COL['analyze'], 1.3),
    ('naver',  'naver.png',     ( 0.85, 0.0, -3.70), 0.72, COL['search'],  0.8),
    ('google', 'google.png',    ( 1.30, 2.5,  4.10), 0.62, COL['pri'],     0.6),
]
SRC = SRC_TALL if PORTRAIT else SRC_WIDE
tile_mat = mat_principled('tile', '#2b2a26', rough=0.28, coat=0.9)
tiles = []
for name, png, pos, k, col, _ in SRC:
    t = rounded_box('tile_' + name, (2.5 * k, 0.32 * k, 1.0 * k), 0.12 * k, tile_mat)
    t.location = pos
    lm, (iw, ih) = mat_logo('logo_' + name, png, 1.6)
    aspect = iw / ih
    lw = min(1.75 * k, 0.42 * k * aspect)
    lh = lw / aspect
    bpy.ops.mesh.primitive_plane_add(size=1)
    lp = bpy.context.active_object
    lp.name = 'logo_' + name
    lp.scale = (lw, lh, 1)
    lp.rotation_euler = (math.radians(90), 0, 0)
    lp.data.materials.append(lm)
    lp.parent = t
    lp.location = (0.12 * k, -0.165 * k - 0.004, 0)
    dot = bpy.data.objects.new('dot_' + name, sphere_mesh(0.065 * k, 16, 8))
    add(dot, mat_emit('dotm_' + name, col, 4))
    dot.parent = t
    dot.location = (-lw / 2 - 0.12 * k + 0.12 * k - 0.18 * k, -0.17 * k, 0)
    # 천천히 흔들린다
    ph = random.random() * 6.28
    for f in range(1, FRAMES + 1, 10):
        a = f / FRAMES * 6.28 + ph
        t.rotation_euler = (math.radians(6 * math.sin(a)), 0, math.radians(9 * math.sin(a * 0.7 + 1)))
        t.keyframe_insert('rotation_euler', frame=f)
    tiles.append(t)

# 코어: 유리 구 속의 주황 빛
core_glass = bpy.data.objects.new('core_glass', sphere_mesh(0.62, 64, 32))
add(core_glass, mat_principled('glass', '#ffffff', rough=0.04, trans=1.0, ior=1.45))
core = bpy.data.objects.new('core', sphere_mesh(0.27, 32, 16))
add(core, mat_emit('core_e', COL['pri'], 2.2))
point_light((0, 0, 0), 250, COL['pri'], 0.3)
for f in range(1, FRAMES + 1, 6):
    key_scale(core, f, 1 + 0.12 * math.sin(f / 9))

# 빛 구슬: 오브젝트 색을 읽는 발광 재질 하나를 같이 쓴다
pm = bpy.data.materials.new('particle')
pm.use_nodes = True
nt = pm.node_tree
nt.nodes.remove(nt.nodes['Principled BSDF'])
oi = nt.nodes.new('ShaderNodeObjectInfo')
em = nt.nodes.new('ShaderNodeEmission')
em.inputs[1].default_value = 2.2
nt.links.new(oi.outputs['Color'], em.inputs[0])
nt.links.new(em.outputs[0], nt.nodes['Material Output'].inputs[0])
pmesh = sphere_mesh(1.0, 12, 6)
pmesh.materials.append(pm)

weights = [s[5] for s in SRC]
pri = hexlin(COL['pri'])
N = 300
for i in range(N):
    s = random.choices(range(len(SRC)), weights)[0]
    src = Vector(SRC[s][2])
    scol = hexlin(SRC[s][4])
    o = bpy.data.objects.new(f'p{i}', pmesh)
    sc.collection.objects.link(o)
    size = random.uniform(0.018, 0.048)
    born = int(3 + random.random() * 40)
    dur = int(32 + random.random() * 34)
    start = src + Vector((random.uniform(-0.6, 0.6), random.uniform(-0.3, 0.3), random.uniform(-0.25, 0.25)))
    # 도착점: 코어 둘레의 궤도
    orb_r = random.uniform(0.75, 1.6)
    orb_a = random.random() * 6.28
    orb_tilt = random.uniform(-0.6, 0.6)
    orb_sp = random.uniform(0.04, 0.09) * random.choice([-1, 1])

    def orbit(f):
        a = orb_a + f * orb_sp
        return Vector((math.cos(a) * orb_r, math.sin(a) * orb_r * 0.9, math.sin(a) * orb_r * orb_tilt))

    end_f = born + dur
    end = orbit(end_f)
    mid = (start + end) / 2
    perp = Vector((-(end - start).z, 0, (end - start).x)).normalized()
    ctrl = mid + perp * random.uniform(-1.6, 1.6) + Vector((0, random.uniform(-2.2, 2.2), 0))

    o.scale = (0, 0, 0)
    o.location = start
    o.keyframe_insert('scale', frame=1)
    o.keyframe_insert('location', frame=1)
    o.keyframe_insert('scale', frame=max(1, born - 1))
    for f in range(born, FRAMES + 2, 2):
        if f <= end_f:
            u = ease((f - born) / dur)
            p = (1 - u) ** 2 * start + 2 * (1 - u) * u * ctrl + u * u * end
            mix = max(0.0, (u - 0.55) / 0.45)
        else:
            p = orbit(f)
            mix = 1.0
        o.location = p
        o.keyframe_insert('location', frame=f)
        sz = size * (1.0 if f > born + 3 else (f - born + 1) / 4)
        o.scale = (sz, sz, sz)
        o.keyframe_insert('scale', frame=f)
        o.color = tuple(scol[j] * (1 - mix) + pri[j] * mix for j in range(3)) + (1,)
        o.keyframe_insert('color', frame=f)

linear_all()
render()
