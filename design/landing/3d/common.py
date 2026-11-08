"""TrendCheck 첫 화면 3D 장면 공통 도구.

blender -b -P sN.py -- [preview]
preview 를 주면 EEVEE 로 작게, 안 주면 Cycles 로 크게 렌더한다.
"""
import bpy, math, os, sys, random
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PREVIEW = 'preview' in ARGS
PORTRAIT = 'portrait' in ARGS  # 폰용 세로 영상
STILL = next((int(a.split('=')[1]) for a in ARGS if a.startswith('still=')), None)
ROOT = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(ROOT, 'tex')
FPS = 24
FRAMES = 130  # 5.4초. 장면 하나가 5.2초 떠 있으므로 그보다 조금 길게


def hexlin(h, a=1.0):
    """#rrggbb 를 Blender 가 쓰는 선형 색으로."""
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), a)


# V9 TrendCheck 토큰
COL = {
    'night': '#1b1a18', 'night3': '#33312d', 'paper': '#f7f7f4', 'strong': '#e6e5e0',
    'pri': '#f54e00', 'collect': '#dfa88f', 'search': '#9fc9a2', 'analyze': '#9fbbe0',
    'verify': '#c0a8dd', 'verdict': '#c08532', 'ok': '#1f8a65', 'hold': '#cfcdc4', 'err': '#cf2d56',
}


def setup(name, frames=FRAMES):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, frames
    sc.render.fps = FPS
    if PREVIEW:
        sc.render.resolution_x, sc.render.resolution_y = (540, 960) if PORTRAIT else (960, 540)
        sc.render.engine = 'BLENDER_EEVEE'
        try:
            sc.eevee.taa_render_samples = 32
            sc.eevee.use_raytracing = True
        except Exception:
            pass
    else:
        sc.render.resolution_x, sc.render.resolution_y = (720, 1280) if PORTRAIT else (1600, 900)
        sc.render.engine = 'CYCLES'
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = 'GPU'
        sc.cycles.samples = 48
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.adaptive_threshold = 0.03
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 6
        sc.cycles.diffuse_bounces = 2
        sc.cycles.glossy_bounces = 3
        sc.cycles.transmission_bounces = 6
        sc.render.use_persistent_data = True
    sc.render.resolution_percentage = 100
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Punchy'
    except Exception:
        pass
    sc.render.image_settings.file_format = 'PNG'
    out = os.path.join(ROOT, 'out', name + ('_m' if PORTRAIT else '') + ('_pre' if PREVIEW else ''))
    os.makedirs(out, exist_ok=True)
    sc.render.filepath = os.path.join(out, 'f_')

    w = bpy.data.worlds.new('W')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = hexlin('#141311')
    bg.inputs[1].default_value = 1.0
    return sc


def camera(loc, target, lens=50, fstop=None, focus=None):
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.data.lens = lens
    cam.location = loc
    aim(cam, target)
    if fstop:
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.focus_distance = focus or (Vector(loc) - Vector(target)).length
    return cam


def aim(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def area_light(loc, target, energy, size, color='#ffffff', hide_reflect=True):
    l = bpy.data.objects.new('L', bpy.data.lights.new('L', 'AREA'))
    bpy.context.scene.collection.objects.link(l)
    l.location = loc
    l.data.energy = energy
    l.data.size = size
    l.data.color = hexlin(color)[:3]
    aim(l, target)
    # 조명 패널이 바닥이나 유리에 사각형으로 비치지 않게
    for attr in (('visible_glossy', 'visible_camera', 'visible_transmission') if hide_reflect else ('visible_camera',)):
        try:
            setattr(l, attr, False)
        except Exception:
            pass
    return l


def point_light(loc, energy, color, radius=0.2):
    l = bpy.data.objects.new('P', bpy.data.lights.new('P', 'POINT'))
    bpy.context.scene.collection.objects.link(l)
    l.location = loc
    l.data.energy = energy
    l.data.color = hexlin(color)[:3]
    l.data.shadow_soft_size = radius
    return l


def _bsdf(m):
    return m.node_tree.nodes['Principled BSDF']


def mat_principled(name, color, rough=0.4, metal=0.0, coat=0.0, trans=0.0, ior=1.45, emit=None, emit_str=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = _bsdf(m)
    b.inputs['Base Color'].default_value = hexlin(color)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['IOR'].default_value = ior
    b.inputs['Transmission Weight'].default_value = trans
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Alpha'].default_value = alpha
    if emit:
        b.inputs['Emission Color'].default_value = hexlin(emit)
        b.inputs['Emission Strength'].default_value = emit_str
    return m


def mat_emit(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes['Principled BSDF'])
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs[0].default_value = hexlin(color)
    e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes['Material Output'].inputs[0])
    return m


def mat_logo(name, png, strength=2.5):
    """흰 로고 PNG 를 빛나는 글자로. 투명한 곳은 완전히 비운다."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes['Principled BSDF'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(os.path.join(TEX, png))
    tex.extension = 'CLIP'
    tex.interpolation = 'Cubic'
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs[0].default_value = hexlin('#f7f7f4')
    em.inputs[1].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(tex.outputs['Alpha'], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes['Material Output'].inputs[0])
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    return m, tex.image.size[:]


def add(obj, mat=None):
    bpy.context.scene.collection.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj


def mesh_obj(name, mesh_fn, mat=None, **kw):
    mesh_fn(**kw)
    o = bpy.context.active_object
    o.name = name
    if mat:
        o.data.materials.append(mat)
    return o


def rounded_box(name, size, bevel, mat=None, segments=6):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    mod = o.modifiers.new('bev', 'BEVEL')
    mod.width = bevel
    mod.segments = segments
    mod.limit_method = 'NONE'
    bpy.ops.object.shade_smooth()
    if mat:
        o.data.materials.append(mat)
    return o


def sphere_mesh(r=1.0, seg=24, ring=12):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=ring)
    o = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    me = o.data
    bpy.data.objects.remove(o)
    return me


def key_loc(o, f, v):
    o.location = v
    o.keyframe_insert('location', frame=f)


def key_scale(o, f, s):
    o.scale = (s, s, s) if isinstance(s, (int, float)) else s
    o.keyframe_insert('scale', frame=f)


def linear_all():
    for a in bpy.data.actions:
        try:
            curves = a.fcurves
        except AttributeError:
            curves = [fc for layer in a.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
        for fc in curves:
            for k in fc.keyframe_points:
                k.interpolation = 'LINEAR'


def ease(t):
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def floor(z=0.0, color='#191816', rough=0.22, size=80):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    o = bpy.context.active_object
    o.name = 'Floor'
    o.data.materials.append(mat_principled('floor', color, rough=rough))
    return o


def render():
    sc = bpy.context.scene
    if STILL:
        sc.frame_set(STILL)
        sc.render.filepath = sc.render.filepath + f'still_{STILL:04d}'
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
