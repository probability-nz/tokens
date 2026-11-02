"""Verify the physical fillet radius, not just the width of a chamfer."""

import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np

spec = importlib.util.spec_from_file_location(
    "align", Path(__file__).with_name("align-dice.py")
)
align = importlib.util.module_from_spec(spec)
spec.loader.exec_module(align)


class RoundingTests(unittest.TestCase):
    def test_every_die_has_a_one_mm_geometric_fillet(self):
        catalog = json.loads((align.ASSETS / "catalog.json").read_text())
        for entry in catalog["pieces"]:
            if not entry["faces"]:
                continue
            with self.subTest(die=entry["name"]):
                path = align.ASSETS / entry["src"]
                doc, points, groups = align.geometry(path)
                scale = np.array(entry["scale"]) * 1000
                self.assertEqual(float(np.ptp(scale)), 0)
                points = points * scale
                ns = np.array([g["normal"] for g in groups])
                ds = np.array(
                    [
                        np.mean(np.array(g["points"]) * scale @ n)
                        for g, n in zip(groups, ns)
                    ]
                )
                primitive = doc["meshes"][0]["primitives"][0]
                accessor = doc["accessors"][primitive["attributes"]["NORMAL"]]
                view = doc["bufferViews"][accessor["bufferView"]]
                buffer = (
                    path.parent / doc["buffers"][view["buffer"]]["uri"]
                ).read_bytes()
                normals = np.ndarray(
                    (accessor["count"], 3),
                    dtype="<f4",
                    buffer=buffer,
                    offset=view.get("byteOffset", 0) + accessor.get("byteOffset", 0),
                    strides=(view.get("byteStride", 12), 4),
                ).astype(float)
                self.assertLess(
                    float(np.max(np.abs(np.linalg.norm(normals, axis=1) - 1))), 1e-6
                )
                index_accessor = doc["accessors"][primitive["indices"]]
                index_view = doc["bufferViews"][index_accessor["bufferView"]]
                index_bytes = (
                    path.parent / doc["buffers"][index_view["buffer"]]["uri"]
                ).read_bytes()
                indices = np.frombuffer(
                    index_bytes,
                    dtype={5123: "<u2", 5125: "<u4"}[index_accessor["componentType"]],
                    count=index_accessor["count"],
                    offset=index_view.get("byteOffset", 0)
                    + index_accessor.get("byteOffset", 0),
                ).reshape(-1, 3)
                # Export splits UV seams. Weld within 0.1 micrometre before
                # checking that each geometric edge belongs to two triangles.
                _, welded = np.unique(np.round(points, 4), axis=0, return_inverse=True)
                triangles = welded[indices]
                edges = np.sort(
                    np.concatenate(
                        [
                            triangles[:, [0, 1]],
                            triangles[:, [1, 2]],
                            triangles[:, [2, 0]],
                        ]
                    ),
                    axis=1,
                )
                _, counts = np.unique(edges, axis=0, return_counts=True)
                self.assertTrue(
                    np.all(counts == 2), "Rounded patches must form a closed surface"
                )
                # Every surface point must be exactly 1.0mm along its normal
                # from the boundary of the same inward-offset convex core.
                # Blender quantizes custom split normals; allow one micron.
                core = points - 1.0 * normals
                distances = ds[None, :] - 1.0 - core @ ns.T
                self.assertGreater(float(distances.min()), -0.001)
                self.assertLess(float(np.min(np.abs(distances), axis=1).max()), 0.001)
                # Rounded edges/corners must actually be tessellated; a sharp
                # solid with only a normal-map bevel cannot satisfy this check.
                active = np.sum(np.abs(distances) < 0.001, axis=1)
                self.assertGreater(np.count_nonzero(active >= 2), len(groups) * 10)
                self.assertGreater(np.count_nonzero(active >= 3), len(groups) * 10)


if __name__ == "__main__":
    unittest.main()
