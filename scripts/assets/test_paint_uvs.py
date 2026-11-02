"""Painting islands must be distinct, continuous, and have usable PNG guides."""

import itertools
import subprocess
from scipy.spatial import ConvexHull
import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "align", Path(__file__).with_name("align-dice.py")
)
align = importlib.util.module_from_spec(spec)
spec.loader.exec_module(align)


class PaintUVTests(unittest.TestCase):
    def test_islands_do_not_overlap_and_corner_seams_are_continuous(self):
        for name, published in itertools.product(
            ("die", "d4", "d6", "d8", "d12", "d20"), (False, True)
        ):
            with self.subTest(die=name, published=published):
                asset_folder = ROOT / "src/assets" / name
                folder = asset_folder if published else asset_folder / "regular"
                doc = json.loads((folder / f"{name}.gltf").read_text())
                layout = json.loads(
                    (asset_folder / "regular/uv-layout.json").read_text()
                )

                def read(index, width, dtype):
                    a = doc["accessors"][index]
                    v = doc["bufferViews"][a["bufferView"]]
                    data = (folder / doc["buffers"][v["buffer"]]["uri"]).read_bytes()
                    scalar = np.dtype(dtype).itemsize
                    return np.ndarray(
                        (a["count"], width),
                        dtype=dtype,
                        buffer=data,
                        offset=v.get("byteOffset", 0) + a.get("byteOffset", 0),
                        strides=(v.get("byteStride", width * scalar), scalar),
                    )

                p = doc["meshes"][0]["primitives"][0]
                uv = read(p["attributes"]["TEXCOORD_0"], 2, "<f4")
                xyz = read(p["attributes"]["POSITION"], 3, "<f4")
                normals = read(p["attributes"]["NORMAL"], 3, "<f4").astype(float)
                tangents = read(p["attributes"]["TANGENT"], 4, "<f4").astype(float)
                self.assertLess(
                    float(np.abs(np.linalg.norm(tangents[:, :3], axis=1) - 1).max()),
                    1e-6,
                )
                self.assertLess(
                    float(np.abs(np.sum(normals * tangents[:, :3], axis=1)).max()), 1e-6
                )
                _, welded = np.unique(np.round(xyz, 5), axis=0, return_inverse=True)
                for group in np.flatnonzero(np.bincount(welded) > 1):
                    ns = normals[welded == group]
                    self.assertLess(
                        float(np.linalg.norm(ns - ns[0], axis=1).max()), 1e-6
                    )
                a = doc["accessors"][p["indices"]]
                ids = read(
                    p["indices"], 1, {5123: "<u2", 5125: "<u4"}[a["componentType"]]
                ).reshape(-1, 3)
                columns = layout["columns"]
                tiles = np.floor(uv * columns).astype(int)
                slots = tiles[:, 1] * columns + tiles[:, 0]
                self.assertEqual(set(slots), set(range(len(layout["patches"]))))
                for slot, patch in enumerate(layout["patches"]):
                    selected = np.all(slots[ids] == slot, axis=1)
                    self.assertTrue(selected.any())
                    triangles = uv[ids[selected]].astype(float) * columns
                    a = triangles[:, 1] - triangles[:, 0]
                    b = triangles[:, 2] - triangles[:, 0]
                    signed = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
                    self.assertGreater(float(np.abs(signed).min()), 1e-8)
                    self.assertTrue(
                        np.all(signed > 0) or np.all(signed < 0),
                        "UV fan folds over itself",
                    )
                    hull_area = ConvexHull(
                        uv[slots == slot].astype(float) * columns
                    ).volume
                    self.assertAlmostEqual(
                        float(np.abs(signed).sum() / 2), hull_area, delta=1e-6
                    )
                    # All triangles at the same 3D corner point must use
                    # the same UV: the old per-wedge mapping repeated art.
                    seen = {}
                    for index in ids[selected].ravel():
                        key = tuple(np.round(xyz[index], 5))
                        if key in seen:
                            np.testing.assert_allclose(uv[index], seen[key], atol=1e-5)
                        seen[key] = uv[index]
                # Every mesh triangle belongs wholly to one labelled island.
                self.assertTrue(np.all(slots[ids] == slots[ids][:, :1]))
                for file in (
                    "blank.png",
                    "numbered.png",
                    "uv-guide.png",
                    "reference.png",
                ):
                    im = Image.open(asset_folder / "paint" / file)
                    im.load()
                    self.assertEqual(im.size, (2048, 2048))
                    if file == "uv-guide.png":
                        self.assertEqual(im.mode, "RGBA")
                        self.assertLess(
                            np.count_nonzero(np.asarray(im)[..., 3]) / 2048**2, 0.2
                        )

    def test_standalone_build_includes_current_painting_layers(self):
        subprocess.run(["node", "scripts/build-catalog.mjs"], cwd=ROOT, check=True)
        for name in ("die", "d4", "d6", "d8", "d12", "d20"):
            for source in (ROOT / "src/assets" / name / "paint").iterdir():
                with self.subTest(die=name, layer=source.name):
                    self.assertEqual(
                        source.read_bytes(),
                        (ROOT / "dist" / name / "paint" / source.name).read_bytes(),
                    )


if __name__ == "__main__":
    unittest.main()
