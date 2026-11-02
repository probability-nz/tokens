"""Center numeral artwork and rebuild matching engraving on each planar die face.

Run before prepare-assets.mjs. Original maps, UVs, meshes and face ordering stay
intact; centered/ contains reproducible maps derived from the original artwork.
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

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "src/assets"
NAMES = ("d4", "d6", "d8", "d12", "d20")
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


def label_jobs(name, faces, diffuse, entry):
    labels = Image.fromarray(label_mask(diffuse))
    jobs = []
    for centre, polygon, face_normal, frame in faces:
        box, inside, target = face_region(centre, polygon, diffuse.size, 1.06)
        _, safe, _ = face_region(centre, polygon, diffuse.size, 1.0)
        ink = np.asarray(labels.crop(box)) & inside
        if not ink.any():
            raise ValueError(f"{name}: no label on face")
        components, count = ndimage.label(ink)
        sizes = np.bincount(components.ravel())
        sizes[0] = 0
        parts = [ink]
        if name == "d4":
            parts = [
                components == index
                for index in range(1, count + 1)
                if sizes[index] > 20
            ]
            if len(parts) != 3:
                raise ValueError(
                    "Each D4 face must contain three complete corner labels"
                )
        for part in parts:
            y, x = np.nonzero(part)
            destination = target
            basis = None
            if name == "d4":
                mean_uv = (
                    np.array([x.mean(), y.mean()]) + box[:2] + 0.5
                ) / diffuse.size
                corner = polygon[np.argmin(np.linalg.norm(polygon - mean_uv, axis=1))]
                centre_world = np.r_[centre, 1] @ frame
                up = np.r_[corner, 1] @ frame - centre_world
                up /= np.linalg.norm(up)
                basis = np.array([np.cross(up, face_normal), -up]).T
                destination = (
                    (centre + 0.46 * (corner - centre)) * diffuse.size - 0.5 - box[:2]
                )
            else:
                pose = max(
                    entry["faces"],
                    key=lambda f: (align.matrix(f["rotation"]) @ face_normal)[1],
                )
                basis = align.matrix(pose["rotation"]).T[:, [0, 2]]
                # A 6/9 dot remains alongside the digit but must not pull the
                # numeral itself off centre. Keep all substantial digit components.
                body = part & (sizes[components] >= sizes.max() * 0.1)
                y, x = np.nonzero(body)
            # Measure in the actual face/corner reading frame, not in the
            # arbitrarily rotated UV atlas. Engraving is derived from the final ink.
            projection = np.diag(1 / np.array(diffuse.size)) @ frame[:2] @ basis
            points = np.c_[x, y] @ projection
            source = ((points.min(axis=0) + points.max(axis=0)) / 2) @ np.linalg.inv(
                projection
            )
            height = np.ptp(points, axis=0)[1]
            scale = 1.0
            jobs.append(
                dict(
                    box=box,
                    inside=inside,
                    safe=safe,
                    ink=part,
                    source=source,
                    destination=destination,
                    scale=scale,
                    height=height,
                )
            )
    common_height = (
        np.median([job["height"] for job in jobs])
        * {
            "d4": 0.90,
            "d6": 1.0,
            "d8": 0.88,
            "d12": 0.90,
            "d20": 0.90,
        }[name]
    )
    for job in jobs:
        job["scale"] = common_height / job["height"]
    return jobs


def engraving_normal(color, blank):
    """Derive an inset lip from the final ink, so geometry and print cannot drift.

    Image rows run downwards; tangent-space +Y runs upwards. Negative height
    inside the ink gives an engraving, with the opposite signs for X/Y slopes.
    """
    ink = label_mask(color)
    distance = ndimage.distance_transform_edt(ink) - ndimage.distance_transform_edt(
        ~ink
    )
    radius = max(1.5, color.width / 800)
    t = np.clip((distance + radius) / (2 * radius), 0, 1)
    height = -radius * 0.9 * t * t * (3 - 2 * t)
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
    # Preserve the exact blank pixels outside the lip, including baked bevels.
    changed = (dx != 0) | (dy != 0)
    output = np.array(blank)
    output[changed] = encoded[changed]
    return Image.fromarray(output)


def center(name):
    folder, faces = face_uvs(name, True)
    diffuse = Image.open(folder / f"{name}_diffuse.png").convert("RGB")
    normal = Image.open(folder / f"{name}_normal.png").convert("RGB")
    # Use freshly baked regular maps, not potentially stale published copies.
    blank_folder = folder
    blank = Image.open(blank_folder / f"{name}-blank-normal.png").convert("RGB")
    assert normal.size == blank.size
    # D20 source albedo is double the normal-map resolution. Work at the shared
    # resolution so ink and generated engraving use identical texel coordinates.
    diffuse = diffuse.resize(normal.size, Image.Resampling.LANCZOS)
    output_color = diffuse.copy()
    engraving_labels = Image.fromarray(label_mask(diffuse, 180))
    entry = next(
        e
        for e in json.loads((ASSETS / "catalog.json").read_text())["pieces"]
        if e["name"] == ("Classic die" if name == "die" else name.upper())
    )
    for job in ([] if name == "die" else label_jobs(name, faces, diffuse, entry)):
        box, inside, safe, ink = (job[key] for key in ("box", "inside", "safe", "ink"))
        source, destination, scale = (
            job[key] for key in ("source", "destination", "scale")
        )
        color = np.array(diffuse.crop(box))
        radius = 3  # Preserve antialiasing; the old engraving is no longer copied.
        engraving = np.asarray(engraving_labels.crop(box)) & inside
        if name == "d4":
            engraving &= ndimage.binary_dilation(ink, iterations=3)
        horizontal = engraving.copy()
        for offset in range(1, radius + 1):
            horizontal[:, offset:] |= engraving[:, :-offset]
            horizontal[:, :-offset] |= engraving[:, offset:]
        mask = horizontal.copy()
        for offset in range(1, radius + 1):
            mask[offset:] |= horizontal[:-offset]
            mask[:-offset] |= horizontal[offset:]
        offset = (source - destination / scale)[::-1]

        def transform(values, order=1):
            return ndimage.affine_transform(
                values,
                np.eye(2) / scale,
                offset=offset,
                output_shape=inside.shape,
                order=order,
                mode="constant",
                cval=0,
                prefilter=False,
            )

        moved = transform(mask.astype(float)) > 0
        if not safe[moved].all():
            raise ValueError(
                f"{name}: shifted engraving reaches face border {box} source {source} target {destination} scale {scale}"
            )
        new_color = np.array(output_color.crop(box))
        new_color[mask] = 255
        for channel in range(3):
            ink_channel = (255 - color[:, :, channel].astype(float)) * mask
            shifted_ink = transform(ink_channel)
            new_color[:, :, channel][moved] = (
                np.rint(255 - shifted_ink[moved]).clip(0, 255).astype("uint8")
            )
        output_color.paste(Image.fromarray(new_color), box[:2])
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
    engraving_normal(output_color, blank).save(out / f"{name}_normal.png")
    print(name, "aligned labels in their reading frames")


if __name__ == "__main__":
    for name in sys.argv[1:] or NAMES:
        if name not in ("die", *NAMES):
            raise ValueError(name)
        center(name)
