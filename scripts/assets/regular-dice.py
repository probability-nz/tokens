"""Blender: generate consistently rounded regular dice meshes and transfer their original artwork.
Run: blender -b --python-exit-code 1 --python scripts/assets/regular-dice.py -- d4 (die, d4, d6, d8, d12 or d20)
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
assert NAME in ("die", "d4", "d6", "d8", "d12", "d20")
OUT = ROOT / f"src/assets/{NAME}/regular"
OUT.mkdir(exist_ok=True)
RADIUS = 3 * math.sqrt(2) / 4
catalog = json.loads((ROOT / "src/assets/catalog.json").read_text())
entry = next(e for e in catalog["pieces"] if e["src"] == f"{NAME}/{NAME}.gltf")
assert max(entry["scale"]) == min(entry["scale"])
# One physical fillet radius for every numbered/blank die, at catalog scale.
BEVEL = 0.0006 / entry["scale"][0]
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
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "align", ROOT / "scripts/assets/align-dice.py"
    )
    align_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(align_module)
    _, _, groups = align_module.geometry(ROOT / f"src/assets/{NAME}/source/{NAME}.gltf")
    inradius = float(
        np.mean([np.mean(np.array(g["points"]) @ g["normal"]) for g in groups])
    )
    if NAME in ("die", "d6"):
        face_normals = [
            tuple(sign if i == axis else 0 for i in range(3))
            for axis in range(3)
            for sign in (-1, 1)
        ]
    elif NAME == "d8":
        face_normals = [
            n
            for a in (-1, 1)
            for b in (-1, 1)
            for n in [
                (a * math.sqrt(2 / 3), b / math.sqrt(3), 0),
                (0, b / math.sqrt(3), a * math.sqrt(2 / 3)),
            ]
        ]
    elif NAME == "d12":
        phi = (1 + math.sqrt(5)) / 2
        face_normals = [
            unit(n)
            for a in (-1, 1)
            for b in (-1, 1)
            for n in [(0, a * phi, b), (a, 0, b * phi), (a * phi, b, 0)]
        ]
    else:
        # Exact icosahedron in the original north/south-pole orientation.
        ideal = [(0, 1, 0), (0, -1, 0)] + [
            (
                2
                / math.sqrt(5)
                * math.cos((2 * k + (0 if sign == 1 else 1)) * math.pi / 5),
                sign / math.sqrt(5),
                2
                / math.sqrt(5)
                * math.sin((2 * k + (0 if sign == 1 else 1)) * math.pi / 5),
            )
            for sign in (-1, 1)
            for k in range(5)
        ]
        face_normals = []
        for ids in combinations(range(12), 3):
            a, b, c = [ideal[i] for i in ids]
            n = unit(cross(sub(b, a), sub(c, a)))
            if dot(n, a) < 0:
                n = mul(n, -1)
            if max(dot(n, q) - dot(n, a) for q in ideal) > 1e-8:
                continue
            if not any(
                np.linalg.norm(np.array(n) - old) < 1e-8 for old in face_normals
            ):
                face_normals.append(n)
        assert len(face_normals) == 20
    vertices = []
    for ids in combinations(range(len(face_normals)), 3):
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
    centre = unit(tuple(sum(n[k] for n in ns) for k in range(3)))
    u = unit(sub(ns[0], mul(centre, dot(ns[0], centre))))
    v = cross(centre, u)
    ns.sort(key=lambda n: math.atan2(dot(n, v), dot(n, u)))
    # A fan supports the 3/4/5 faces meeting at cube/octahedron/icosahedron corners.
    for a, b in zip(ns, ns[1:] + ns[:1]):
        triangle_normals = [centre, a, b]
        grid = {}
        for i in range(SEGMENTS + 1):
            for j in range(SEGMENTS + 1 - i):
                ws = ((SEGMENTS - i - j) / SEGMENTS, i / SEGMENTS, j / SEGMENTS)
                n = unit(
                    tuple(
                        sum(n[k] * w for n, w in zip(triangle_normals, ws))
                        for k in range(3)
                    )
                )
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
for kind, name, color in [("DIFFUSE", NAME + "_diffuse", (1, 1, 1, 1))]:
    image = bpy.data.images.new(name, width=2048, height=2048, alpha=False)
    image.generated_color = color
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    mat.node_tree.nodes.active = node
    bpy.ops.object.bake(type=kind)
    image.filepath_raw = str(OUT / (name + ".png"))
    image.file_format = "PNG"
    image.save()
# Analytic mesh normals supply all edge/corner rounding. Do not bake the old
# bevels onto the new flat faces; final engraving is derived from final ink.
from PIL import Image

for suffix in ("_normal", "-blank-normal"):
    path = OUT / (NAME + suffix + ".png")
    Image.new("RGB", (2048, 2048), (128, 128, 255)).save(path)
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(str(path))
    node.image.colorspace_settings.name = "Non-Color"
# Export through Blender so UV V direction and tangent handedness match the
# baked tangent-space normal map. A geometry-only UV flip would invert bumps.
shader = mat.node_tree.nodes.get("Principled BSDF")
images = {
    Path(node.image.filepath_raw or node.image.filepath).stem: node
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
