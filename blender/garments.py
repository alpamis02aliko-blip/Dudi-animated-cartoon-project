"""Clothes as separate meshes built from offset distance fields of the body parts,
so every layer sits outside the one beneath it by construction:

  body < hoodie (torso+sleeves) < jacket < hood roll / collar / backpack straps
  body < pants (with rolled hems and cargo pockets) ; body feet < sneakers
"""
import math
import time
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
import spec as S
import sdf
import body as B
from sdf import smin, smax, ellipsoid, round_cone, box, _len
from bl_util import mesh_object, voxel_remesh, verts_np, poly_centers_np, link

# offsets from the body surface (inner surface of each garment)
HOODIE_OFF = 0.010
HOODIE_T = 0.0030
JACKET_OFF = 0.024
JACKET_T = 0.0055
PANTS_OFF = 0.013
PANTS_T = 0.0035


def shell(name, field_fn, lo, hi, coll, step=0.004, voxel=0.0035):
    t = time.time()
    P, axes = sdf.grid(lo, hi, step)
    P = P.astype(np.float32)
    d = field_fn(P)
    v, f = sdf.polygonise(d, axes)
    ob = mesh_object(name, v, f, coll)
    voxel_remesh(ob, voxel)
    print('  %s: %d verts (%.1fs)' % (name, len(ob.data.vertices), time.time() - t))
    return ob


def bisect(ob, co, no, clear_outer=False, clear_inner=False):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=Vector(co), plane_no=Vector(no),
                           clear_outer=clear_outer, clear_inner=clear_inner)
    bm.to_mesh(ob.data)
    bm.free()


def delete_faces(ob, pred):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    kill = [f for f in bm.faces if pred(f.calc_center_median())]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    # drop tiny islands left behind by the cuts
    bm.verts.ensure_lookup_table()
    bm.to_mesh(ob.data)
    bm.free()
    keep_largest(ob)


def keep_largest(ob, min_frac=0.02):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    seen = set()
    islands = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack = [f]
        isl = []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        islands.append(isl)
    if len(islands) > 1:
        big = max(len(i) for i in islands)
        kill = [f for isl in islands if len(isl) < big * min_frac for f in isl]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(ob.data)
    bm.free()


def solidify(ob, t, offset=1.0, rim=True):
    m = ob.modifiers.new('thick', 'SOLIDIFY')
    m.thickness = t
    m.offset = offset
    m.use_rim = rim
    m.use_even_offset = True
    return m


def subsurf(ob, lv=1):
    m = ob.modifiers.new('sub', 'SUBSURF')
    m.levels = lv
    m.render_levels = lv
    return m


# ------------------------------------------------------------------ fields
def upper_body(P):
    t = B.torso_field(P)
    for s in 'LR':
        t = smin(t, B.arm_field(P, s), 0.03)
    return t


def forearm_axis(side):
    s = 1 if side == 'L' else -1
    e = np.array([S.ELBOW[0] * s, S.ELBOW[1], S.ELBOW[2]])
    w = np.array([S.WRIST[0] * s, S.WRIST[1], S.WRIST[2]])
    a = (w - e) / np.linalg.norm(w - e)
    return e, w, a


def cuff_plane(side, extra):
    """Plane through the forearm axis at the jacket cuff (+extra along the arm)."""
    e, w, a = forearm_axis(side)
    t = (S.CUFF_Z - e[2]) / a[2]
    p = e + a * (t + extra)
    return p, a


def ring_band(P, side, z0, z1, extra, base_fn):
    """A bulge band around a limb between two planes along its axis."""
    e, w, a = forearm_axis(side)
    t = ((P - e) @ a)
    t0 = (z0 - e[2]) / a[2]
    t1 = (z1 - e[2]) / a[2]
    lo, hi = min(t0, t1), max(t0, t1)
    slab = np.maximum(lo - t, t - hi)
    return smax(base_fn(P) - extra, slab, 0.004)


def hoodie_field(P):
    d = upper_body(P) - HOODIE_OFF
    # ribbed hem band and cuffs (slightly fuller)
    hem = smax(B.torso_field(P) - (HOODIE_OFF + 0.004), np.maximum(S.HOODIE_HEM_Z - P[..., 2], P[..., 2] - 0.292), 0.003)
    return smin(d, hem, 0.004)


