"""Export Photoshop-friendly PNG layers and a labelled UV reference for every die."""

import json
from pathlib import Path
from collections import Counter
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "src/assets"
SIZE = 2048
try:
    FONT = ImageFont.truetype("DejaVuSans.ttf", 15)
except OSError:
    # Pillow bundles this font; generation must not depend on system fonts.
    FONT = ImageFont.load_default(size=15)
for name in ("die", "d4", "d6", "d8", "d10", "d12", "d20"):
    folder = ASSETS / name
    doc = json.loads((folder / "regular" / f"{name}.gltf").read_text())
    layout = json.loads((folder / "regular/uv-layout.json").read_text())

    def read(index, width, dtype):
        accessor = doc["accessors"][index]
        view = doc["bufferViews"][accessor["bufferView"]]
        data = (folder / "regular" / doc["buffers"][view["buffer"]]["uri"]).read_bytes()
        scalar = np.dtype(dtype).itemsize
        return np.ndarray(
            (accessor["count"], width),
            dtype=dtype,
            buffer=data,
            offset=view.get("byteOffset", 0) + accessor.get("byteOffset", 0),
            strides=(view.get("byteStride", width * scalar), scalar),
        )

    primitive = doc["meshes"][0]["primitives"][0]
    uv = read(primitive["attributes"]["TEXCOORD_0"], 2, "<f4")
    accessor = doc["accessors"][primitive["indices"]]
    indices = read(
        primitive["indices"], 1, {5123: "<u2", 5125: "<u4"}[accessor["componentType"]]
    ).reshape(-1, 3)
    guide = Image.new("RGBA", (SIZE, SIZE))
    draw = ImageDraw.Draw(guide)
    columns = layout["columns"]
    # Count geometric UV edges, so the guide shows island boundaries rather than
    # triangulation diagonals that users could mistake for paint seams.
    edges = Counter()
    for triangle in uv[indices]:
        points = [tuple(np.round(p * SIZE, 3)) for p in triangle]
        for a, b in zip(points, points[1:] + points[:1]):
            edges[tuple(sorted((a, b)))] += 1
    for (a, b), count in edges.items():
        if count == 1:
            draw.line((a, b), fill=(0, 130, 210, 220), width=2)
    for slot, patch in enumerate(layout["patches"]):
        x = (slot % columns) * SIZE / columns
        y = (slot // columns) * SIZE / columns
        draw.text(
            (round(x + 5), round(y + 3)),
            patch["label"],
            font=FONT,
            fill=(150, 50, 170, 255),
        )
    out = folder / "paint"
    out.mkdir(exist_ok=True)
    guide.save(out / "uv-guide.png")
    blank = Image.new("RGB", (SIZE, SIZE), "white")
    blank.save(out / "blank.png")
    ink = Image.open(folder / "centered" / f"{name}_diffuse.png").convert("RGB")
    ink.save(out / "numbered.png")
    reference = ink.convert("RGBA")
    reference.alpha_composite(guide)
    reference.convert("RGB").save(out / "reference.png")
    (out / "README.txt").write_text("""DICE PAINTING TEMPLATE — 2048 × 2048 PNG

Open blank.png or numbered.png in Photoshop, Krita, GIMP, or Affinity.
Place uv-guide.png above it as a separate layer, aligned at (0, 0).
Paint on layers below the guide. Blue lines are the physical island boundaries.
Extend your colour slightly beyond those lines to avoid filtering seams.
Hide the guide before exporting a flat PNG at the original square dimensions.
reference.png is for orientation only; its labels must not appear in the export.

Faces are ordered left to right, then top to bottom. They are oriented to match
that face's reading direction in Play. D4 has three corner numbers per face:
“Opposite N” means the physical face opposite vertex N, not a single printed N.
Each island includes the flat face and its share of the rounded rim.
There are no separate edge or corner pieces to paint. Seams meet halfway
around the rounded edges; match adjacent face colours for continuous patterns.
Blank and numbered variants use exactly the same UV layout and geometry.

Use your PNG as the model's base-colour texture. For custom artwork, remove the
original numbered normal map or replace it with a neutral normal map, otherwise
the original numbers will still appear engraved beneath your artwork.
The blank model already has a neutral normal map.
""")
    print(name, "painting templates exported")
