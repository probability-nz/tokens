"""Center existing numeral artwork and engraving on each planar die face.

Run before prepare-assets.mjs. Original maps, UVs, meshes and face ordering stay
intact; centered/ contains reproducible maps derived from the original artwork.
D4 uses corner labels, and the classic die uses pips, so neither is processed.
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
NAMES = ("d6", "d8", "d12", "d20")
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


def face_uvs(name):
    folder = ASSETS / name / ("regular" if name == "d12" else "source")
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
        faces.append((centre, hull(triangles.reshape(-1, 2)), group["normal"]))
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


def label_mask(image):
    dark = np.asarray(image).max(axis=2) < 100
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


def center(name):
    folder, faces = face_uvs(name)
    diffuse = Image.open(folder / f"{name}_diffuse.png").convert("RGB")
    normal = Image.open(folder / f"{name}_normal.png").convert("RGB")
    blank = Image.open(ASSETS / "blank-dice" / f"{name}-blank-normal.png").convert(
        "RGB"
    )
    assert normal.size == blank.size
    # D20 source albedo is double the normal-map resolution. Work at the shared
    # resolution so ink and engraving receive exactly the same integer shift.
    diffuse = diffuse.resize(normal.size, Image.Resampling.LANCZOS)
    output_color, output_normal = diffuse.copy(), normal.copy()
    labels = Image.fromarray(label_mask(diffuse))
    entry = next(
        e
        for e in json.loads((ASSETS / "catalog.json").read_text())["pieces"]
        if e["name"] == name.upper()
    )
    report = []
    for centre, polygon, face_normal in faces:
        box, inside, target = face_region(centre, polygon, diffuse.size, 1.06)
        _, safe, _ = face_region(centre, polygon, diffuse.size, 1.0)
        color = np.array(diffuse.crop(box))
        original = np.array(normal.crop(box))
        base = np.array(blank.crop(box))
        ink = np.asarray(labels.crop(box)) & inside
        yy, xx = np.nonzero(ink)
        if not len(xx):
            raise ValueError(f"{name}: no label on face")
        source = np.array([(xx.min() + xx.max()) / 2, (yy.min() + yy.max()) / 2])
        shift = np.rint(target - source).astype(int)
        radius = max(3, round(diffuse.width / 160))
        horizontal = ink.copy()
        for offset in range(1, radius + 1):
            horizontal[:, offset:] |= ink[:, :-offset]
            horizontal[:, :-offset] |= ink[:, offset:]
        mask = horizontal.copy()
        for offset in range(1, radius + 1):
            mask[offset:] |= horizontal[:-offset]
            mask[:-offset] |= horizontal[offset:]
        # Uniform reductions leave room for the tallest/widest label on each
        # triangular die, including the engraving around multi-digit labels.
        scale = {"d8": 0.88, "d20": 0.94}.get(name, 1.0)
        destination = source + shift if scale == 1 else target
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
                f"{name}: shifted engraving reaches face border: source={source}, target={target}, shift={shift}, centre={centre}"
            )
        new_color = np.array(output_color.crop(box))
        new_normal = np.array(output_normal.crop(box)).astype("float64")
        new_color[mask] = 255
        new_normal[mask] = base[mask]
        for channel in range(3):
            ink_channel = (255 - color[:, :, channel].astype(float)) * mask
            shifted_ink = transform(ink_channel)
            new_color[:, :, channel][moved] = (
                np.rint(255 - shifted_ink[moved]).clip(0, 255).astype("uint8")
            )
            residual = (
                original[:, :, channel].astype(float) - base[:, :, channel]
            ) * mask
            shifted_normal = transform(residual)
            new_normal[:, :, channel][moved] = (
                base[:, :, channel][moved] + shifted_normal[moved]
            )
        output_color.paste(Image.fromarray(new_color), box[:2])
        output_normal.paste(
            Image.fromarray(np.rint(new_normal).clip(0, 255).astype("uint8")), box[:2]
        )
        label = max(
            entry["faces"], key=lambda f: (align.matrix(f["rotation"]) @ face_normal)[1]
        )["name"]
        report.append({"face": label, "shiftPixels": shift.tolist(), "scale": scale})
    out = ASSETS / name / "centered"
    out.mkdir(exist_ok=True)
    output_color.save(out / f"{name}_diffuse.png")
    output_normal.save(out / f"{name}_normal.png")
    print(name, json.dumps(sorted(report, key=lambda r: int(r["face"]))))


if __name__ == "__main__":
    for name in sys.argv[1:] or NAMES:
        if name not in NAMES:
            raise ValueError(name)
        center(name)