def jacket_field(P):
    d = upper_body(P) - JACKET_OFF
    # hem band and cuff bands
    band = smax(B.torso_field(P) - (JACKET_OFF + 0.0035), np.maximum(S.JACKET_HEM_Z - P[..., 2], P[..., 2] - 0.322), 0.003)
    d = smin(d, band, 0.003)
    for s in 'LR':
        cuff = ring_band(P, s, S.CUFF_Z, S.CUFF_Z + 0.026, JACKET_OFF + 0.004, lambda Q, s=s: B.arm_field(Q, s))
        d = smin(d, cuff, 0.003)
    # chest pockets (flap + pocket bag), slightly raised
    for s in (1, -1):
        d = smin(d, box(P, (0.088 * s, -0.103, 0.478), (0.030, 0.010, 0.026), rounding=0.008) , 0.006)
    return d


def pants_field(P):
    z = P[..., 2]
    hips = ellipsoid(P, (0, 0.006, 0.282), (0.113, 0.082, 0.075))
    hips = smin(hips, ellipsoid(P, (0, -0.004, 0.33), (0.116, 0.08, 0.06)), 0.03)
    d = hips
    for s in 'LR':
        d = smin(d, B.leg_field(P, s), 0.035)
    off = PANTS_OFF + 0.012 * np.clip(1 - z / 0.24, 0, 1) - 0.007 * np.clip((z - 0.255) / 0.03, 0, 1)
    d = d - off
    for s in (1, -1):
        # rolled cuffs: a thick band at the hem
        ax = np.array([S.ANKLE[0] * s, S.ANKLE[1], 0.0])
        rr = np.sqrt((P[..., 0] - ax[0]) ** 2 + (P[..., 1] - ax[1]) ** 2)
        cuff = smax(rr - 0.061, np.maximum(S.PANTS_HEM_Z - 0.002 - z, z - S.CUFF_ROLL_TOP_Z), 0.008)
        d = smin(d, cuff, 0.006)
        # cargo pockets on the outer thighs with flaps
        d = smin(d, box(P, (0.118 * s, 0.006, 0.178), (0.012, 0.036, 0.040), rounding=0.009), 0.006)
        d = smin(d, box(P, (0.121 * s, 0.006, 0.222), (0.012, 0.039, 0.012), rounding=0.005), 0.003)
    return d


# ------------------------------------------------------------------ builders
def build_hoodie(coll):
    ob = shell('hoodie', hoodie_field, (-0.28, -0.16, 0.22), (0.28, 0.16, 0.64), coll)
    bisect(ob, (0, 0, S.HOODIE_HEM_Z), (0, 0, -1), clear_outer=True)
    for s in 'LR':
        p, a = cuff_plane(s, 0.007)
        bisect(ob, p, a, clear_outer=True)
    # neck opening
    delete_faces(ob, lambda c: c.z > 0.50 and math.hypot(c.x, c.y - 0.012) < 0.084)
    solidify(ob, HOODIE_T, 1.0)
    subsurf(ob)
    return ob


def build_jacket(coll):
    ob = shell('jacket', jacket_field, (-0.30, -0.18, 0.26), (0.30, 0.18, 0.64), coll)
    bisect(ob, (0, 0, S.JACKET_HEM_Z), (0, 0, -1), clear_outer=True)
    for s in 'LR':
        p, a = cuff_plane(s, 0.0)
        bisect(ob, p, a, clear_outer=True)
    # neckline and open front
    for s in (1, -1):
        bisect(ob, (0.050 * s, 0, 0), (1, 0, 0))
    delete_faces(ob, lambda c: c.z > 0.48 and math.hypot(c.x, c.y - 0.012) < 0.104)
    delete_faces(ob, lambda c: c.y < -0.02 and abs(c.x) < 0.050 and c.z < 0.62)
    # front V of the neckline (lapels open toward the collar)
    delete_faces(ob, lambda c: c.y < -0.03 and c.z > 0.50 and abs(c.x) < 0.050 + (c.z - 0.50) * 0.8)
    solidify(ob, JACKET_T, 1.0)
    subsurf(ob)
    return ob


def build_pants(coll):
    ob = shell('pants', pants_field, (-0.22, -0.14, 0.07), (0.22, 0.14, 0.34), coll)
    bisect(ob, (0, 0, 0.300), (0, 0, 1), clear_outer=True)
    bisect(ob, (0, 0, S.PANTS_HEM_Z), (0, 0, -1), clear_outer=True)
    solidify(ob, PANTS_T, 1.0)
    subsurf(ob)
    return ob


