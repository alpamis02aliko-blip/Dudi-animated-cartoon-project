"""Stage 1: Dudi's continuous body mesh, colour map, mouth cavity and facial shape keys."""
import math
import time
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
import spec as S
import sdf
import body as B
from bl_util import (mesh_object, voxel_remesh, verts_np, set_corner_colors, hex_lin, apply_modifiers,
                     principled, vertex_group, link, new_material)

MOUTH_HALF = 0.074


def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def sig(x, w):
    return smooth01(0.5 + x / (2 * w))


def mouth_z(x):
    return S.MOUTH_CENTER_Z + (S.MOUTH_CORNER[2] - S.MOUTH_CENTER_Z) * (np.asarray(x) / 0.08) ** 2


CAVITY_C = (0.0, -0.128, 0.667)
CAVITY_R = (0.046, 0.030, 0.016)


def build_body_mesh(coll, step=0.0045, voxel=0.004):
    t0 = time.time()
    P, axes = sdf.grid(*B.BOUNDS, step)
    P = P.astype(np.float32)
    parts = B.part_fields(P)
    d = B.body_field(P, parts)
    del parts, P
    v, f = sdf.polygonise(d, axes)
    del d
    ob = mesh_object('Dudi_body', v, f, coll)
    voxel_remesh(ob, voxel)
    print('body mesh: %d verts (%.1fs)' % (len(ob.data.vertices), time.time() - t0))
    return ob


def classify(co):
    f = B.part_fields(co)
    names = B.PARTS
    D = np.stack([f[n] for n in names], 1)
    region = np.argmin(D, 1)
    return {n: (region == i) for i, n in enumerate(names)}, f


def ear_local(co, side):
    s = 1.0 if side == 'L' else -1.0
    base = np.array([0.172 * s, 0.112, 0.800])
    tip = np.array([S.EAR_TIP[0] * s, S.EAR_TIP[1], S.EAR_TIP[2]])
    yaw = np.radians(40.0)
    normal = np.array([np.sin(yaw) * s, -np.cos(yaw), 0.0])
    L = float(np.linalg.norm(tip - base))
    o, R = sdf.frame_from(base, tip - base, normal)
    q = (co - o) @ R.T
    u, v, w = q[:, 0], q[:, 1], q[:, 2]
    t = np.clip(u / L, 0, 1)
    w = w - 0.02 * (v / 0.075) ** 2 * (1.0 - 0.5 * t)
    hw = np.minimum(0.075 * np.power(np.clip((1 - t) / 0.55, 0, 1), 0.6), 0.075 * (0.78 + 0.22 * np.clip(t / 0.25, 0, 1))) + 0.003
    return t, v / hw, w


def tail_param(co):
    pts, rr, s = B.tail_centerline()
    best = np.full(len(co), 1e9)
    par = np.zeros(len(co))
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ab = b - a
        tt = np.clip(((co - a) @ ab) / (ab @ ab), 0, 1)
        dd = np.linalg.norm(co - (a + tt[:, None] * ab), axis=1)
        m = dd < best
        best[m] = dd[m]
        par[m] = s[i] + tt[m] * (s[i + 1] - s[i])
    return par


