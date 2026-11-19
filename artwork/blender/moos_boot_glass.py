"""MoOS boot "Liquid Glass" scene for Blender (run headless, never in the image).

The owner's mark is kept exactly: its own cleaned colour and silhouette are the
emblem texture. Blender adds what the flat trace lacks: rounded glass bevels,
a clear coat that catches studio light, a glass bezel behind the mark, a sheen
that flows over it, liquid glass droplets and a glint. Every object is built
procedurally here, so the scene is reviewable source rather than an opaque
.blend; --save-blend writes editable copies for the owner.

Layers (host pipeline: artwork/generate_boot_glass.py):
  emblem   transparent RGBA — the improved mark (the boot hero)
  bezel    on black, keyed — glass ring and body behind the mark
  sheen    on black, keyed — dome reflections drawn over the mark
  drop-N   on black, keyed — tinted liquid glass droplets
(The glint is a tiny deterministic sprite made by the host pipeline.)

Usage:
  blender -b --factory-startup -P artwork/blender/moos_boot_glass.py -- \
      --out DIR --maps DIR [--layers ...] [--samples N] [--save-blend DIR]
"""

from __future__ import annotations

import argparse
import os
import sys

import bpy

CYAN = "#20D6F8"
BLUE = "#1647B9"
VIOLET = "#743AE2"
EMBLEM_RADIUS = 0.96      # the cleaned mark's radius in scene units (plane 2x2)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="moos_boot_glass.py")
    parser.add_argument("--out", required=True)
    parser.add_argument("--maps", required=True, help="emblem-colour.png and emblem-height.png")
    parser.add_argument("--layers", default="emblem,bezel,sheen,drops")
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--save-blend", default="")
    return parser.parse_args(argv)


