"""Center numeral artwork and rebuild matching engraving on each planar die face.

Run before prepare-assets.mjs. UVs, meshes and face ordering stay intact;
centered/ contains reproducible maps rendered from the bundled font.
D4 retains shared corner anchors; the classic die keeps its original pip layout.
"""

import importlib.util
import json
from pathlib import Path
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
from dice_style import (
    ENGRAVING_ROUNDING_MM,
    ENGRAVING_SMOOTHING_MM,
    ENGRAVING_DEPTH_MM,
    PIP_DEPTH_MM,
)

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "src/assets"
NAMES = ("d4", "d6", "d8", "d10", "d12", "d20")
spec = importlib.util.spec_from_file_location(
    "align", Path(__file__).with_name("align-dice.py")
)
align = importlib.util.module_from_spec(spec)
spec.loader.exec_module(align)


def hull(points):
    points = sorted(set(map(tuple, points)))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def half(values):
        result = []
        for point in values:
            while len(result) >= 2 and cross(result[-2], result[-1], point) <= 0:
                result.pop()
            result.append(point)
        return result

    return np.array(half(points)[:-1] + half(points[::-1])[:-1])


def face_uvs(name, with_frames=False):
    folder = ASSETS / name / "regular"
    path = folder / f"{name}.gltf"
    doc, positions, groups = align.geometry(path)
    buffers = [(folder / b["uri"]).read_bytes() for b in doc["buffers"]]

    def read(index):
        a = doc["accessors"][index]
        v = doc["bufferViews"][a["bufferView"]]
        count = {"VEC2": 2, "SCALAR": 1}[a["type"]]
        fmt = "<" + {5126: "f", 5123: "H", 5125: "I"}[a["componentType"]] * count
        return np.array(
            [
                struct.unpack_from(
                    fmt,
                    buffers[v["buffer"]],
                    v.get("byteOffset", 0)
                    + a.get("byteOffset", 0)
                    + i * v.get("byteStride", struct.calcsize(fmt)),
                )
                for i in range(a["count"])
            ]
        )

    primitive = doc["meshes"][0]["primitives"][0]
    uv = read(primitive["attributes"]["TEXCOORD_0"])
    indices = read(primitive["indices"]).astype(int).reshape(-1, 3)
    tri = positions[indices]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = np.linalg.norm(normals, axis=1)
    normals /= np.maximum(area[:, None], 1e-20)
    if np.prod(doc["nodes"][0].get("scale", [1, 1, 1])) < 0:
        normals *= -1
    faces = []
    for group in groups:
        selected = (np.linalg.norm(normals - group["normal"], axis=1) < 1e-3) & (
            area > area.max() * 0.1
        )
        triangles = uv[indices[selected]]
        # An area-weighted UV centroid maps exactly to the planar face centre.
        centre = np.average(triangles.mean(axis=1), axis=0, weights=area[selected])
        face = (centre, hull(triangles.reshape(-1, 2)), group["normal"])
        if with_frames:
            uv_points = triangles.reshape(-1, 2)
            frame = np.linalg.lstsq(
                np.c_[uv_points, np.ones(len(uv_points))],
                tri[selected].reshape(-1, 3),
                rcond=None,
            )[0]
            face = (*face, frame)
        faces.append(face)
    return folder, faces


def face_region(centre, polygon, size, inset=0.96):
    dimensions = np.array(size)
    centre = centre * dimensions - 0.5
    polygon = polygon * dimensions - 0.5
    minimum = np.floor(polygon.min(axis=0)).astype(int).clip(0)
    maximum = np.ceil(polygon.max(axis=0)).astype(int)
    maximum = np.minimum(maximum, dimensions - 1)
    box = (*minimum, *(maximum + 1))
    mask = Image.new("L", tuple(maximum - minimum + 1))
    # Exclude the dark atlas background and bevel perimeter from label detection.
    inner = centre + inset * (polygon - centre)
    ImageDraw.Draw(mask).polygon([tuple(p - minimum) for p in inner], fill=255)
    return tuple(map(int, box)), np.asarray(mask) > 0, centre - minimum


def label_mask(image, threshold=100):
    dark = np.asarray(image).max(axis=2) < threshold
    components, _ = ndimage.label(dark)
    sizes = np.bincount(components.ravel())
    keep = (sizes > 2) & (sizes < dark.size * 0.04)
    keep[0] = False
    keep[
        np.unique(
            np.concatenate(
                (components[0], components[-1], components[:, 0], components[:, -1])
            )
        )
    ] = False
    return keep[components]


