"""Small Blender helpers shared by the build and render scripts."""
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix


def srgb_to_linear(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def hex_lin(h, alpha=1.0):
    h = h.lstrip('#')
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(srgb_to_linear(rgb)) + (alpha,)


def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def mesh_object(name, verts, faces, coll=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(map(int, f)) for f in faces])
    me.validate(clean_customdata=False)
    me.update()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    return link(ob, coll)


def apply_modifiers(ob):
    """Bake the modifier stack into the mesh without operators."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def voxel_remesh(ob, size, adaptivity=0.0):
    m = ob.modifiers.new('remesh', 'REMESH')
    m.mode = 'VOXEL'
    m.voxel_size = size
    m.adaptivity = adaptivity
    m.use_smooth_shade = True
    apply_modifiers(ob)
    return ob


def recalc_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def verts_np(ob):
    n = len(ob.data.vertices)
    a = np.empty(n * 3, np.float64)
    ob.data.vertices.foreach_get('co', a)
    return a.reshape(n, 3)


def set_verts_np(ob, co):
    ob.data.vertices.foreach_set('co', np.asarray(co, np.float64).ravel())
    ob.data.update()


def normals_np(ob):
    me = ob.data
    n = len(me.vertices)
    a = np.empty(n * 3, np.float64)
    me.vertices.foreach_get('normal', a)
    return a.reshape(n, 3)


def poly_centers_np(ob):
    me = ob.data
    n = len(me.polygons)
    a = np.empty(n * 3, np.float64)
    me.polygons.foreach_get('center', a)
    return a.reshape(n, 3)


def set_corner_colors(ob, name, vert_rgb):
    """Write per-vertex linear RGB into a byte colour layer on face corners
    (the layer type Cycles also hands to particle hair)."""
    me = ob.data
    if name in me.color_attributes:
        me.color_attributes.remove(me.color_attributes[name])
    layer = me.color_attributes.new(name, 'BYTE_COLOR', 'CORNER')
    nl = len(me.loops)
    vi = np.empty(nl, np.int64)
    me.loops.foreach_get('vertex_index', vi)
    rgba = np.ones((nl, 4))
    rgba[:, :3] = np.clip(np.asarray(vert_rgb)[vi], 0, 1)
    layer.data.foreach_set('color', rgba.ravel())
    me.color_attributes.active_color = layer
    return layer


def vertex_group(ob, name, weights, threshold=1e-4):
    vg = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
    w = np.asarray(weights)
    idx = np.nonzero(w > threshold)[0]
    # group by rounded weight to cut API calls
    for wv in np.unique(np.round(w[idx], 3)):
        sel = idx[np.round(w[idx], 3) == wv]
        vg.add(sel.tolist(), float(wv), 'REPLACE')
    return vg


def new_material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    return m, nt


def principled(name, color_hex=None, rough=0.6, sheen=0.0, coat=0.0, spec=0.5, color_attr=None, normal_img=None,
               normal_scale=40.0, normal_strength=0.6, metallic=0.0):
    m, nt = new_material(name)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metallic
    bs.inputs['Specular IOR Level'].default_value = spec
    if sheen:
        bs.inputs['Sheen Weight'].default_value = sheen
    if coat:
        bs.inputs['Coat Weight'].default_value = coat
        bs.inputs['Coat Roughness'].default_value = 0.08
    if color_attr:
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_name = color_attr
        nt.links.new(at.outputs['Color'], bs.inputs['Base Color'])
    elif color_hex:
        bs.inputs['Base Color'].default_value = hex_lin(color_hex)
    if normal_img:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (normal_scale, normal_scale, normal_scale)
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = normal_img
        tx.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = normal_strength
        nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], tx.inputs['Vector'])
        nt.links.new(tx.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bs.inputs['Normal'])
    nt.links.new(bs.outputs[0], out.inputs[0])
    m['base_hex'] = color_hex or ''
    return m


def bvh_from_object(ob, world=True):
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    M = ob.matrix_world if world else Matrix.Identity(4)
    verts = [M @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)
