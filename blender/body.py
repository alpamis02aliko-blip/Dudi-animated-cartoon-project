"""Dudi's body as a signed-distance field: one continuous surface for head, ears,
torso, limbs, hands, feet and tail. Also exposes the per-part fields used for
region masks, garment shells and skin weights."""
import numpy as np
from sdf import smin, smax, ellipsoid, round_cone, chain, _len, frame_from
import spec as S


def mirror(p):
    return (-p[0], p[1], p[2])


# ------------------------------------------------------------------ parts
def cap_frame():
    """World->cap-local rotation (rows: x, t, n) and base centre."""
    b = np.radians(S.CAP_TILT_DEG)
    n = np.array([0.0, np.sin(b), np.cos(b)])
    t = np.array([0.0, np.cos(b), -np.sin(b)])
    x = np.array([1.0, 0.0, 0.0])
    return np.asarray(S.CAP_C0, float), np.stack([x, t, n])


def cap_volume(P, inflate=0.0):
    """Solid volume of the cap crown (outer surface), optionally inflated."""
    c0, R = cap_frame()
    q = (P - c0) @ R.T
    r = np.asarray(S.CAP_R_OUT) + inflate
    d = ellipsoid(q, (0, 0, 0), r)
    return smax(d, -(q[..., 2] + 0.012 + inflate), 0.0)


def ear_field(P, side):
    """Leaf-shaped pointed ear, cupped toward the front, clipped where the cap sits."""
    s = 1.0 if side == 'L' else -1.0
    base = np.array([0.172 * s, 0.112, 0.800])
    tip = np.array([S.EAR_TIP[0] * s, S.EAR_TIP[1], S.EAR_TIP[2]])
    yaw = np.radians(40.0)
    normal = np.array([np.sin(yaw) * s, -np.cos(yaw), 0.0])  # front of the ear faces forward-out
    L = float(np.linalg.norm(tip - base))
    o, R = frame_from(base, tip - base, normal)
    q = (P - o) @ R.T
    u, v, w = q[..., 0], q[..., 1], q[..., 2]
    t = np.clip(u / L, 0.0, 1.0)
    hw_top = 0.075 * np.power(np.clip((1.0 - t) / 0.55, 0.0, 1.0), 0.6)
    hw_base = 0.075 * (0.78 + 0.22 * np.clip(t / 0.25, 0.0, 1.0))
    hw = np.minimum(hw_top, hw_base) + 0.003
    w = w - 0.02 * (v / 0.075) ** 2 * (1.0 - 0.5 * t)  # edges curl forward: front face is concave
    th = 0.013 + (0.0045 - 0.013) * t
    d_profile = np.maximum(np.maximum(np.abs(v) - hw, -u), u - L) * 0.85
    d_thick = np.abs(w) - th
    dd = np.stack([d_profile, d_thick], -1)
    d = _len(np.maximum(dd, 0.0)) + np.minimum(np.max(dd, -1), 0.0) - 0.002
    return smax(d, -cap_volume(P, 0.008), 0.004)


def head_field(P):
    d = ellipsoid(P, (0, 0.012, 0.805), (0.160, 0.150, 0.172))
    for s in (1, -1):
        d = smin(d, ellipsoid(P, (0.083 * s, -0.045, 0.725), (0.118, 0.100, 0.090)), 0.05)
    d = smin(d, ellipsoid(P, (0, -0.122, 0.708), (0.070, 0.070, 0.052)), 0.035)
    d = smin(d, round_cone(P, (0, -0.085, 0.790), (0, -0.165, 0.735), 0.055, 0.030), 0.03)
    d = smin(d, ellipsoid(P, (0, -0.098, 0.652), (0.055, 0.062, 0.032)), 0.03)
    d = smin(d, ellipsoid(P, (0, -0.030, 0.648), (0.110, 0.100, 0.060)), 0.04)
    # cheek ruffs: pointed tufts flaring out and down
    for s in (1, -1):
        for (a, ra, b, rb) in (
            ((0.160, -0.015, 0.712), 0.034, (0.230, 0.005, 0.684), 0.011),
            ((0.150, 0.010, 0.672), 0.030, (0.210, 0.030, 0.638), 0.010),
            ((0.165, -0.010, 0.748), 0.028, (0.220, 0.000, 0.740), 0.010),
        ):
            d = smin(d, round_cone(P, (a[0] * s, a[1], a[2]), (b[0] * s, b[1], b[2]), ra, rb), 0.02)
    # eye sockets
    for s in (1, -1):
        e = (S.EYE_C[0] * s, S.EYE_C[1], S.EYE_C[2])
        d = smax(d, -ellipsoid(P, e, (S.EYE_SOCKET_R,) * 3), 0.008)
    return d


