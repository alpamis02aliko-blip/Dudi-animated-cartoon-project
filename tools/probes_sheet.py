"""Colour probe points on the master sheet (sheet pixel coords) and their measured RGB."""
import numpy as np
from PIL import Image, ImageDraw
from sheetlib import load_sheet, patch_mean, save_json, REPO
import os

# name: (view, x, y, radius, kind)
PROBES = {
    'fur_forehead':     ('front', 230, 447, 4, 'fur'),
    'fur_cheek_orange': ('front', 150, 480, 4, 'fur'),
    'fur_muzzle_cream': ('front', 160, 525, 4, 'fur'),
    'fur_cheek_cream':  ('front', 300, 532, 4, 'fur'),
    'fur_ear_inner':    ('front', 122, 372, 3, 'fur'),
    'fur_ear_tip_back': ('back', 1150, 325, 4, 'fur'),
    'fur_nape':         ('back', 1160, 500, 4, 'fur'),
    'fur_tail_orange':  ('side', 1060, 730, 5, 'fur'),
    'fur_tail_cream':   ('side', 1075, 590, 5, 'fur'),
    'fur_hand':         ('front', 133, 748, 3, 'fur'),
    'cap':              ('front', 180, 400, 4, 'cloth'),
    'denim':            ('front', 320, 690, 4, 'cloth'),
    'hoodie':           ('front', 233, 700, 4, 'cloth'),
    'pants':            ('front', 200, 810, 4, 'cloth'),
    'sneaker':          ('front', 205, 872, 2, 'cloth'),
    'backpack':         ('back', 1240, 630, 4, 'cloth'),
    'nose':             ('front', 230, 506, 2, 'face'),
    'brow':             ('front', 188, 433, 1, 'face'),
}

if __name__ == '__main__':
    a = load_sheet()
    out = {}
    im = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for k, (view, x, y, r, kind) in PROBES.items():
        c = patch_mean(a, x, y, r)
        out[k] = {'view': view, 'xy': [x, y], 'r': r, 'kind': kind, 'rgb': [round(float(v), 1) for v in c],
                  'hex': '#%02X%02X%02X' % tuple(int(round(v)) for v in c)}
        d.rectangle([x - r - 2, y - r - 2, x + r + 2, y + r + 2], outline=(0, 255, 0), width=2)
        d.text((x + r + 4, y - 6), k, fill=(0, 120, 0))
        print(f'{k:18s} {view:6s} {out[k]["hex"]} {out[k]["rgb"]}')
    save_json(os.path.join(REPO, 'reference', 'sheet_probes.json'), out)
    im.crop((0, 250, 1438, 950)).save(os.path.join(os.environ.get('SCRATCH', '/tmp'), 'probe_marks.png'))
