"""Backward burgundy baseball cap: six-panel crown with seams, eyelets and top
button, snapback opening with a holed strap (facing forward, because the cap is
worn backward) and a cambered brim pointing back and down."""
import math
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
import spec as S
import body as B
from bl_util import mesh_object, link

SEAMS_DEG = [30, 90, 150, 210, 270, 330]
OPEN_HALF_X = 0.050      # snapback opening half-width
OPEN_BASE_N = 0.030      # straight part of the opening above the base
OPEN_ARCH_N = 0.036      # arch height on top of that


def frame():
    c0, R = B.cap_frame()  # rows: x, t (toward the back of the head), n (up)
    return Vector(c0), Matrix([list(R[0]), list(R[1]), list(R[2])]).transposed()  # columns = axes


def to_world(local):
    c0, M = frame()
    return c0 + M @ Vector(local)


def crown_point(theta, phi, inflate=0.0, seam=True):
    rx, rt, rn = (np.array(S.CAP_R_OUT) + inflate)
    st, ct = math.sin(theta), math.cos(theta)
    p = Vector((rx * st * math.cos(phi), rt * st * math.sin(phi), rn * ct))
    if seam:
        # shallow groove along each panel seam
        dmin = min(abs(((math.degrees(phi) - s) + 180) % 360 - 180) for s in SEAMS_DEG)
        arc = math.radians(dmin) * st * 0.18
        dent = 0.0011 * math.exp(-(arc / 0.0022) ** 2)
        p = p * (1.0 - dent / max(p.length, 1e-6))
    return p


def in_opening(p):
    """Local point on the crown's rear (= head front) inside the snapback arch?"""
    if p.y > -0.02:
        return False
    x, n = abs(p.x), p.z
    if x >= OPEN_HALF_X:
        return False
    top = OPEN_BASE_N + OPEN_ARCH_N * math.sqrt(max(0.0, 1 - (x / OPEN_HALF_X) ** 2))
    return n < top


def build_crown(coll, n_theta=46, n_phi=180):
    verts, faces, keep = [], [], []
    thetas = [math.radians(1.0 + 89.0 * (i / (n_theta - 1)) ** 0.9) for i in range(n_theta)]
    for th in thetas:
        for j in range(n_phi):
            phi = 2 * math.pi * j / n_phi
            verts.append(crown_point(th, phi))
    top = len(verts)
    verts.append(Vector((0, 0, S.CAP_R_OUT[2])))
    for i in range(n_theta - 1):
        for j in range(n_phi):
            a = i * n_phi + j
            b = i * n_phi + (j + 1) % n_phi
            faces.append((a, a + n_phi, b + n_phi, b))
    for j in range(n_phi):
        faces.append((top, j, (j + 1) % n_phi))
    # remove the snapback opening
    kept = []
    for f in faces:
        c = sum((verts[k] for k in f), Vector()) / len(f)
        if not in_opening(c):
            kept.append(f)
    ob = mesh_object('cap_crown', [to_world(v) for v in verts], kept, coll)
    # snap the opening rim onto the analytic arch
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    c0, M = frame()
    Minv = M.inverted()
    for v in bm.verts:
        if not v.is_boundary:
            continue
        lp = Minv @ (v.co - c0)
        if lp.z < 0.004 or lp.y > -0.02:
            continue  # the bottom band edge
        x, n = lp.x, lp.z
        if abs(x) < OPEN_HALF_X * 1.15 and n < OPEN_BASE_N + OPEN_ARCH_N + 0.01:
            # nearest point on the arch boundary
            if n <= OPEN_BASE_N:
                x = math.copysign(OPEN_HALF_X, x)
            else:
                a = math.atan2((n - OPEN_BASE_N) / OPEN_ARCH_N, x / OPEN_HALF_X)
                x, n = OPEN_HALF_X * math.cos(a), OPEN_BASE_N + OPEN_ARCH_N * math.sin(a)
            # back onto the ellipsoid surface
            rx, rt, rn = S.CAP_R_OUT
            t2 = 1 - (x / rx) ** 2 - (n / rn) ** 2
            y = -rt * math.sqrt(max(t2, 0.0))
            v.co = c0 + M @ Vector((x, y, n))
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def opening_loop_points(n=60, lift=0.0016):
    """Analytic rim of the snapback opening (for the binding)."""
    pts = []
    rx, rt, rn = S.CAP_R_OUT
    path = []
    # up the left side, over the arch, down the right side
    for i in range(10):
        path.append((-OPEN_HALF_X, OPEN_BASE_N * (i / 9)))
    for i in range(1, n):
        a = math.pi * (1 - i / n)
        path.append((OPEN_HALF_X * math.cos(a), OPEN_BASE_N + OPEN_ARCH_N * math.sin(a)))
    for i in range(10):
        path.append((OPEN_HALF_X, OPEN_BASE_N * (1 - i / 9)))
    for (x, nn) in path:
        t2 = 1 - (x / rx) ** 2 - (nn / rn) ** 2
        y = -rt * math.sqrt(max(t2, 0.0))
        p = Vector((x, y, nn))
        nrm = Vector((x / rx ** 2, y / rt ** 2, nn / rn ** 2)).normalized()
        pts.append((to_world(p + nrm * lift), frame()[1] @ nrm))
    return pts


