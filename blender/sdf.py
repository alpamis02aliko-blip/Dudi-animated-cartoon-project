"""Signed-distance modelling helpers (numpy).

Dudi's body and the garment shells are built as smooth unions of analytic
primitives, polygonised with marching cubes, then re-meshed to quads in Blender.
All functions take P with shape (..., 3) and return distances (...,).
"""
import numpy as np


def _len(v):
    return np.sqrt(np.sum(v * v, axis=-1))


def smin(a, b, k):
    """Polynomial smooth minimum (union) with blend radius k."""
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


def ellipsoid(P, c, r, R=None):
    """Approximate SDF of an ellipsoid (Quilez). R: optional 3x3 world->local rotation."""
    q = P - np.asarray(c)
    if R is not None:
        q = q @ np.asarray(R).T
    r = np.asarray(r, dtype=float)
    k0 = _len(q / r)
    k1 = _len(q / (r * r))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def round_cone(P, a, b, r1, r2):
    """Exact SDF of a cone between spheres (a, r1) and (b, r2) (Quilez sdRoundCone)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = P - a
    y = pa @ ba
    z = y - l2
    x = pa * l2 - y[..., None] * ba
    x2 = np.sum(x * x, axis=-1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    d1 = np.sqrt(x2 + z2) * il2 - r2
    d2 = np.sqrt(x2 + y2) * il2 - r1
    d3 = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
    out = np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))
    return out


def chain(P, pts, radii, k=0.0):
    """Union of round cones along a polyline with per-point radii."""
    d = None
    for i in range(len(pts) - 1):
        di = round_cone(P, pts[i], pts[i + 1], radii[i], radii[i + 1])
        d = di if d is None else smin(d, di, k)
    return d


def box(P, c, half, R=None, rounding=0.0):
    q = P - np.asarray(c)
    if R is not None:
        q = q @ np.asarray(R).T
    q = np.abs(q) - (np.asarray(half) - rounding)
    return _len(np.maximum(q, 0.0)) + np.minimum(np.max(q, axis=-1), 0.0) - rounding


def uneven_capsule_2d(px, py, r1, r2, h):
    """2D SDF: circle r1 at (0,0) to circle r2 at (0,h) (Quilez sdUnevenCapsule)."""
    px = np.abs(px)
    b = (r1 - r2) / h
    a = np.sqrt(max(1.0 - b * b, 1e-9))
    k = -px * b + py * a  # dot((px,py), (-b, a))
    d_lo = np.sqrt(px * px + py * py) - r1
    d_hi = np.sqrt(px * px + (py - h) ** 2) - r2
    d_mid = px * a + py * b - r1
    return np.where(k < 0.0, d_lo, np.where(k > a * h, d_hi, d_mid))


def frame_from(origin, axis_u, axis_w):
    """Orthonormal local frame: u (length), v (width), w (thickness/normal)."""
    u = np.asarray(axis_u, float)
    u /= np.linalg.norm(u)
    w = np.asarray(axis_w, float)
    w = w - u * (w @ u)
    w /= np.linalg.norm(w)
    v = np.cross(w, u)
    R = np.stack([u, v, w])  # world->local rows
    return np.asarray(origin, float), R


def ear(P, base, tip, normal, half_width, tip_r, thick_base, thick_tip, cup):
    """Cupped, pointed ear: 2D uneven capsule in (v,u), extruded along w, bent by `cup`.

    Positive `cup` bends the edges toward +w (the front), making the front face concave.
    """
    base = np.asarray(base, float)
    tip = np.asarray(tip, float)
    L = float(np.linalg.norm(tip - base))
    o, R = frame_from(base, tip - base, normal)
    q = (P - o) @ R.T
    u, v, w = q[..., 0], q[..., 1], q[..., 2]
    t = np.clip(u / L, 0.0, 1.0)
    w = w - cup * (v / half_width) ** 2 * (1.0 - 0.6 * t)
    d2 = uneven_capsule_2d(v, u, half_width, tip_r, L)
    th = thick_base + (thick_tip - thick_base) * t
    dw = np.abs(w) - th
    dd = np.stack([d2, dw], -1)
    return _len(np.maximum(dd, 0.0)) + np.minimum(np.max(dd, -1), 0.0)


def grid(lo, hi, step):
    xs = np.arange(lo[0], hi[0] + step, step)
    ys = np.arange(lo[1], hi[1] + step, step)
    zs = np.arange(lo[2], hi[2] + step, step)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
    return np.stack([X, Y, Z], -1), (xs, ys, zs)


def polygonise(field, axes, level=0.0):
    """Marching cubes -> (verts, faces) in world units, outward-facing."""
    from skimage.measure import marching_cubes
    xs, ys, zs = axes
    step = (xs[1] - xs[0], ys[1] - ys[0], zs[1] - zs[0])
    # pad with 'outside' so shapes cut by the sampling box still give closed surfaces
    field = np.pad(field, 1, mode='constant', constant_values=1.0)
    verts, faces, _n, _v = marching_cubes(field, level=level, spacing=step)
    verts = verts + np.array([xs[0] - step[0], ys[0] - step[1], zs[0] - step[2]])
    # skimage gives faces wound so normals point toward increasing field (outside for SDF).
    return verts, faces[:, ::-1]
