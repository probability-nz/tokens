# SPDX-License-Identifier: CC0-1.0
"""Shared mesh and image interchange for the CC0 tabletop generators."""
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

SETTINGS = json.loads((Path(__file__).resolve().parents[1] / "texture-settings.json").read_text())
ASSETS = Path(__file__).resolve().parents[2] / "assets"


def textures(directory, color, normal):
    """Write one AVIF albedo and one lossless WebP tangent-space normal map."""
    color.save(directory / "albedo.png")
    subprocess.run([
        "magick", "-limit", "thread", "1", str(directory / "albedo.png"), "-strip",
        "-define", "heic:speed=6", "-define", "heic:chroma=444", "-quality", str(SETTINGS["avifQuality"]),
        str(directory / "albedo.avif"),
    ], check=True)
    normal.save(directory / "normal.webp", lossless=True, method=4)
    names = []
    for filename in ("albedo.avif", "normal.webp"):
        path = directory / filename
        name = hashlib.sha256(path.read_bytes()).hexdigest()[:20] + path.suffix
        path.replace(directory / name)
        names.append(name)
    return names


def write_mesh(directory, slug, name, streams, images, material, bounds):
    positions, normals, uvs, tangents, indices = streams
    arrays = [np.asarray(stream, dtype="<f4") for stream in (positions, normals, uvs, tangents)]
    arrays.append(np.asarray(indices, dtype="<u2").reshape(-1))
    (directory / (slug + ".raw")).write_bytes(b"".join(a.tobytes() for a in arrays))
    recipe = dict(name=name, counts=[len(a) for a in arrays], images=images,
                  bounds=bounds, material=material)
    (directory / (slug + ".json")).write_text(json.dumps(recipe))