def tube_along(name, pts, radius, coll, segs=8, closed=False, flat=1.0, up=None):
    verts, faces = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        a = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        tng = a.normalized()
        ref = up[i] if up is not None else Vector((0, 0, 1))
        nx = tng.cross(ref)
        if nx.length < 1e-6:
            nx = tng.orthogonal()
        nx.normalize()
        ny = nx.cross(tng).normalized()
        for k in range(segs):
            ang = 2 * math.pi * k / segs
            verts.append(p + nx * (math.cos(ang) * radius) + ny * (math.sin(ang) * radius * flat))
    for i in range(n - 1 if not closed else n):
        for k in range(segs):
            a = i * segs + k
            b = i * segs + (k + 1) % segs
            c = ((i + 1) % n) * segs + (k + 1) % segs
            d = ((i + 1) % n) * segs + k
            faces.append((a, b, c, d))
    if not closed:
        faces.append(tuple(range(segs))[::-1])
        faces.append(tuple(range((n - 1) * segs, n * segs)))
    return mesh_object(name, verts, faces, coll)


def build_strap(coll):
    """Holed strap across the bottom of the opening, sitting just proud of the crown."""
    rx, rt, rn = S.CAP_R_OUT
    nx, nn = 40, 6
    verts, faces = [], []
    lift = 0.0028
    for i in range(nn + 1):
        n = 0.006 + 0.022 * i / nn
        for j in range(nx + 1):
            x = -0.064 + 0.128 * j / nx
            t2 = 1 - ((x / (rx + lift)) ** 2) - (n / (rn + lift)) ** 2
            y = -(rt + lift) * math.sqrt(max(t2, 0.0))
            verts.append(to_world((x, y, n)))
    for i in range(nn):
        for j in range(nx):
            a = i * (nx + 1) + j
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    ob = mesh_object('cap_strap', verts, faces, coll)
    sol = ob.modifiers.new('thick', 'SOLIDIFY')
    sol.thickness = 0.0022
    sol.offset = 1.0
    holes = []
    for k, x in enumerate((-0.012, 0.004, 0.020, 0.036)):
        n = 0.017
        t2 = 1 - (x / rx) ** 2 - (n / rn) ** 2
        y = -(rt + 0.0058) * math.sqrt(max(t2, 0.0))
        holes.append(to_world((x, y, n)))
    return ob, holes


def build_brim(coll, n_s=40, n_r=14):
    rx, rt, rn = S.CAP_R_OUT
    span = math.radians(64)
    drop = math.radians(S.CAP_BRIM_DROP_DEG)
    L = S.CAP_BRIM_LEN
    verts, faces = [], []
    for i in range(n_r + 1):
        r = i / n_r
        for j in range(n_s + 1):
            s = -1 + 2 * j / n_s
            phi = math.pi / 2 + span * s
            inner = Vector((rx * math.cos(phi), rt * math.sin(phi), -0.002))
            length = L * math.sqrt(max(0.0, 1 - abs(s) ** 2.6))
            out = Vector((inner.x * (1 + 0.25 * r), inner.y + length * r, 0.0))
            camber = -0.022 * (s ** 2) * r
            out.z = inner.z - math.sin(drop) * length * r + camber
            out.y = inner.y + math.cos(drop) * length * r
            verts.append(to_world(out))
    for i in range(n_r):
        for j in range(n_s):
            a = i * (n_s + 1) + j
            faces.append((a, a + n_s + 1, a + n_s + 2, a + 1))
    ob = mesh_object('cap_brim', verts, faces, coll)
    sol = ob.modifiers.new('thick', 'SOLIDIFY')
    sol.thickness = 0.0055
    sol.offset = 0.0
    sol.use_rim = True
    return ob