def linear(hex_colour: str, alpha: float = 1.0):
    value = hex_colour.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(value[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, alpha)


def reset(size, samples, transparent=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.seed = 1173
    scene.cycles.max_bounces = 12
    scene.cycles.transmission_bounces = 12
    scene.cycles.glossy_bounces = 6
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent
    scene.render.dither_intensity = 0.0
    settings = scene.render.image_settings
    settings.file_format = "PNG"
    settings.color_mode = "RGBA" if transparent else "RGB"
    settings.color_depth = "16" if transparent else "8"
    settings.compression = 15
    for transform in ("Khronos PBR Neutral", "Standard"):
        try:
            scene.view_settings.view_transform = transform
            break
        except TypeError:
            continue
    world = bpy.data.worlds.new("Studio dark")
    scene.world = world
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0, 0, 0, 1)
    background.inputs["Strength"].default_value = 0.0
    return scene


def link(*objects):
    for obj in objects:
        bpy.context.scene.collection.objects.link(obj)


def camera(scale):
    data = bpy.data.cameras.new("Camera")
    data.type = "ORTHO"
    data.ortho_scale = scale
    obj = bpy.data.objects.new("Camera", data)
    obj.location = (0, 0, 20)
    link(obj)
    bpy.context.scene.camera = obj


def area_light(name, location, target, size, power, colour="#FFFFFF", shape="DISK", size_y=None):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = shape
    data.size = size
    if size_y is not None:
        data.size_y = size_y
    data.energy = power
    data.color = linear(colour)[:3]
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    direction = [t - l for t, l in zip(target, location)]
    obj.rotation_euler = _look_rotation(direction)
    link(obj)
    return obj


def _look_rotation(direction):
    from mathutils import Vector
    return Vector(direction).to_track_quat("-Z", "Y").to_euler()


def studio(scale=1.0, rim=1.0, key=1.0, fill=1.0):
    """Key softbox upper-left, strip highlight above, brand rims, low fill."""
    area_light("Key", (-3.2 * scale, 3.4 * scale, 4.0 * scale), (0, 0, 0), 3.2 * scale,
               340 * key * scale ** 2)
    area_light("Strip", (0.6 * scale, 4.2 * scale, 2.2 * scale), (0, 0, 0), 5.0 * scale,
               200 * key * scale ** 2, shape="RECTANGLE", size_y=0.35 * scale)
    if rim:
        area_light("Cyan rim", (4.0 * scale, -0.6 * scale, 1.4 * scale), (0, 0, 0), 2.0 * scale,
                   300 * rim * scale ** 2, CYAN)
        area_light("Violet rim", (-3.6 * scale, -3.0 * scale, 1.2 * scale), (0, 0, 0), 2.0 * scale,
                   280 * rim * scale ** 2, VIOLET)
    if fill:
        area_light("Fill", (0, -2.5 * scale, 6.0 * scale), (0, 0, 0), 6.0 * scale,
                   30 * fill * scale ** 2, "#BFD6FF")


def material(name):
    mat = bpy.data.materials.new(name)
    tree = mat.node_tree
    principled = tree.nodes.get("Principled BSDF") or tree.nodes.new("ShaderNodeBsdfPrincipled")
    return mat, tree, principled


def glass(name, tint="#FFFFFF", roughness=0.04, ior=1.45):
    mat, tree, principled = material(name)
    principled.inputs["Base Color"].default_value = linear(tint)
    principled.inputs["Transmission Weight"].default_value = 1.0
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["IOR"].default_value = ior
    principled.inputs["Coat Weight"].default_value = 0.6
    principled.inputs["Coat Roughness"].default_value = 0.02
    return mat


def liquid_edge(name, tint, edge_strength, gloss_roughness=0.05):
    """Liquid Glass on black: clear centre, Fresnel-lit tinted edge, glossy skin."""
    mat = bpy.data.materials.new(name)
    tree = mat.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    weight = tree.nodes.new("ShaderNodeLayerWeight")
    weight.inputs["Blend"].default_value = 0.35
    edge = tree.nodes.new("ShaderNodeMath")
    edge.operation = "POWER"
    edge.inputs[1].default_value = 1.6
    tree.links.new(weight.outputs["Facing"], edge.inputs[0])
    strength = tree.nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    strength.inputs[1].default_value = edge_strength
    tree.links.new(edge.outputs[0], strength.inputs[0])
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = linear(tint)
    tree.links.new(strength.outputs[0], emission.inputs["Strength"])
    gloss = tree.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = gloss_roughness
    fresnel = tree.nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.45
    black = tree.nodes.new("ShaderNodeEmission")
    black.inputs["Strength"].default_value = 0.0
    skin = tree.nodes.new("ShaderNodeMixShader")
    tree.links.new(fresnel.outputs[0], skin.inputs[0])
    tree.links.new(black.outputs[0], skin.inputs[1])
    tree.links.new(gloss.outputs[0], skin.inputs[2])
    total = tree.nodes.new("ShaderNodeAddShader")
    tree.links.new(skin.outputs[0], total.inputs[0])
    tree.links.new(emission.outputs[0], total.inputs[1])
    tree.links.new(total.outputs[0], output.inputs["Surface"])
    return mat


def render(scene, args, name):
    path = os.path.join(args.out, f"{name}.png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    if args.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(args.save_blend, f"moos-boot-{name}.blend"),
                                    check_existing=False)
    print(f"MOOS_GLASS_RENDERED {name} {path}")


def plane(name, size, mat, z=0.0):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def disc(name, radius, depth, bevel, mat, z=0.0, vertices=256):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=(0, 0, z))
    obj = bpy.context.active_object
    obj.name = name
    modifier = obj.modifiers.new("Bevel", "BEVEL")
    modifier.width = bevel
    modifier.segments = 10
    modifier.limit_method = "ANGLE"
    obj.modifiers.new("Smooth", "WEIGHTED_NORMAL")
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.data.materials.append(mat)
    return obj


