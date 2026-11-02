"""D10 outcomes must select the printed face while preserving the whole solid."""

import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np
from scipy.spatial import cKDTree

spec = importlib.util.spec_from_file_location(
    "center", Path(__file__).with_name("center-dice-labels.py")
)
center = importlib.util.module_from_spec(spec)
spec.loader.exec_module(center)
align = center.align


class D10Tests(unittest.TestCase):
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