def hood_field_factory(jacket_ob):
    """Hood roll around the neck, clipped against the jacket and the neck so it rests on them."""
    jv = verts_np(jacket_ob)

    def f(P):
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        cy = 0.012
        ang = np.arctan2(x, -(y - cy))  # 0 at the front, +/-pi at the back
        back = 0.5 - 0.5 * np.cos(ang)  # 0 front, 1 back
        ax, ay = 0.118 + 0.006 * back, 0.112 + 0.010 * back
        rho = np.sqrt((x / ax) ** 2 + ((y - cy) / ay) ** 2)
        R = 0.5 * (ax + ay)
        zc = 0.584 + 0.020 * back - 0.012 * (1 - back) ** 3
        minor = 0.026 + 0.016 * back
        d = np.sqrt(((rho - 1.0) * R) ** 2 + ((z - zc) / 1.15) ** 2) - minor
        # clip: stay outside the jacket solid and the neck
        jac = upper_body(P) - (JACKET_OFF + JACKET_T + 0.004)
        neck = B.neck_field(P) - 0.006
        d = smax(d, -jac, 0.004)
        d = smax(d, -neck, 0.004)
        # hoodie front panel continues down into the jacket opening
        return d

    return f


def build_hood(coll, jacket_ob):
    ob = shell('hoodie_hood', hood_field_factory(jacket_ob), (-0.20, -0.16, 0.50), (0.20, 0.19, 0.66), coll,
               step=0.0035, voxel=0.003)
    subsurf(ob)
    return ob


def shoe_field_local(P):
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    sole = box(P, (0, -0.008, 0.0095), (0.054, 0.097, 0.0095), rounding=0.0085)
    upper = ellipsoid(P, (0, -0.052, 0.030), (0.050, 0.052, 0.034))
    upper = smin(upper, ellipsoid(P, (0, 0.046, 0.040), (0.046, 0.043, 0.042)), 0.03)
    upper = smin(upper, ellipsoid(P, (0, -0.004, 0.046), (0.045, 0.058, 0.040)), 0.03)
    upper = smax(upper, 0.012 - z, 0.004)
    # tongue rising out of the opening
    tongue = box(P, (0, -0.040, 0.066), (0.025, 0.018, 0.010), rounding=0.008)
    upper = smin(upper, tongue, 0.01)
    return smin(sole, upper, 0.004)


SHOE_TOE_OUT = math.radians(7.0)


def shoe_matrix(side):
    s = 1 if side == 'L' else -1
    return Matrix.Translation((0.080 * s, -0.010, 0.0)) @ Matrix.Rotation(-SHOE_TOE_OUT * s, 4, 'Z')


def build_shoe(side, coll):
    M = shoe_matrix(side)
    Mi = np.array(M.inverted())

    def f(P):
        Q = P @ Mi[:3, :3].T + Mi[:3, 3]
        return shoe_field_local(Q)

    s = 1 if side == 'L' else -1
    lo = (0.080 * s - 0.08, -0.13, -0.005)
    hi = (0.080 * s + 0.08, 0.11, 0.095)
    ob = shell('sneaker.' + side, f, (min(lo[0], hi[0]), lo[1], lo[2]), (max(lo[0], hi[0]), hi[1], hi[2]), coll,
               step=0.003, voxel=0.0028)
    # ankle opening
    ank = Vector((S.ANKLE[0] * s, S.ANKLE[1] + 0.008, 0))
    delete_faces(ob, lambda c: c.z > 0.060 and (Vector((c.x, c.y, 0)) - ank).length < 0.036)
    solidify(ob, 0.003, -1.0)
    subsurf(ob)
    return ob


def backpack_field(P):
    d = box(P, (0, 0.165, 0.452), (0.098, 0.044, 0.098), rounding=0.040)
    d = smin(d, box(P, (0, 0.208, 0.398), (0.076, 0.016, 0.046), rounding=0.014), 0.006)
    return d


def build_backpack(coll):
    ob = shell('backpack', backpack_field, (-0.14, 0.09, 0.32), (0.14, 0.25, 0.58), coll, step=0.003, voxel=0.003)
    subsurf(ob)
    return ob
