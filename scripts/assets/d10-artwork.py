"""Reuse the set's original D12 numeral artwork on the D10's kite UV islands.

Digits 1–9 come from their corresponding D12 faces; zero comes from face 10.
Keep the original 6/9 dots and antialiasing. No substitute font is used.
"""

import importlib.util
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "center", Path(__file__).with_name("center-dice-labels.py")
)
center = importlib.util.module_from_spec(spec)
spec.loader.exec_module(center)
catalog = json.loads((ROOT / "src/assets/catalog.json").read_text())["pieces"]
source_entry = next(e for e in catalog if e["name"] == "D12")
source_folder, source_faces = center.face_uvs("d12")
source = Image.open(source_folder / "d12_diffuse.png").convert("RGB")
labels = Image.fromarray(center.label_mask(source))
folder, target_faces = center.face_uvs("d10")
entry = next(e for e in catalog if e["name"] == "D10")
output = Image.new("RGB", (2048, 2048), "white")
for face in entry["faces"]:
    label = face["name"]
    source_pose = next(
        f
        for f in source_entry["faces"]
        if f["name"] == ("10" if label == "0" else label)
    )
    rotation = center.align.matrix(source_pose["rotation"])
    centre, polygon, _ = max(source_faces, key=lambda f: (rotation @ f[2])[1])
    box, inside, _ = center.face_region(centre, polygon, source.size, 1.0)
    ink = np.asarray(labels.crop(box)) & inside
    if label == "0":
        # Select the rightmost substantial connected glyph from the printed 10.
        components, _ = ndimage.label(ink)
        sizes = np.bincount(components.ravel())
        sizes[0] = 0
        candidates = [i for i in range(1, len(sizes)) if sizes[i] > sizes.max() * 0.1]
        component = max(candidates, key=lambda i: np.nonzero(components == i)[1].mean())
        ink = components == component
    # Preserve grayscale antialiasing, without copying neighbouring glyphs.
    keep = ndimage.binary_dilation(ink, iterations=2)
    pixels = np.array(source.crop(box))
    pixels[~keep] = 255
    yy, xx = np.nonzero(keep)
    glyph = Image.fromarray(pixels).crop(
        (xx.min(), yy.min(), xx.max() + 1, yy.max() + 1)
    )
    rotation = center.align.matrix(face["rotation"])
    point, polygon, _ = max(target_faces, key=lambda f: (rotation @ f[2])[1])
    # Match the set's proportions; common physical height is normalized by the
    # shared centering pass. The source's dot stays attached to its numeral.
    height = 140
    glyph = glyph.resize(
        (round(glyph.width * height / glyph.height), height), Image.Resampling.LANCZOS
    )
    x, y = point * np.array(output.size) - 0.5
    output.paste(glyph, (round(x - glyph.width / 2), round(y - glyph.height / 2)))
output.save(folder / "d10_diffuse.png")