def build_cap(coll, mat_cap, mat_dark, mat_metal):
    crown = build_crown(coll)
    sol = crown.modifiers.new('thick', 'SOLIDIFY')
    sol.thickness = S.CAP_THICK
    sol.offset = -1.0
    sub = crown.modifiers.new('sub', 'SUBSURF')
    sub.levels = 1
    sub.render_levels = 1
    crown.data.materials.append(mat_cap)
    parts = [crown]
    binding = tube_along('cap_binding', [p for p, n in opening_loop_points()], 0.0021, coll, 8,
                         up=[n for p, n in opening_loop_points()])
    binding.data.materials.append(mat_cap)
    parts.append(binding)
    strap, holes = build_strap(coll)
    strap.data.materials.append(mat_cap)
    parts.append(strap)
    for k, h in enumerate(holes):
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, segments=16, radius=0.0032)
        me = bpy.data.meshes.new('hole')
        bm.to_mesh(me)
        bm.free()
        ob = link(bpy.data.objects.new('cap_strap_hole.%d' % k, me), coll)
        nrm = (h - Vector(S.CAP_C0)).normalized()
        ob.matrix_world = Matrix.Translation(h) @ Vector((0, 0, 1)).rotation_difference(nrm).to_matrix().to_4x4()
        me.materials.append(mat_dark)
        parts.append(ob)
    brim = build_brim(coll)
    brim.data.materials.append(mat_cap)
    parts.append(brim)
    # top button
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=0.011)
    me = bpy.data.meshes.new('cap_button')
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    btn = link(bpy.data.objects.new('cap_button', me), coll)
    c0, M = frame()
    btn.matrix_world = Matrix.Translation(to_world((0, 0, S.CAP_R_OUT[2] + 0.002))) @ M.to_4x4() @ Matrix.Diagonal((1, 1, 0.45, 1))
    me.materials.append(mat_cap)
    parts.append(btn)
    # eyelets on the four side panels
    for k, phi in enumerate((60, 120, 240, 300)):
        th = math.radians(43)
        p = crown_point(th, math.radians(phi), 0.0006, seam=False)
        rx, rt, rn = S.CAP_R_OUT
        nrm_l = Vector((p.x / rx ** 2, p.y / rt ** 2, p.z / rn ** 2)).normalized()
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.0042, radius2=0.0042, depth=0.0012)
        me = bpy.data.meshes.new('eyelet')
        bm.to_mesh(me)
        bm.free()
        ob = link(bpy.data.objects.new('cap_eyelet.%d' % k, me), coll)
        nrm = M @ nrm_l
        ob.matrix_world = Matrix.Translation(to_world(p)) @ Vector((0, 0, 1)).rotation_difference(nrm).to_matrix().to_4x4()
        me.materials.append(mat_dark)
        parts.append(ob)
    return parts


def seam_polylines(offset_deg=0.9, n=40):
    """Stitch paths either side of every panel seam (world space) with outward normals."""
    lines = []
    rx, rt, rn = S.CAP_R_OUT
    c0, M = frame()
    for s in SEAMS_DEG:
        for side in (-1, 1):
            pts = []
            for i in range(n):
                th = math.radians(6 + 82 * i / (n - 1))
                phi = math.radians(s + side * offset_deg / max(math.sin(th), 0.15) * 1.0)
                p = crown_point(th, phi, 0.0, seam=False)
                if in_opening(p) or (s == 270 and p.z < OPEN_BASE_N + OPEN_ARCH_N + 0.006):
                    continue
                nrm = Vector((p.x / rx ** 2, p.y / rt ** 2, p.z / rn ** 2)).normalized()
                pts.append((to_world(p + nrm * 0.0008), M @ nrm))
            if len(pts) > 3:
                lines.append(pts)
    return lines
