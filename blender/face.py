"""Face parts: eyes with two catchlights, lids, brows, nose, mouth cavity, tongue, fangs.

Expressions live as shape keys. Every face mesh carries the same key names,
all driven by one custom property per expression on the rig (see rig.py).
"""
import math
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion
import spec as S
from bl_util import mesh_object, principled, hex_lin, new_material, link

EXPRESSIONS = ['happy', 'surprise', 'thinking', 'confused', 'determined', 'mischief', 'laughing',
               'blink', 'eyes_bulging', 'cheeks_swollen']

GAZE_TARGET = Vector((0.0, -2.2, 0.80))


def eye_center(side):
    s = 1 if side == 'L' else -1
    return Vector((S.EYE_C[0] * s, S.EYE_C[1], S.EYE_C[2]))


def eye_basis(side, gaze_offset=(0.0, 0.0)):
    """Rotation whose columns are eye-local x (right on screen), y (up), z (gaze)."""
    c = eye_center(side)
    z = (GAZE_TARGET - c).normalized()
    q = Quaternion(Vector((0, 0, 1)), gaze_offset[0]) @ Quaternion(Vector((1, 0, 0)), gaze_offset[1])
    up = Vector((0, 0, 1))
    x = up.cross(z).normalized()  # screen-right for a viewer in front
    y = z.cross(x).normalized()
    M = Matrix((x, y, z)).transposed()
    if gaze_offset != (0.0, 0.0):
        # yaw about world Z, pitch about eye x
        M = Matrix.Rotation(gaze_offset[0], 3, 'Z') @ Matrix.Rotation(gaze_offset[1], 3, x) @ M
    return M


# ------------------------------------------------------------------ materials
def eye_material():
    m, nt = new_material('eye')
    N = nt.nodes
    L = nt.links
    out = N.new('ShaderNodeOutputMaterial')
    bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Roughness'].default_value = 0.35
    bs.inputs['Coat Weight'].default_value = 1.0
    bs.inputs['Coat Roughness'].default_value = 0.03
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Object'], sep.inputs[0])
    z = sep.outputs['Z']
    y = sep.outputs['Y']

    def ramp(socket, a, b):
        mr = N.new('ShaderNodeMapRange')
        mr.interpolation_type = 'SMOOTHSTEP'
        mr.inputs['From Min'].default_value = a
        mr.inputs['From Max'].default_value = b
        L.new(socket, mr.inputs['Value'])
        return mr.outputs['Result']

    iris_m = ramp(z, math.cos(math.radians(36.0)), math.cos(math.radians(34.6)))
    rim_m = ramp(z, math.cos(math.radians(29.5)), math.cos(math.radians(33.0)))  # 1 inside rim
    pupil_m = ramp(z, math.cos(math.radians(19.5)), math.cos(math.radians(18.2)))
    low_m = ramp(y, 0.05, -0.45)  # lighter amber toward the bottom of the iris

    def mix(fac, a, b):
        mx = N.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        L.new(fac, mx.inputs['Factor'])
        for sock, val in ((mx.inputs[6], a), (mx.inputs[7], b)):
            if isinstance(val, tuple):
                sock.default_value = val
            else:
                L.new(val, sock)
        return mx.outputs[2]

    iris_col = mix(low_m, hex_lin(S.PALETTE['iris']), hex_lin('#C98A3E'))
    iris_col = mix(rim_m, hex_lin(S.PALETTE['iris_rim']), iris_col)
    c = mix(iris_m, hex_lin(S.PALETTE['eye_white']), iris_col)
    c = mix(pupil_m, c, hex_lin('#050303'))
    L.new(c, bs.inputs['Base Color'])
    L.new(bs.outputs[0], out.inputs[0])
    return m


def emission_material(name, strength=6.0):
    m, nt = new_material(name)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = strength
    em.inputs['Color'].default_value = (1, 1, 1, 1)
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


# ------------------------------------------------------------------ geometry
def uv_sphere(name, radius, segs=48, rings=32, coll=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=radius)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    return link(ob, coll)


