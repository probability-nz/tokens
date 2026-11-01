"""Blender: generate regular D4/D12 meshes and transfer their original artwork.
Run: blender -b --python-exit-code 1 --python scripts/assets/regular-dice.py -- d4 (or -- d12)
Original source files are retained for reproducible baking (no external assets).
"""

import bpy
import json
import math
from pathlib import Path
import sys
import numpy as np
from itertools import combinations

ROOT = Path(__file__).resolve().parents[2]
NAME = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "d4"
assert NAME in ("d4", "d12")
OUT = ROOT / f"src/assets/{NAME}/regular"
OUT.mkdir(exist_ok=True)
RADIUS = 3 * math.sqrt(2) / 4
BEVEL = 0.05
SEGMENTS = 6


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x * s for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def unit(a):
    return mul(a, 1 / math.sqrt(dot(a, a)))


if NAME == "d4":
    vertices = [
        mul(v, RADIUS)
        for v in [
            (0, 1, 0),
            (math.sqrt(2 / 3), -1 / 3, math.sqrt(2) / 3),
            (0, -1 / 3, -2 * math.sqrt(2) / 3),
            (-math.sqrt(2 / 3), -1 / 3, math.sqrt(2) / 3),
        ]
    ]
    face_normals = [mul(unit(v), -1) for v in vertices]
    faces = [[i for i in range(4) if i != opposite] for opposite in range(4)]
    inradius = RADIUS / 3
else:
    # Exact dodecahedral normals use the golden ratio. Keep the original
    # supporting-plane distance, replacing uneven source bevels, not the size.
    phi = (1 + math.sqrt(5)) / 2
    face_normals = [
        unit(n)
        for a in (-1, 1)
        for b in (-1, 1)
        for n in [(0, a * phi, b), (a, 0, b * phi), (a * phi, b, 0)]
    ]
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "align", Path(__file__).with_name("align-dice.py")
    )
    align_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(align_module)
    _, _, groups = align_module.geometry(ROOT / "src/assets/d12/source/d12.gltf")
    inradius = float(
        np.mean([np.mean(np.array(g["points"]) @ g["normal"]) for g in groups])
    )
    vertices = []
    for ids in combinations(range(12), 3):
        n = np.array([face_normals[i] for i in ids])
        if abs(np.linalg.det(n)) < 1e-8:
            continue
        point = np.linalg.solve(n, np.full(3, inradius))
        if max(np.array(face_normals) @ point) > inradius + 1e-8:
            continue
        if not any(np.linalg.norm(point - v) < 1e-8 for v in vertices):
            vertices.append(tuple(point))
    faces = [
        [i for i, v in enumerate(vertices) if abs(dot(n, v) - inradius) < 1e-8]
        for n in face_normals
    ]
    assert len(vertices) == 20 and all(len(f) == 5 for f in faces)
    BEVEL = 0.03
inner = [mul(v, 1 - BEVEL / inradius) for v in vertices]
edges = [
    (a, b)
    for a, b in combinations(range(len(vertices)), 2)
    if sum(a in f and b in f for f in faces) == 2
]
atlas = math.ceil(math.sqrt(len(faces) + len(edges) + len(vertices)))
positions = []
normals = []
uvs = []
indices = []


