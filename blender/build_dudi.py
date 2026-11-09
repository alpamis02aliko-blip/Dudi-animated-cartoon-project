"""Build Dudi in Blender 5 (bpy) and save build/dudi.blend.

    python blender/build_dudi.py [--stage body|all]
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import numpy as np
import bpy
from mathutils import Vector, Matrix
import spec as S
import build_body as BB
import face as F
import cap as CAP
import garments as G
from bl_util import (link, verts_np, set_corner_colors, principled, new_material, hex_lin, bvh_from_object)

OUT_DIR = os.path.join(REPO, 'build')


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.scale_length = 1.0
    coll = bpy.data.collections.new('Dudi')
    sc.collection.children.link(coll)
    return coll


def skin_material():
    m, nt = new_material('skin')
    N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial')
    bs = N.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Roughness'].default_value = 0.85
    bs.inputs['Sheen Weight'].default_value = 0.6
    bs.inputs['Sheen Roughness'].default_value = 0.4
    at = N.new('ShaderNodeAttribute')
    at.attribute_name = 'furcol'
    L.new(at.outputs['Color'], bs.inputs['Base Color'])
    L.new(bs.outputs[0], out.inputs[0])
    return m


def stage_body(coll):
    ob = BB.build_body_mesh(coll)
    co = verts_np(ob)
    reg, _ = BB.classify(co)
    ob['regions'] = list(reg.keys())
    col = BB.body_colors(co, reg)
    ob.data.materials.append(skin_material())
    set_corner_colors(ob, 'furcol', col)
    t = time.time()
    BB.carve_mouth(ob, coll)
    print('mouth boolean %.1fs, %d verts' % (time.time() - t, len(ob.data.vertices)))
    # colours again (boolean added verts; corner colours were interpolated, keep them)
    BB.add_body_shape_keys(ob)
    return ob


def stage_face(coll, body):
    bvh = bvh_from_object(body)
    parts = {}
    for side in 'LR':
        eye, lights = F.build_eye(side, coll)
        up = F.lid_mesh('lid_upper.' + side, side, True, coll, radius=0.0484, edge_deg=56.0, corner_drop=26.0)
        lo = F.lid_mesh('lid_lower.' + side, side, False, coll, radius=0.0490, edge_deg=54.0, corner_drop=20.0)
        up.data.materials.append(bpy.data.materials.get('lid_upper') or F.lid_material(S.PALETTE['fur'], 'lid_upper'))
        lo.data.materials.append(bpy.data.materials.get('lid_lower') or F.lid_material(S.PALETTE['fur'], 'lid_lower'))
        brow, brow_fn = F.build_brow(side, bvh, coll)
        brow.data.materials.append(bpy.data.materials.get('brow') or principled('brow', S.PALETTE['brow'], rough=0.8))
        parts[side] = dict(eye=eye, lights=lights, up=up, lo=lo, brow=brow, brow_fn=brow_fn)
    nose = F.build_nose(coll)
    parts['nose'] = nose
    return parts


def stage_cap(coll):
    mats = (principled('cap', S.PALETTE['cap'], rough=0.8, sheen=0.3),
            principled('cap_dark', '#2A0E14', rough=0.6),
            principled('metal', '#B0B0B0', rough=0.3, metallic=1.0))
    return CAP.build_cap(coll, *mats)


def stage_garments(coll):
    out = {}
    out['hoodie'] = G.build_hoodie(coll)
    out['hoodie'].data.materials.append(principled('hoodie', S.PALETTE['hoodie'], rough=0.85, sheen=0.4))
    out['jacket'] = G.build_jacket(coll)
    out['jacket'].data.materials.append(principled('denim', S.PALETTE['denim'], rough=0.8))
    out['hood'] = G.build_hood(coll, out['jacket'])
    out['hood'].data.materials.append(bpy.data.materials['hoodie'])
    out['pants'] = G.build_pants(coll)
    out['pants'].data.materials.append(principled('pants', S.PALETTE['pants'], rough=0.85))
    shoe_m = principled('sneaker', S.PALETTE['sneakers'], rough=0.8)
    for side in 'LR':
        sh = G.build_shoe(side, coll)
        sh.data.materials.append(shoe_m)
        out['shoe_' + side] = sh
    out['backpack'] = G.build_backpack(coll)
    out['backpack'].data.materials.append(principled('backpack', S.PALETTE['backpack'], rough=0.55))
    return out


def main():
    stage = 'all'
    if '--stage' in sys.argv:
        stage = sys.argv[sys.argv.index('--stage') + 1]
    t0 = time.time()
    coll = reset()
    body = stage_body(coll)
    face = stage_face(coll, body)
    cap = stage_cap(coll)
    clothes = stage_garments(coll)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, 'dudi.blend')
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print('saved %s in %.1fs' % (path, time.time() - t0))


if __name__ == '__main__':
    main()