def body_colors(co, reg):
    P = S.PALETTE
    orange = np.array(hex_lin(P['fur'])[:3])
    cream = np.array(hex_lin(P['cream'])[:3])
    dark = np.array(hex_lin(P['ear_tip'])[:3])
    hand = np.array(hex_lin(P['hands'])[:3])
    inner_ear = np.array(hex_lin('#E8CDB0')[:3])
    x, y, z = co.T
    ax = np.abs(x)
    col = np.tile(orange, (len(co), 1))

    # face: cream lower face, muzzle, chin and throat
    ct = np.interp(ax, [0.0, 0.03, 0.077, 0.15, 0.19, 0.25], [0.716, 0.722, 0.735, 0.735, 0.712, 0.69])
    front = sig(0.035 - y, 0.03)
    k_face = sig(ct - z, 0.008) * front
    k_neck = (reg['neck'] | reg['torso']) * sig(-y + 0.01, 0.03)
    k = np.clip(np.maximum(k_face * (reg['head'] | reg['neck']), k_neck), 0, 1)
    col = col * (1 - k[:, None]) + cream * k[:, None]

    # ears: inner cream, dark tips and rims
    for side in 'LR':
        m = reg['ear_' + side]
        if not m.any():
            continue
        t, vn, w = ear_local(co[m], side)
        c = np.tile(orange, (m.sum(), 1))
        frontface = sig(w, 0.004)
        inner = frontface * sig(0.78 - np.abs(vn), 0.08) * sig(0.88 - t, 0.06)
        c = c * (1 - inner[:, None]) + inner_ear * inner[:, None]
        tipk = np.maximum(sig(t - 0.60, 0.05) * (1 - frontface * sig(0.6 - np.abs(vn), 0.1) * sig(0.86 - t, 0.04)),
                          sig(t - 0.86, 0.03))
        rim = frontface * sig(np.abs(vn) - 0.78, 0.06) * sig(t - 0.45, 0.06)
        dk = np.clip(np.maximum(tipk, rim), 0, 1)
        c = c * (1 - dk[:, None]) + dark * dk[:, None]
        col[m] = c

    # tail: long cream tip
    m = reg['tail']
    if m.any():
        s = tail_param(co[m])
        kk = sig(s - S.TAIL_CREAM_FROM, 0.04)
        col[m] = col[m] * (1 - kk[:, None]) + cream * kk[:, None]

    # hands
    for side in 'LR':
        m = reg['hand_' + side]
        col[m] = hand
    return col


