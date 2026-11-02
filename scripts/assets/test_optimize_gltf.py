"""Lossless optimization must preserve every oriented triangle's attribute bytes."""

from collections import Counter
import json
import random
from pathlib import Path
import struct
import unittest
from optimize_gltf import optimize

ROOT = Path(__file__).resolve().parents[2]


def triangle_records(doc, data):
    def read(index):
        a = doc["accessors"][index]
        v = doc["bufferViews"][a["bufferView"]]
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
        fmt = "<" + {5126: "f", 5123: "H", 5125: "I"}[a["componentType"]] * width
        size = struct.calcsize(fmt)
        start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        return [
            data[
                start
                + i * v.get("byteStride", size) : start
                + i * v.get("byteStride", size)
                + size
            ]
            for i in range(a["count"])
        ], fmt

    result = []
    for mesh in doc["meshes"]:
        for p in mesh["primitives"]:
            streams = [read(p["attributes"][n])[0] for n in sorted(p["attributes"])]
            vertices = list(zip(*streams))
            records, fmt = read(p["indices"])
            ids = [struct.unpack(fmt, r)[0] for r in records]
            result.append(
                Counter(
                    tuple(vertices[i] for i in ids[k : k + 3])
                    for k in range(0, len(ids), 3)
                )
            )
    return result


class OptimizerTests(unittest.TestCase):
    def test_source_meshes_preserve_all_attributes_and_are_idempotent(self):
        for name in ("die", "d4", "d6", "d8", "d12", "d20"):
            with self.subTest(die=name):
                folder = ROOT / "src/assets" / name / "regular"
                doc = json.loads((folder / f"{name}.gltf").read_text())
                data = (folder / doc["buffers"][0]["uri"]).read_bytes()
                result, output = optimize(doc, data)
                self.assertEqual(
                    triangle_records(doc, data), triangle_records(result, output)
                )
                self.assertLessEqual(len(output), len(data))
                again, second = optimize(result, output)
                self.assertEqual(result, again)
                self.assertEqual(output, second)
                # Exercise actual triangle reordering, not only an already
                # optimized mesh passing through unchanged.
                scrambled = bytearray(data)
                for mesh in doc["meshes"]:
                    for primitive in mesh["primitives"]:
                        acc = doc["accessors"][primitive["indices"]]
                        view = doc["bufferViews"][acc["bufferView"]]
                        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
                        size = {5123: 2, 5125: 4}[acc["componentType"]] * 3
                        triangles = [
                            bytes(scrambled[start + i * size : start + (i + 1) * size])
                            for i in range(acc["count"] // 3)
                        ]
                        random.Random(0).shuffle(triangles)
                        scrambled[start : start + acc["count"] // 3 * size] = b"".join(
                            triangles
                        )
                changed, changed_data = optimize(doc, bytes(scrambled))
                self.assertEqual(
                    triangle_records(doc, bytes(scrambled)),
                    triangle_records(changed, changed_data),
                )

    def test_exact_duplicates_merge_but_uv_seams_do_not(self):
        for seam, expected in ((False, 4), (True, 5)):
            with self.subTest(seam=seam):
                positions = [
                    (0, 0, 0),
                    (1, 0, 0),
                    (1, 1, 0),
                    (0, 0, 0),
                    (1, 1, 0),
                    (0, 1, 0),
                ]
                uv = [p[:2] for p in positions]
                if seam:
                    uv[3] = (0.25, 0.25)
                doc = {
                    "buffers": [{"uri": "mesh.bin"}],
                    "bufferViews": [],
                    "accessors": [],
                    "meshes": [{"primitives": [{"attributes": {}, "mode": 4}]}],
                }
                data = bytearray()
                p = doc["meshes"][0]["primitives"][0]
                for name, values, kind, width in [
                    ("POSITION", positions, "VEC3", 3),
                    ("NORMAL", [(0, 0, 1)] * 6, "VEC3", 3),
                    ("TEXCOORD_0", uv, "VEC2", 2),
                    ("TANGENT", [(1, 0, 0, 1)] * 6, "VEC4", 4),
                ]:
                    start = len(data)
                    for value in values:
                        data.extend(struct.pack("<" + "f" * width, *value))
                    doc["bufferViews"].append(
                        dict(buffer=0, byteOffset=start, byteLength=len(data) - start)
                    )
                    p["attributes"][name] = len(doc["accessors"])
                    doc["accessors"].append(
                        dict(
                            bufferView=len(doc["bufferViews"]) - 1,
                            componentType=5126,
                            count=6,
                            type=kind,
                        )
                    )
                start = len(data)
                data.extend(struct.pack("<6H", *range(6)))
                doc["bufferViews"].append(
                    dict(buffer=0, byteOffset=start, byteLength=12)
                )
                p["indices"] = len(doc["accessors"])
                doc["accessors"].append(
                    dict(
                        bufferView=len(doc["bufferViews"]) - 1,
                        componentType=5123,
                        count=6,
                        type="SCALAR",
                    )
                )
                doc["buffers"][0]["byteLength"] = len(data)
                result, output = optimize(doc, bytes(data))
                rp = result["meshes"][0]["primitives"][0]
                self.assertEqual(
                    result["accessors"][rp["attributes"]["POSITION"]]["count"], expected
                )
                self.assertEqual(
                    triangle_records(doc, bytes(data)), triangle_records(result, output)
                )


if __name__ == "__main__":
    unittest.main()