def vertex(p, n, uv, patch):
    i = len(positions)
    positions.append(p)
    normals.append(n)
    uvs.append(
        (
            (patch % atlas + 0.04 + 0.92 * uv[0]) / atlas,
            (patch // atlas + 0.04 + 0.92 * uv[1]) / atlas,
        )
    )
    return i


def triangle(a, b, c):
    if (
        dot(
            cross(sub(positions[b], positions[a]), sub(positions[c], positions[a])),
            add(add(normals[a], normals[b]), normals[c]),
        )
        < 0
    ):
        b, c = c, b
    indices.extend([a, b, c])


for patch, (corners, n) in enumerate(zip(faces, face_normals)):
    centre = mul(n, inradius)
    ps = [add(inner[i], mul(n, BEVEL)) for i in corners]
    u = unit(sub(ps[0], centre))
    v = cross(n, u)
    ps.sort(key=lambda p: math.atan2(dot(sub(p, centre), v), dot(sub(p, centre), u)))
    radius = max(math.sqrt(dot(sub(p, centre), sub(p, centre))) for p in ps)
    ids = [
        vertex(
            p,
            n,
            (
                0.5 + dot(sub(p, centre), u) / (2 * radius),
                0.5 + dot(sub(p, centre), v) / (2 * radius),
            ),
            patch,
        )
        for p in ps
    ]
    for i in range(1, len(ids) - 1):
        triangle(ids[0], ids[i], ids[i + 1])
for patch, (a, b) in enumerate(edges, len(faces)):
    n0, n1 = [face_normals[i] for i, f in enumerate(faces) if a in f and b in f]
    rows = []
    for step in range(SEGMENTS + 1):
        t = step / SEGMENTS
        n = unit(add(mul(n0, 1 - t), mul(n1, t)))
        rows.append(
            [
                vertex(add(inner[i], mul(n, BEVEL)), n, (u, t), patch)
                for i, u in [(a, 0), (b, 1)]
            ]
        )
    for p, q in zip(rows, rows[1:]):
        triangle(p[0], p[1], q[1])
        triangle(p[0], q[1], q[0])
for corner in range(len(vertices)):
    ns = [face_normals[i] for i, f in enumerate(faces) if corner in f]
    assert len(ns) == 3
    grid = {}
    for i in range(SEGMENTS + 1):
        for j in range(SEGMENTS + 1 - i):
            ws = ((SEGMENTS - i - j) / SEGMENTS, i / SEGMENTS, j / SEGMENTS)
            n = unit(tuple(sum(n[k] * w for n, w in zip(ns, ws)) for k in range(3)))
            grid[i, j] = vertex(
                add(inner[corner], mul(n, BEVEL)),
                n,
                ((i + j / 2) / SEGMENTS, j / SEGMENTS),
                len(faces) + len(edges) + corner,
            )
    for i in range(SEGMENTS):
        for j in range(SEGMENTS - i):
            triangle(grid[i, j], grid[i + 1, j], grid[i, j + 1])
            if i + j < SEGMENTS - 1:
                triangle(grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1])
# Cycles transfers the existing color/engraving to the new UVs and tangent frame.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(ROOT / f"src/assets/{NAME}/source/{NAME}.gltf"))
source = next(o for o in bpy.context.scene.objects if o.type == "MESH")
# The source sharp tetrahedron has a 1.5 high axis and a sqrt(3) base edge.
# Correct its height and centre before projecting its artwork onto the regular die.
if NAME == "d4":
    source.scale.z *= math.sqrt(8) / 3
    source.location.z += 0.225 * math.sqrt(8) / 3
mesh = bpy.data.meshes.new(f"Regular {NAME.upper()}")
coords = [(x, -z, y) for x, y, z in positions]
mesh.from_pydata(coords, [], [indices[i : i + 3] for i in range(0, len(indices), 3)])
mesh.update()
uv = mesh.uv_layers.new(name="UVMap")
for loop in mesh.loops:
    uv.data[loop.index].uv = uvs[loop.vertex_index]
for poly in mesh.polygons:
    poly.use_smooth = True
mesh.normals_split_custom_set_from_vertices([(x, -z, y) for x, y, z in normals])
target = bpy.data.objects.new(f"Regular {NAME.upper()}", mesh)
bpy.context.collection.objects.link(target)
mat = bpy.data.materials.new(NAME.upper())
mat.use_nodes = True
mat.use_backface_culling = True
target.data.materials.append(mat)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 1
scene.render.bake.use_selected_to_active = True
scene.render.bake.cage_extrusion = 0.15
scene.render.bake.max_ray_distance = 0.3
scene.render.bake.margin = 12
scene.render.bake.use_pass_direct = False
scene.render.bake.use_pass_indirect = False
scene.render.bake.use_pass_color = True
bpy.ops.object.select_all(action="DESELECT")
source.select_set(True)
target.select_set(True)
bpy.context.view_layer.objects.active = target
for kind, name, color in [
    ("DIFFUSE", NAME + "_diffuse", (1, 1, 1, 1)),
    ("NORMAL", NAME + "_normal", (0.5, 0.5, 1, 1)),
]:
    image = bpy.data.images.new(name, width=2048, height=2048, alpha=False)
    image.generated_color = color
    if kind == "NORMAL":
        image.colorspace_settings.name = "Non-Color"
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    mat.node_tree.nodes.active = node
    bpy.ops.object.bake(type=kind)
    image.filepath_raw = str(OUT / (name + ".png"))
    image.file_format = "PNG"
    image.save()
