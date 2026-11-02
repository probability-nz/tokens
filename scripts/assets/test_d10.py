"""D10 outcomes must select the printed face while preserving the whole solid."""

import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np
from scipy.spatial import cKDTree
from scipy import ndimage
from PIL import Image

spec = importlib.util.spec_from_file_location(
    "center", Path(__file__).with_name("center-dice-labels.py")
)
center = importlib.util.module_from_spec(spec)
spec.loader.exec_module(center)
align = center.align


class D10Tests(unittest.TestCase):
    def test_digits_match_the_existing_set_artwork(self):
        catalog = json.loads((align.ASSETS / "catalog.json").read_text())["pieces"]

        def glyph(name, label):
            _, faces = center.face_uvs(name)
            entry = next(e for e in catalog if e["name"] == name.upper())
            source_label = "10" if name == "d12" and label == "0" else label
            pose = align.matrix(
                next(f for f in entry["faces"] if f["name"] == source_label)["rotation"]
            )
            point, polygon, _ = max(faces, key=lambda f: (pose @ f[2])[1])
            image = Image.open(
                align.ASSETS / name / "centered" / f"{name}_diffuse.png"
            ).convert("RGB")
            box, inside, _ = center.face_region(point, polygon, image.size)
            ink = (np.asarray(image.crop(box)).max(axis=2) < 100) & inside
            components, _ = ndimage.label(ink)
            sizes = np.bincount(components.ravel())
            sizes[0] = 0
            ids = [i for i in range(1, len(sizes)) if sizes[i] > sizes.max() * 0.1]
            if source_label == "10":
                ids = [max(ids, key=lambda i: np.nonzero(components == i)[1].mean())]
            ink = np.isin(components, ids)
            y, x = np.nonzero(ink)
            cropped = Image.fromarray(ink[y.min() : y.max() + 1, x.min() : x.max() + 1])
            return np.asarray(cropped.resize((96, 128), Image.Resampling.NEAREST))

        for label in map(str, range(10)):
            with self.subTest(label=label):
                original, actual = glyph("d12", label), glyph("d10", label)
                # Permit raster resampling at different atlas scales, but reject
                # substituted fonts, altered strokes, or an incorrect digit.
                overlap = np.count_nonzero(original & actual) / np.count_nonzero(
                    original | actual
                )
                self.assertGreater(overlap, 0.92)

    def test_kites_opposites_labels_and_all_ten_symmetries(self):
        entry = next(
            p
            for p in json.loads((align.ASSETS / "catalog.json").read_text())["pieces"]
            if p["name"] == "D10"
        )
        doc, points, groups = align.geometry(align.ASSETS / entry["src"])
        self.assertEqual([f["name"] for f in entry["faces"]], list(map(str, range(10))))
        self.assertEqual(len(groups), 10)
        self.assertEqual([len(g["points"]) for g in groups], [4] * 10)
        # All ten flat kites have the same six pairwise corner distances.
        shapes = [
            np.sort(
                [
                    np.linalg.norm(a - b)
                    for i, a in enumerate(g["points"])
                    for b in g["points"][i + 1 :]
                ]
            )
            for g in groups
        ]
        np.testing.assert_allclose(
            shapes, np.repeat([shapes[0]], 10, axis=0), atol=3e-7
        )
        # The centroid remains at the origin, independent of UV seam duplication.
        np.testing.assert_allclose(
            np.mean([np.mean(g["points"], axis=0) for g in groups], axis=0),
            0,
            atol=1e-7,
        )
        reference = points @ align.matrix(entry["rotation"]).T
        tree = cKDTree(reference)
        _, faces = center.face_uvs("d10")
        selected = []
        flat_centres = []
        for face in entry["faces"]:
            rotation = align.matrix(face["rotation"])
            self.assertEqual(face["rotation"][2], 0)
            self.assertLess(float(tree.query(points @ rotation.T)[0].max()), 3e-7)
            index = max(range(len(faces)), key=lambda i: (rotation @ faces[i][2])[1])
            selected.append(index)
            uv, _, normal = faces[index]
            np.testing.assert_allclose(rotation @ normal, [0, 1, 0], atol=2e-7)
            # Actual mesh UVs identify the printed atlas tile, not generator order.
            slot = int(uv[0] * 4) + 4 * int(uv[1] * 4)
            self.assertEqual(slot, int(face["name"]))
            opposite = min(range(len(faces)), key=lambda i: np.dot(normal, faces[i][2]))
            opposite_uv = faces[opposite][0]
            opposite_label = int(opposite_uv[0] * 4) + 4 * int(opposite_uv[1] * 4)
            self.assertEqual(int(face["name"]) + opposite_label, 9)
            g = max(groups, key=lambda g: np.dot(g["normal"], normal))
            flat_centres.append(np.mean(g["points"], axis=0) @ rotation.T)
        self.assertEqual(len(set(selected)), 10)
        np.testing.assert_allclose(
            flat_centres, np.repeat([flat_centres[0]], 10, axis=0), atol=3e-7
        )


if __name__ == "__main__":
    unittest.main()