def build_eye(side, coll):
    c = eye_center(side)
    M = eye_basis(side)
    ob = uv_sphere('eye.' + side, 1.0, 64, 40, coll)
    ob.matrix_world = Matrix.Translation(c) @ M.to_4x4() @ Matrix.Scale(S.EYE_R, 4)
    ob.data.materials.append(bpy.data.materials.get('eye') or eye_material())
    # two catchlights: a big one up-right of the pupil, a small one down-left
    hl = bpy.data.materials.get('catchlight') or emission_material('catchlight')
    lights = []
    for (ax, ay, r) in ((0.30, 0.30, 0.13), (-0.26, -0.24, 0.06)):
        d = Vector((ax, ay, 1.0)).normalized()
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, segments=20, radius=r)
        me = bpy.data.meshes.new('catch')
        bm.to_mesh(me)
        bm.free()
        hob = link(bpy.data.objects.new('catchlight.%s.%d' % (side, len(lights)), me), coll)
        rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        hob.parent = ob
        hob.matrix_parent_inverse = Matrix.Identity(4)
        hob.matrix_basis = Matrix.Translation(d * 1.012) @ rot
        me.materials.append(hl)
        hob.visible_shadow = False
        lights.append(hob)
    return ob, lights


def lid_mesh(name, side, upper, coll, radius=0.0448, edge_deg=52.0, corner_drop=22.0, span=165.0):
    """Partial spherical shell around the eye. Upper lid covers phi in [edge, edge+span]
    measured from the gaze axis toward +y (eye-local), lower lid mirrors downward.
    The lid edge dips toward the corners (corner_drop) so the opening is oval."""
    c = eye_center(side)
    M = eye_basis(side)
    nu, nv = 44, 28
    verts, faces = [], []
    sgn = 1.0 if upper else -1.0
    for i in range(nv + 1):
        a = i / nv
        for j in range(nu + 1):
            psi = math.radians(-82 + 164 * j / nu)  # across the eye (about local y)
            edge = math.radians(edge_deg) - math.radians(corner_drop) * (psi / math.radians(82)) ** 2
            phi = edge + math.radians(span) * a
            r = radius + 0.0009 * a  # slightly larger away from the edge so it tucks into the socket
            # direction: rotate gaze (0,0,1) toward +y by phi (upper) or -y (lower), then across by psi
            dy = math.sin(phi) * sgn
            dz = math.cos(phi)
            v = Vector((math.sin(psi) * 1.0, dy * math.cos(psi), dz * math.cos(psi)))
            verts.append(c + M @ (v * r))
    for i in range(nv):
        for j in range(nu):
            a = i * (nu + 1) + j
            f = (a, a + 1, a + nu + 2, a + nu + 1)
            faces.append(f if upper else f[::-1])
    ob = mesh_object(name, verts, faces, coll)
    # lash line: first two rows along the edge
    me = ob.data
    lash = me.color_attributes.new('lid', 'BYTE_COLOR', 'POINT')
    cols = np.ones((len(verts), 4))
    for i in range(nv + 1):
        for j in range(nu + 1):
            k = i * (nu + 1) + j
            t = 1.0 if i <= (2 if upper else 1) else 0.0
            cols[k, :3] = (0, 0, 0) if t else (1, 1, 1)
    lash.data.foreach_set('color', cols.ravel())
    ob['lid_params'] = (edge_deg, corner_drop, span, radius)
    return ob


def lid_material(fur_hex, name):
    m, nt = new_material(name)
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial')
    bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Roughness'].default_value = 0.7
    bs.inputs['Sheen Weight'].default_value = 0.5
    at = N.new('ShaderNodeAttribute')
    at.attribute_name = 'lid'
    mx = N.new('ShaderNodeMix')
    mx.data_type = 'RGBA'
    L.new(at.outputs['Fac'], mx.inputs['Factor'])
    mx.inputs[6].default_value = hex_lin('#2A140C')
    mx.inputs[7].default_value = hex_lin(fur_hex)
    L.new(mx.outputs[2], bs.inputs['Base Color'])
    L.new(bs.outputs[0], out.inputs[0])
    return m


def rotate_about(co, center, axis, ang):
    R = Matrix.Rotation(ang, 3, axis)
    return [center + R @ (Vector(p) - center) for p in co]