def engraving_normal(color, blank, texels_per_mm=None, *, spherical_pips=False):
    """Derive rounded recessed strokes from the final ink without print/normal drift.

    The exported Blender bitangent opposes increasing atlas rows (verified
    against the mesh in test_paint_uvs). Negative height inside the ink gives
    a recess, with opposite signs for X/Y slopes.
    """
    ink = label_mask(color)
    density = color.width / 16 if texels_per_mm is None else texels_per_mm
    if spherical_pips:
        # A circular pip is a spherical cap, not a wide numeral stroke. Fit
        # each printed disc so its entire floor curves continuously to centre.
        height = np.zeros(ink.shape, dtype=float)
        components, _ = ndimage.label(ink)
        for label, region in enumerate(ndimage.find_objects(components), 1):
            if region is None:
                continue
            mask = components[region] == label
            y, x = np.nonzero(mask)
            cx, cy = x.mean(), y.mean()
            aperture = np.sqrt(mask.sum() / np.pi)
            depth = min(PIP_DEPTH_MM * density, aperture * 0.8)
            sphere_radius = (aperture**2 + depth**2) / (2 * depth)
            yy, xx = np.indices(mask.shape)
            radial_squared = (xx - cx) ** 2 + (yy - cy) ** 2
            bowl = (
                sphere_radius
                - depth
                - np.sqrt(np.maximum(sphere_radius**2 - radial_squared, 0))
            )
            height[region] = np.minimum(bowl, 0)
    else:
        # Distance grows inward from the antialiased ink boundary. A rounded scoop
        # continues curving through the stroke instead of ending at a flat lip.
        distance = np.maximum(ndimage.distance_transform_edt(ink) - 0.5, 0)
        radius = ENGRAVING_ROUNDING_MM * density
        height = -ENGRAVING_DEPTH_MM * density * np.tanh(distance / radius)
    # Round the rim and medial-axis joins, avoiding staircase highlights and
    # sharp creases where two sides of a narrow numeral stroke meet.
    height = ndimage.gaussian_filter(
        height, max(0.75, ENGRAVING_SMOOTHING_MM * density), truncate=3
    )
    dy, dx = np.gradient(height)
    base = np.asarray(blank).astype(float) / 127.5 - 1
    # Encoded neutral normals use 128, so remove their half-step bias.
    base[..., :2] = (np.asarray(blank)[..., :2].astype(float) - 128) / 127
    z = np.maximum(base[..., 2], 0.05)
    normal = np.stack(
        (base[..., 0] / z - dx, base[..., 1] / z + dy, np.ones_like(dx)), axis=-1
    )
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    encoded = np.rint((normal + 1) * 127.5).clip(0, 255).astype("uint8")
    # Preserve exact neutral pixels outside the groove and its smoothed rim.
    changed = (dx != 0) | (dy != 0)
    output = np.array(blank)
    output[changed] = encoded[changed]
    return Image.fromarray(output)


def center(name):
    folder, faces = face_uvs(name, True)
    normal = Image.open(folder / f"{name}_normal.png").convert("RGB")
    entry = next(
        e
        for e in json.loads((ASSETS / "catalog.json").read_text())["pieces"]
        if e["name"] == ("Classic die" if name == "die" else name.upper())
    )
    if name == "die":
        output_color = (
            Image.open(folder / "die_diffuse.png")
            .convert("RGB")
            .resize(normal.size, Image.Resampling.LANCZOS)
        )
    else:
        from dice_font import render

        output_color = render(name, faces, entry, align.matrix, normal.size)
        # Keep a reproducible source atlas for authoring and existing tools.
        output_color.save(folder / f"{name}_diffuse.png")
    out = ASSETS / name / "centered"
    out.mkdir(exist_ok=True)
    # Atlas backgrounds are not physical face borders. Black outside each
    # island bleeds into face/bevel pixels through filtering and coarse mips.
    # Keep the complete antialiased artwork, with white padding everywhere else.
    keep = ndimage.binary_dilation(label_mask(output_color, 180), iterations=2)
    clean = np.array(output_color)
    clean[~keep] = 255
    output_color = Image.fromarray(clean)
    output_color.save(out / f"{name}_diffuse.png")
    if name in ("die", *NAMES):
        # Analytic mesh normals describe flat faces and the shared round bevels.
        # Rebaked old face-edge shading would make the regular faces look inset.
        blank = Image.new("RGB", normal.size, (128, 128, 255))
    # One physical engraving profile, accounting for each atlas's texel density.
    texels_per_mm = np.median(
        [
            output_color.width / (np.linalg.norm(frame[0]) * entry["scale"][0] * 1000)
            for _, _, _, frame in faces
        ]
    )
    engraving_normal(
        output_color, blank, texels_per_mm, spherical_pips=name == "die"
    ).save(out / f"{name}_normal.png")
    print(name, "aligned labels in their reading frames")


if __name__ == "__main__":
    for name in sys.argv[1:] or NAMES:
        if name not in ("die", *NAMES):
            raise ValueError(name)
        center(name)