# Bake the already de-numbered source normal map onto the same regular mesh.
# This keeps the blank die's bevel shading without retaining engraved glyphs.
source_shader = source.data.materials[0].node_tree.nodes.get("Principled BSDF")
normal_map = source_shader.inputs["Normal"].links[0].from_node
source_texture = normal_map.inputs["Color"].links[0].from_node
source_texture.image = bpy.data.images.load(
    str(ROOT / f"src/assets/{NAME}/source/{NAME}-original-blank-normal.png")
)
source_texture.image.colorspace_settings.name = "Non-Color"
blank = bpy.data.images.new(
    NAME + "-blank-normal", width=2048, height=2048, alpha=False
)
blank.colorspace_settings.name = "Non-Color"
blank_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
blank_node.image = blank
mat.node_tree.nodes.active = blank_node
bpy.ops.object.bake(type="NORMAL")
blank.filepath_raw = str(OUT / (NAME + "-blank-normal.png"))
blank.file_format = "PNG"
blank.save()
# Export through Blender so UV V direction and tangent handedness match the
# baked tangent-space normal map. A geometry-only UV flip would invert bumps.
shader = mat.node_tree.nodes.get("Principled BSDF")
images = {
    Path(node.image.filepath_raw).stem: node
    for node in mat.node_tree.nodes
    if node.type == "TEX_IMAGE"
}
mat.node_tree.links.new(
    images[NAME + "_diffuse"].outputs["Color"], shader.inputs["Base Color"]
)
normal_node = mat.node_tree.nodes.new("ShaderNodeNormalMap")
mat.node_tree.links.new(
    images[NAME + "_normal"].outputs["Color"], normal_node.inputs["Color"]
)
mat.node_tree.links.new(normal_node.outputs["Normal"], shader.inputs["Normal"])
shader.inputs["Roughness"].default_value = 0.5
bpy.ops.object.select_all(action="DESELECT")
target.select_set(True)
bpy.context.view_layer.objects.active = target
bpy.ops.export_scene.gltf(
    filepath=str(OUT / (NAME + ".gltf")),
    export_format="GLTF_SEPARATE",
    use_selection=True,
    export_yup=True,
    export_tangents=True,
    export_image_format="AUTO",
    export_keep_originals=True,
)
document_path = OUT / (NAME + ".gltf")
document = json.loads(document_path.read_text())
document["asset"][
    "copyright"
] = "Garbo Succus; source artwork by Misha Tsyatsko. CC BY 4.0."
document_path.write_text(json.dumps(document, indent=2) + "\n")
print("Wrote regular", NAME, "geometry and rebaked color/normal maps", flush=True)
# The old bevel UVs can contain padding or stray ink. The new rounded bevels
# already have analytic smooth normals: keep their material white and their
# tangent-space normal neutral instead of projecting old bevel artifacts.
from PIL import Image

for suffix, fill in [
    ("_diffuse.png", (255, 255, 255)),
    ("_normal.png", (128, 128, 255)),
    ("-blank-normal.png", (128, 128, 255)),
]:
    path = OUT / (NAME + suffix)
    image = Image.open(path).convert("RGB")
    for patch in range(len(faces), atlas * atlas):
        x = patch % atlas
        y = patch // atlas
        image.paste(
            fill,
            (
                round(x * image.width / atlas),
                round((atlas - y - 1) * image.height / atlas),
                round((x + 1) * image.width / atlas),
                round((atlas - y) * image.height / atlas),
            ),
        )
    image.save(path)