def neck_field(P):
    return round_cone(P, (0, 0.015, 0.660), (0, 0.012, 0.530), 0.068, 0.072)


def torso_field(P):
    d = ellipsoid(P, (0, 0.000, 0.455), (0.112, 0.075, 0.105))
    d = smin(d, ellipsoid(P, (0, -0.004, 0.370), (0.118, 0.080, 0.090)), 0.04)
    d = smin(d, ellipsoid(P, (0, 0.006, 0.282), (0.113, 0.082, 0.075)), 0.04)
    for s in (1, -1):
        d = smin(d, round_cone(P, (0.05 * s, 0.0, 0.50), (S.SHOULDER[0] * s, S.SHOULDER[1], S.SHOULDER[2]), 0.06, 0.04), 0.03)
    return d


def arm_pts(side):
    s = 1 if side == 'L' else -1
    m = lambda p: (p[0] * s, p[1], p[2])
    return [m(S.SHOULDER), m(S.ELBOW), m(S.WRIST)], [0.032, 0.025, 0.021]


def arm_field(P, side):
    pts, rr = arm_pts(side)
    return chain(P, pts, rr, 0.01)


def hand_field(P, side):
    s = 1 if side == 'L' else -1
    m = lambda p: (p[0] * s, p[1], p[2])
    d = ellipsoid(P, m((0.193, 0.002, 0.292)), (0.028, 0.038, 0.040))
    d = smin(d, round_cone(P, m(S.WRIST), m((0.19, 0.0, 0.312)), 0.021, 0.025), 0.01)
    for (c, r) in (((0.186, -0.027, 0.262), 0.0175), ((0.188, -0.004, 0.255), 0.018), ((0.189, 0.020, 0.261), 0.017)):
        d = smin(d, ellipsoid(P, m(c), (r * 1.1, r, r)), 0.008)
    d = smin(d, round_cone(P, m((0.172, -0.030, 0.312)), m((0.166, -0.044, 0.286)), 0.016, 0.013), 0.008)
    return d


def leg_field(P, side):
    s = 1 if side == 'L' else -1
    m = lambda p: (p[0] * s, p[1], p[2])
    return chain(P, [m(S.HIP), m(S.KNEE), m(S.ANKLE)], [0.050, 0.040, 0.030], 0.01)


def foot_field(P, side):
    s = 1 if side == 'L' else -1
    return ellipsoid(P, (0.078 * s, -0.012, 0.030), (0.028, 0.055, 0.022))


def tail_centerline(n=64):
    pts = np.array([(0.0, y, z) for (y, z) in S.TAIL_PTS])
    rr = np.array(S.TAIL_R)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)]) / seg.sum()
    return pts, rr, s


def tail_field(P):
    pts, rr, _ = tail_centerline()
    return chain(P, [tuple(p) for p in pts], list(rr), 0.02)


PARTS = ['head', 'neck', 'torso', 'ear_L', 'ear_R', 'arm_L', 'arm_R', 'hand_L', 'hand_R',
         'leg_L', 'leg_R', 'foot_L', 'foot_R', 'tail']


def part_fields(P):
    return {
        'head': head_field(P), 'neck': neck_field(P), 'torso': torso_field(P),
        'ear_L': ear_field(P, 'L'), 'ear_R': ear_field(P, 'R'),
        'arm_L': arm_field(P, 'L'), 'arm_R': arm_field(P, 'R'),
        'hand_L': hand_field(P, 'L'), 'hand_R': hand_field(P, 'R'),
        'leg_L': leg_field(P, 'L'), 'leg_R': leg_field(P, 'R'),
        'foot_L': foot_field(P, 'L'), 'foot_R': foot_field(P, 'R'),
        'tail': tail_field(P),
    }


def body_field(P, parts=None):
    f = parts or part_fields(P)
    d = smin(f['head'], f['neck'], 0.03)
    d = smin(d, f['ear_L'], 0.018)
    d = smin(d, f['ear_R'], 0.018)
    d = smin(d, f['torso'], 0.04)
    for s in 'LR':
        d = smin(d, f['arm_' + s], 0.03)
        d = smin(d, f['hand_' + s], 0.012)
        d = smin(d, f['leg_' + s], 0.035)
        d = smin(d, f['foot_' + s], 0.015)
    d = smin(d, f['tail'], 0.025)
    return d


BOUNDS = ((-0.31, -0.25, -0.01), (0.31, 0.46, 1.13))
