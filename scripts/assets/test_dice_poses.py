"""Check every catalog die's resting plane, footprint, metadata and pivot."""

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


class DicePoseTests(unittest.TestCase):
    def test_all_catalog_outcomes(self):
        catalog = json.loads((align.ASSETS / "catalog.json").read_text())
        for entry in catalog["pieces"]:
            if not entry["faces"]:
                continue
            with self.subTest(name=entry["name"]):
                document, points, groups = align.geometry(align.ASSETS / entry["src"])
                self.assertEqual(
                    document["extras"]["probability"]["faces"], entry["faces"]
                )
                self.assertEqual(len(groups), len(entry["faces"]))
                transforms = [align.matrix(f["rotation"]) for f in entry["faces"]]
                supports = []
                bounds = []
                for transform in transforms:
                    normals = [transform @ g["normal"] for g in groups]
                    support = min(range(len(groups)), key=lambda i: normals[i][1])
                    supports.append(support)
                    self.assertLess(np.linalg.norm(normals[support] - [0, -1, 0]), 1e-6)
                    p = (points @ transform.T) * entry["scale"]
                    bounds.append((p.min(axis=0), p.max(axis=0)))
                self.assertEqual(len(set(supports)), len(supports))
                # Includes actual bevel geometry, not merely fitted face planes.
                span = np.ptp(np.array(bounds), axis=0)
                print(
                    entry["name"], "bound drift (mm)", np.round(span * 1000, 6).tolist()
                )
                self.assertLess(float(span.max()), 2e-6)
                if entry["name"].startswith(("D4", "D12")):
                    for transform in transforms:
                        rotated = points @ transform.T
                        distances = np.linalg.norm(
                            rotated[:, None, :]
                            - (points @ transforms[0].T)[None, :, :],
                            axis=2,
                        )
                        self.assertLess(float(distances.min(axis=1).max()), 2e-7)
                    # Regular face polygons, no displaced source-mesh origin.
                    for g in groups:
                        corners = g["points"]
                        distances = np.linalg.norm(
                            corners[:, None] - corners[None, :], axis=2
                        )
                        edges = np.min(
                            np.where(distances > 1e-6, distances, np.inf), axis=1
                        )
                        self.assertLess(float(np.ptp(edges)), 3e-7)
                        if entry["name"].startswith("D12"):
                            self.assertEqual(len(corners), 5)
                            self.assertAlmostEqual(
                                float(distances.max() / edges.mean()),
                                (1 + np.sqrt(5)) / 2,
                                places=5,
                            )
                    centre = np.mean(
                        [np.mean(g["points"], axis=0) for g in groups], axis=0
                    )
                    self.assertLess(float(np.linalg.norm(centre)), 1e-7)


if __name__ == "__main__":
    unittest.main()