def dome(name, radius, height, mat, z=0.0):
    """A shallow lens cap: a squashed UV sphere's upper half."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=radius, location=(0, 0, z))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (1.0, 1.0, height / radius)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.data.materials.append(mat)
    return obj


# ── layers ─────────────────────────────────────────────────────────────────
def emblem(args):
    scene = reset((1280, 1280), args.samples, transparent=True)
    scene.view_settings.view_transform = "Standard"   # brand colours exactly
    camera(2.0)
    studio(key=0.65, fill=0)
    mat, tree, principled = material("MoOS mark — glass coat")
    colour = tree.nodes.new("ShaderNodeTexImage")
    colour.image = bpy.data.images.load(os.path.join(args.maps, "emblem-colour.png"))
    colour.interpolation = "Cubic"
    height = tree.nodes.new("ShaderNodeTexImage")
    height.image = bpy.data.images.load(os.path.join(args.maps, "emblem-height.png"))
    height.image.colorspace_settings.name = "Non-Color"
    height.interpolation = "Cubic"
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 0.035
    tree.links.new(height.outputs["Color"], bump.inputs["Height"])
    soft = tree.nodes.new("ShaderNodeBump")
    soft.inputs["Strength"].default_value = 0.55
    soft.inputs["Distance"].default_value = 0.035
    tree.links.new(height.outputs["Color"], soft.inputs["Height"])
    # The mark keeps its own colour as light; the coat only adds glass.
    dim = tree.nodes.new("ShaderNodeVectorMath")
    dim.operation = "SCALE"
    dim.inputs["Scale"].default_value = 0.22
    tree.links.new(colour.outputs["Color"], dim.inputs[0])
    tree.links.new(dim.outputs["Vector"], principled.inputs["Base Color"])
    tree.links.new(colour.outputs["Alpha"], principled.inputs["Alpha"])
    tree.links.new(colour.outputs["Color"], principled.inputs["Emission Color"])
    principled.inputs["Emission Strength"].default_value = 1.0
    principled.inputs["Roughness"].default_value = 0.42
    principled.inputs["Metallic"].default_value = 0.0
    principled.inputs["Coat Weight"].default_value = 1.0
    principled.inputs["Coat Roughness"].default_value = 0.05
    principled.inputs["Coat IOR"].default_value = 1.5
    tree.links.new(soft.outputs["Normal"], principled.inputs["Normal"])
    tree.links.new(bump.outputs["Normal"], principled.inputs["Coat Normal"])
    plane("Mark", 2.0, mat)
    render(scene, args, "emblem")


def bezel(args):
    scene = reset((1024, 1024), args.samples)
    camera(2.0 * 1.3)
    studio(rim=1.2, key=1.4, fill=0)
    body = glass("Bezel glass", "#E6F6FF", roughness=0.12)
    disc("Bezel", EMBLEM_RADIUS * 1.16, 0.16, 0.075, body, z=-0.12)
    render(scene, args, "bezel")


def sheen(args):
    scene = reset((1024, 1024), args.samples)
    camera(2.0 * 1.3)
    # One soft window upper-left draws the classic glass crescent; a faint
    # low counter-light traces the lower rim. Nothing else reflects.
    area_light("Window", (-1.7, 2.4, 2.6), (0, 0, 0), 4.2, 300, shape="ELLIPSE", size_y=2.0)
    area_light("Counter", (2.0, -2.6, 0.9), (0, 0, 0), 2.4, 70, "#9FE8FF", shape="ELLIPSE", size_y=0.6)
    lens = liquid_edge("Dome skin", "#8FDFFF", 0.0, gloss_roughness=0.09)
    dome("Dome", EMBLEM_RADIUS * 1.08, 0.34, lens, z=0.0)
    render(scene, args, "sheen")


def drops(args):
    for index, tint in enumerate((CYAN, "#3A7BFF", VIOLET), start=1):
        scene = reset((256, 256), args.samples)
        camera(2.4)
        area_light("Window", (-1.5, 2.0, 2.4), (0, 0, 0), 1.6, 160, shape="DISK")
        bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=0.86, location=(0, 0, 0))
        drop = bpy.context.active_object
        drop.scale = (1.0, 1.0, 0.82)
        for polygon in drop.data.polygons:
            polygon.use_smooth = True
        drop.data.materials.append(liquid_edge(f"Drop {index}", tint, 2.4))
        render(scene, args, f"drop-{index}")


def main():
    args = parse_args()
    os.makedirs(args.out, exist_ok=True)
    if args.save_blend:
        os.makedirs(args.save_blend, exist_ok=True)
    table = dict(emblem=emblem, bezel=bezel, sheen=sheen, drops=drops)
    layers = [layer.strip() for layer in args.layers.split(",") if layer.strip()]
    for layer in layers:
        if layer not in table:
            raise SystemExit(f"unknown layer {layer!r}")
        table[layer](args)
    print("MOOS_GLASS_COMPLETE", ",".join(layers))


if __name__ == "__main__":
    main()
