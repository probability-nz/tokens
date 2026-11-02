"""Derive face poses from mesh planes and retain one table-facing footprint.
Run after prepare-assets.mjs (requires NumPy). Original pose hints only identify
numbered faces; their rounded Euler angles are never used as the final tilt.
"""

import base64
import copy
import json
import math
from pathlib import Path
import struct
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "src/assets"


def matrix(r):
    x, y, z = r
    cx, sx, cy, sy, cz, sz = (
        math.cos(x),
        math.sin(x),
        math.cos(y),
        math.sin(y),
        math.cos(z),
        math.sin(z),
    )
    return (
        np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        @ np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    )


def euler(m):
    y = math.asin(np.clip(m[0, 2], -1, 1))
    if abs(m[0, 2]) < 0.9999999:
        x, z = math.atan2(-m[1, 2], m[2, 2]), math.atan2(-m[0, 1], m[0, 0])
    else:
        x, z = math.atan2(m[2, 1], m[1, 1]), 0

    # Remove float32 noise at known exact axis turns, not geometric tilt angles.
    def clean(a):
        for b in [i * math.pi / 6 for i in range(-6, 7)]:
            if abs(a - b) < 1e-7:
                return math.pi if abs(b) == math.pi else (b if b else 0)
        # Plane fitting and summation order can vary in the last few binary
        # bits. Canonical precision prevents those bits from changing UV bakes
        # on every regeneration; this is far below float32 mesh precision.
        return round(float(a), 14)

    return [clean(a) for a in (x, y, z)]


def align(a, b):
    v = np.cross(a, b)
    c = np.dot(a, b)
    if np.linalg.norm(v) < 1e-12:
        if c > 0:
            return np.eye(3)
        axis = np.eye(3)[np.argmin(np.abs(a))]
        axis = np.cross(a, axis)
        axis /= np.linalg.norm(axis)
        return 2 * np.outer(axis, axis) - np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def geometry(path):
    d = json.loads(path.read_text())
    buffers = [
        (
            base64.b64decode(b["uri"].split(",")[1])
            if b["uri"].startswith("data:")
            else (path.parent / b["uri"]).read_bytes()
        )
        for b in d["buffers"]
    ]

    def accessor(i):
        a = d["accessors"][i]
        v = d["bufferViews"][a["bufferView"]]
        n = {"VEC2": 2, "VEC3": 3, "VEC4": 4, "SCALAR": 1}[a["type"]]
        fmt = "<" + {5126: "f", 5123: "H", 5125: "I", 5121: "B"}[a["componentType"]] * n
        return np.array(
            [
                struct.unpack_from(
                    fmt,
                    buffers[v["buffer"]],
                    v.get("byteOffset", 0)
                    + a.get("byteOffset", 0)
                    + j * v.get("byteStride", struct.calcsize(fmt)),
                )
                for j in range(a["count"])
            ]
        )

    node = d["nodes"][0]
    primitive = d["meshes"][node["mesh"]]["primitives"][0]
    ps = accessor(primitive["attributes"]["POSITION"]) * node.get(
        "scale", [1, 1, 1]
    ) + node.get("translation", [0, 0, 0])
    ids = accessor(primitive["indices"]).astype(int).reshape(-1, 3)
    if np.prod(node.get("scale", [1, 1, 1])) < 0:
        ids = ids[:, ::-1]
    ts = ps[ids]
    ns = np.cross(ts[:, 1] - ts[:, 0], ts[:, 2] - ts[:, 0])
    areas = np.linalg.norm(ns, axis=1)
    groups = []
    for tri, n, area in zip(ts, ns, areas):
        if area < max(areas) * 0.1:
            continue
        n = n / area
        match = next(
            (g for g in groups if np.linalg.norm(g["normal"] - n) < 1e-3), None
        )
        if match is None:
            groups.append({"normal": n, "points": list(tri)})
        else:
            match["points"].extend(tri)
    for g in groups:
        g["points"] = np.unique(np.round(g["points"], 7), axis=0)
        # A plane fitted to every polygon corner avoids arbitrary triangulation noise.
        _, _, vh = np.linalg.svd(g["points"] - np.mean(g["points"], axis=0))
        n = vh[-1]
        g["normal"] = n if np.dot(n, g["normal"]) > 0 else -n
    return d, ps, groups


