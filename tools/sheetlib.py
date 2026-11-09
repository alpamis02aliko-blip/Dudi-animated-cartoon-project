"""Shared helpers for measuring the Dudi master sheet and comparing renders to it.

Pure numpy + Pillow so it runs outside Blender.
"""
import json
import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHEET = os.path.join(REPO, 'reference', 'dudi_master_sheet.jpg')
BG = np.array([217.0, 214.0, 210.0])

# Crop boxes (x0, y0, x1, y1) in sheet pixels (sheet is 1438 x 2576).
CROPS = {
    'front': (60, 270, 400, 920),
    'q34': (410, 270, 800, 920),
    'side': (740, 270, 1120, 920),
    'back': (1110, 270, 1438, 920),
    'happy': (90, 1480, 420, 1840),
    'surprise': (520, 1050, 880, 1410),
    'determined': (970, 1480, 1330, 1840),
}


def load_sheet():
    return np.asarray(Image.open(SHEET).convert('RGB')).astype(np.float64)


def crop(a, view):
    x0, y0, x1, y1 = CROPS[view]
    return a[y0:y1, x0:x1]


def _dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def _erode(m, r):
    return ~_dilate(~m, r)


def label_components(m):
    """4-connected components; returns label image and sizes (simple BFS, fine for crops)."""
    h, w = m.shape
    lab = np.zeros((h, w), np.int32)
    sizes = [0]
    cur = 0
    ys, xs = np.nonzero(m)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        cur += 1
        stack = [(y0, x0)]
        lab[y0, x0] = cur
        n = 0
        while stack:
            y, x = stack.pop()
            n += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    stack.append((yy, xx))
        sizes.append(n)
    return lab, np.array(sizes)


def fg_mask(img, bg=BG):
    """Foreground = differs from the grey backdrop, excluding neutral floor shadows and guide lines."""
    d = np.linalg.norm(img - bg, axis=2)
    chroma = img.max(2) - img.min(2)
    val = img.mean(2)
    shadow = (chroma < 14) & (val < bg.mean() + 2)
    m = (d > 22) & ~shadow
    m = _erode(_dilate(m, 2), 2)  # close small gaps in fur
    lab, sizes = label_components(m)
    if len(sizes) > 1:
        keep = np.argmax(sizes[1:]) + 1
        m = lab == keep
    # fill holes: background not connected to border
    inv = ~m
    lab2, _ = label_components(inv)
    border = set(np.unique(np.concatenate([lab2[0], lab2[-1], lab2[:, 0], lab2[:, -1]])))
    holes = inv & ~np.isin(lab2, list(border))
    return m | holes


def hsv(img):
    r, g, b = [img[..., i] / 255.0 for i in range(3)]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    d = mx - mn + 1e-9
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-9), 0)
    return h, s, mx


def part_masks(img, fg):
    """Colour-based part masks on a photo-like render of Dudi."""
    h, s, v = hsv(img)
    cap = fg & (((h > 315) | (h < 8)) & (s > 0.3) & (v < 0.62) & (v > 0.18))
    return {'cap': cap}


def patch_mean(img, x, y, r=4):
    return img[y - r:y + r + 1, x - r:x + r + 1].reshape(-1, 3).mean(0)


def save_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2)


# ---------------------------------------------------------------- alignment
VIEW_GEOM = {}  # filled lazily: crown row, sole row, feet centre x (crop coords)


def view_geometry(view, a=None):
    """Crown (top of cap), sole and feet-centre of a turnaround view, in crop pixels."""
    if view in VIEW_GEOM:
        return VIEW_GEOM[view]
    a = load_sheet() if a is None else a
    c = crop(a, view)
    m = fg_mask(c)
    h, s, v = hsv(c)
    ys, xs = np.nonzero(m)
    sole = ys.max()
    upper = np.zeros_like(m)
    upper[:sole - 250] = True
    cap = m & upper & (((h > 315) | (h < 8)) & (s > 0.3) & (v < 0.62) & (v > 0.18))
    crown = np.nonzero(cap)[0].min()
    feet = m.copy()
    feet[:sole - 40] = False
    fx = np.nonzero(feet)[1]
    g = {'crown': int(crown), 'sole': int(sole), 'cx': float((fx.min() + fx.max()) / 2), 'H': int(sole - crown)}
    VIEW_GEOM[view] = g
    return g


def sheet_to_frame(view, px_per_unit, out_w, out_h, z_center, x_center=0.0, a=None):
    """Resample a sheet view into a frame where world (x, z) maps like an ortho render:
    col = out_w/2 + (x - x_center)*ppu, row = out_h/2 - (z - z_center)*ppu.
    Returns (rgb float array, mask bool array)."""
    a = load_sheet() if a is None else a
    g = view_geometry(view, a)
    c = crop(a, view)
    m = fg_mask(c)
    k = g['H'] / px_per_unit  # sheet px per output px
    rows = np.arange(out_h)
    cols = np.arange(out_w)
    z = z_center - (rows - out_h / 2) / px_per_unit
    x = x_center + (cols - out_w / 2) / px_per_unit
    sr = (g['sole'] - z * g['H']).round().astype(int)
    sc = (g['cx'] + x * g['H']).round().astype(int)
    R, C = np.meshgrid(sr, sc, indexing='ij')
    ok = (R >= 0) & (R < c.shape[0]) & (C >= 0) & (C < c.shape[1])
    out = np.zeros((out_h, out_w, 3)) + BG
    mk = np.zeros((out_h, out_w), bool)
    out[ok] = c[R[ok], C[ok]]
    mk[ok] = m[R[ok], C[ok]]
    return out, mk


def outline(mask):
    e = _erode(mask, 1)
    return mask & ~e