def lid_shape(ob, side, upper, d_edge_deg=0.0, tilt_deg=0.0, scale=1.0):
    """Rotate the lid about the eye's local x axis (open/close) and gaze axis (tilt)."""
    c = eye_center(side)
    M = eye_basis(side)
    x_ax = M.col[0]
    z_ax = M.col[2]
    co = [v.co.copy() for v in ob.data.vertices]
    co = rotate_about(co, c, x_ax, math.radians(d_edge_deg) * (1 if upper else -1))
    if tilt_deg:
        s = 1 if side == 'L' else -1
        co = rotate_about(co, c, z_ax, math.radians(tilt_deg) * s)
    if scale != 1.0:
        co = [c + (p - c) * scale for p in co]
    return co


# ------------------------------------------------------------------ brows
def brow_curve(side, raise_=0.0, inner_drop=0.0, arch=0.0, shift_x=0.0):
    s = 1 if side == 'L' else -1
    pts = []
    for i in range(17):
        t = i / 16
        x = 0.036 + (0.121 - 0.036) * t + shift_x
        # arch peaks ~45% along; inner end lower than outer (sheet)
        z = 0.832 + 0.022 * math.sin(math.pi * min(1.0, t / 0.9)) * (1 + arch) + 0.008 * t
        z += raise_ - inner_drop * (1 - t) ** 1.5
        pts.append((x * s, z))
    return pts


def project_to_surface(bvh, pts_xz, lift):
    """Ray-cast from the front onto the head; returns surface points + normals."""
    out = []
    for (x, z) in pts_xz:
        hit = bvh.ray_cast(Vector((x, -0.6, z)), Vector((0, 1, 0)))
        if hit[0] is None:
            hit = bvh.find_nearest(Vector((x, -0.15, z)))
        p, n = hit[0], hit[1]
        out.append((p + n * lift, n))
    return out


def strip_from_curve(surf_pts, width_fn, thick):
    """Build a flat tapered ribbon (closed, with thickness) along surface points."""
    verts, faces = [], []
    n = len(surf_pts)
    for i, (p, nrm) in enumerate(surf_pts):
        t = i / (n - 1)
        a = surf_pts[min(i + 1, n - 1)][0] - surf_pts[max(i - 1, 0)][0]
        tan = a.normalized()
        side = nrm.cross(tan).normalized()
        w = width_fn(t)
        for (sx, sy) in ((-1, 0), (1, 0), (1, 1), (-1, 1)):
            verts.append(p + side * (w * 0.5 * sx) + nrm * (thick * sy))
    for i in range(n - 1):
        for k in range(4):
            a = i * 4 + k
            b = i * 4 + (k + 1) % 4
            faces.append((a, b, b + 4, a + 4))
    faces.append((0, 3, 2, 1))
    faces.append(((n - 1) * 4, (n - 1) * 4 + 1, (n - 1) * 4 + 2, (n - 1) * 4 + 3))
    return verts, faces


def brow_width(t):
    return 0.012 * math.sin(math.pi * (0.08 + 0.84 * t)) ** 0.6 + 0.002


def build_brow(side, bvh, coll, **kw):
    pts = project_to_surface(bvh, brow_curve(side, **kw), 0.0015)
    v, f = strip_from_curve(pts, brow_width, 0.0035)
    return mesh_object('brow.' + side, v, f, coll), (lambda **k: strip_from_curve(
        project_to_surface(bvh, brow_curve(side, **k), 0.0015), brow_width, 0.0035)[0])


# ------------------------------------------------------------------ nose
def build_nose(coll):
    ob = uv_sphere('nose', 1.0, 40, 28, coll)
    me = ob.data
    for v in me.vertices:
        x, y, z = v.co
        taper = 0.58 + 0.42 * (z + 1) / 2  # narrower at the bottom -> rounded inverted triangle
        flat = 1.0 - 0.25 * max(0.0, -y)   # flatter at the back
        v.co = Vector((x * 0.031 * taper, y * 0.022 * flat, z * 0.022 + 0.004 * (1 - x * x)))
    ob.location = Vector(S.NOSE_C)
    ob.rotation_euler = (math.radians(-12), 0, 0)
    m = principled('nose', S.PALETTE['nose'], rough=0.32, coat=0.6)
    me.materials.append(m)
    return ob