def flat_pose(hint, groups):
    old = matrix(hint)
    g = min(groups, key=lambda g: (old @ g["normal"])[1])
    return align(old @ g["normal"], np.array([0.0, -1.0, 0.0])) @ old, g


def corner_angles(r, g):
    ps = g["points"] @ r.T
    ps -= np.mean(ps, axis=0)
    radius = np.linalg.norm(ps[:, [0, 2]], axis=1)
    return [
        math.atan2(p[2], p[0]) for p, rad in zip(ps, radius) if rad > max(radius) * 0.95
    ]


def generate():
    catalog_path = ASSETS / "catalog.json"
    catalog = json.loads(catalog_path.read_text())
    hints = json.loads((ROOT / "scripts/assets/authored-dice-poses.json").read_text())
    for entry in catalog["pieces"]:
        if entry["name"] == "D4":
            tilt = -math.acos(-1 / 3)
            entry["rotation"] = [0, 0, 0]
            entry["faces"] = [
                {"name": str(i + 1), "rotation": r}
                for i, r in enumerate(
                    [
                        [0, 0, 0],
                        [tilt, -math.pi / 3, 0],
                        [tilt, math.pi / 3, 0],
                        [tilt, math.pi, 0],
                    ]
                )
            ]
        elif entry["name"] == "D10":
            from d10_geometry import poses
            entry["faces"] = poses()
            entry["rotation"] = entry["faces"][0]["rotation"]
        elif entry["name"] in hints:
            _, ps, groups = geometry(ASSETS / entry["src"])
            hint = hints[entry["name"]]
            reference, face = flat_pose(hint["rotation"], groups)
            ref_angles = corner_angles(reference, face)
            rotations = []
            for outcome in hint["faces"]:
                pose, g = flat_pose(outcome["rotation"], groups)
                # Any matching corner gives the same regular footprint. Choose the
                # smallest yaw correction to retain the authored number's readability.
                deltas = [
                    math.atan2(math.sin(a - b), math.cos(a - b))
                    for a in ref_angles
                    for b in corner_angles(pose, g)
                ]
                delta = min(deltas, key=abs)
                # Use every face normal to refine the yaw. Individual bevel corners may
                # be asymmetric (notably D12), so a single corner is a poor heading guide.
                pose = matrix([0, -delta, 0]) @ pose
                reference_normals = np.array(
                    [reference @ group["normal"] for group in groups]
                )
                for _ in range(3):
                    current = np.array([pose @ group["normal"] for group in groups])
                    matches = reference_normals[
                        np.argmin(
                            np.linalg.norm(
                                current[:, None] - reference_normals[None, :], axis=2
                            ),
                            axis=1,
                        )
                    ]
                    sine = np.sum(
                        current[:, 2] * matches[:, 0] - current[:, 0] * matches[:, 2]
                    )
                    cosine = np.sum(
                        current[:, 0] * matches[:, 0] + current[:, 2] * matches[:, 2]
                    )
                    pose = matrix([0, math.atan2(sine, cosine), 0]) @ pose
                rotations.append({"name": outcome["name"], "rotation": euler(pose)})
            entry["faces"] = rotations
            entry["rotation"] = rotations[0]["rotation"]
        elif entry["name"].endswith(" (blank)"):
            original = next(
                p
                for p in catalog["pieces"]
                if p["name"] == entry["name"].replace(" (blank)", "")
            )
            entry["rotation"] = copy.deepcopy(original["rotation"])
            entry["faces"] = copy.deepcopy(original["faces"])
        if entry["faces"]:
            path = ASSETS / entry["src"]
            doc = json.loads(path.read_text())
            doc.setdefault("extras", {}).setdefault("probability", {})["faces"] = entry[
                "faces"
            ]
            path.write_text(json.dumps(doc, indent=2) + "\n")
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n")


if __name__ == "__main__":
    generate()