def carve_mouth(ob, coll):
    """Cut the smile slit and a cavity behind it (Boolean, exact)."""
    me_bvh = BVHTree.FromPolygons([v.co.copy() for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])
    # cavity
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * CAVITY_R[0], v.co.y * CAVITY_R[1], v.co.z * CAVITY_R[2])) + Vector(CAVITY_C)
    # slit blade along the smile curve
    xs = np.linspace(-MOUTH_HALF, MOUTH_HALF, 41)
    th = 0.0013
    rows = []
    for x in xs:
        zc = float(mouth_z(x))
        hit = me_bvh.ray_cast(Vector((x, -0.5, zc)), Vector((0, 1, 0)))
        ys = hit[0].y if hit[0] is not None else -0.17
        depth = 0.045 if abs(x) < 0.04 else 0.045 - (abs(x) - 0.04) / (MOUTH_HALF - 0.04) * 0.033
        y_in, y_out = ys + depth, ys - 0.03
        rows.append([(x, y_out, zc - th), (x, y_in, zc - th), (x, y_in, zc + th), (x, y_out, zc + th)])
    vb = []
    for r in rows:
        vb.extend([bm.verts.new(Vector(p)) for p in r])
    n = len(rows)
    for i in range(n - 1):
        for k in range(4):
            a, b = i * 4 + k, i * 4 + (k + 1) % 4
            bm.faces.new((vb[a], vb[b], vb[b + 4], vb[a + 4]))
    bm.faces.new((vb[3], vb[2], vb[1], vb[0]))
    e = (n - 1) * 4
    bm.faces.new((vb[e], vb[e + 1], vb[e + 2], vb[e + 3]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('mouth_cutter')
    bm.to_mesh(me)
    bm.free()
    cutter = link(bpy.data.objects.new('mouth_cutter', me), coll)
    mouth_mat = principled('mouth_inside', S.PALETTE['mouth'], rough=0.55)
    cutter.data.materials.append(mouth_mat)
    if not ob.data.materials:
        ob.data.materials.append(bpy.data.materials.get('skin') or principled('skin', S.PALETTE['fur']))
    mod = ob.modifiers.new('mouth', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    mod.material_mode = 'TRANSFER'
    mod.use_self = True
    apply_modifiers(ob)
    bpy.data.objects.remove(cutter)
    return ob


# ------------------------------------------------------------------ facial shape keys (body)
def jaw_offsets(co, open_deg, width=1.0, corner_up=0.0, corner_out=0.0, upper_lift=0.0):
    """Lower-face deformation: rotate the jaw region about a hinge, keeping the corners closed."""
    x, y, z = co.T
    zc = mouth_z(np.clip(x, -0.08, 0.08))
    below = z < zc
    half = MOUTH_HALF * width
    wx = np.clip(1 - (np.abs(x) / half) ** 2, 0, 1) ** 1.2
    near = sig(0.0 - y, 0.05) * sig(z - 0.60, 0.02)
    w_low = wx * near * below
    hinge = np.array([0.0, -0.04, 0.705])
    ang = np.radians(open_deg) * w_low
    p = co - hinge
    c, s = np.cos(ang), np.sin(ang)
    ny = p[:, 1] * c - p[:, 2] * s
    nz = p[:, 1] * s + p[:, 2] * c
    d = np.zeros_like(co)
    d[:, 1] = ny - p[:, 1]
    d[:, 2] = nz - p[:, 2]  # +angle about +X drops the chin (Dudi faces -Y)
    # upper lip lift
    w_up = wx * near * (~below) * sig(zc + 0.03 - z, 0.012)
    d[:, 2] += upper_lift * w_up
    # corners
    corner = sig(np.abs(x) - 0.05, 0.02) * sig(0.10 - np.abs(x), 0.02) * sig(0.03 - np.abs(z - zc), 0.02) * near
    d[:, 2] += corner_up * corner
    d[:, 0] += corner_out * corner * np.sign(x)
    return d


def cheek_offsets(co, nrm, amount, raise_=0.0):
    x, y, z = co.T
    out = np.zeros_like(co)
    for s in (1, -1):
        c = np.array([0.095 * s, -0.10, 0.705])
        dd = np.linalg.norm(co - c, axis=1)
        w = smooth01(1 - dd / 0.075) * sig(-y + 0.02, 0.03)
        out += nrm * (amount * w)[:, None]
        out[:, 2] += raise_ * w
    return out


def add_body_shape_keys(ob):
    co = verts_np(ob)
    me = ob.data
    nrm = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    head = co[:, 2] > 0.55
    if not me.shape_keys:
        ob.shape_key_add(name='Basis')

    def key(name, d):
        d = d * head[:, None]
        k = ob.shape_key_add(name=name, from_mix=False)
        k.data.foreach_set('co', (co + d).ravel())
        k.slider_min = 0.0
        k.slider_max = 1.0
        return k

    Z = np.zeros_like(co)
    key('happy', jaw_offsets(co, 16, 1.0, corner_up=0.010, corner_out=0.004, upper_lift=0.004) + cheek_offsets(co, nrm, 0.004, 0.006))
    key('surprise', jaw_offsets(co, 13, 0.55, corner_up=-0.002, corner_out=-0.006))
    key('thinking', jaw_offsets(co, 0, 1.0, corner_up=-0.004) + cheek_offsets(co, nrm, 0.002, 0.0))
    key('confused', jaw_offsets(co, 2, 0.6, corner_up=-0.003))
    key('determined', jaw_offsets(co, 0, 1.0, corner_up=0.003, corner_out=0.002) + cheek_offsets(co, nrm, 0.002, 0.002))
    key('mischief', jaw_offsets(co, 2, 1.0, corner_up=0.012, corner_out=0.006) + cheek_offsets(co, nrm, 0.004, 0.006))
    key('laughing', jaw_offsets(co, 22, 1.0, corner_up=0.012, corner_out=0.006, upper_lift=0.006) + cheek_offsets(co, nrm, 0.006, 0.01))
    key('blink', Z)
    key('eyes_bulging', Z)
    key('cheeks_swollen', cheek_offsets(co, nrm, 0.018, 0.0) + jaw_offsets(co, 0, 0.6, corner_out=-0.006))
