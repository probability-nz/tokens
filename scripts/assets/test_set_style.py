"""Check physical set sizes and lettering clearance independently of generation."""

import importlib.util
import json
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
from dice_style import HEIGHT_MM, LABEL_CLEARANCE_MM

spec = importlib.util.spec_from_file_location(
    "center", Path(__file__).with_name("center-dice-labels.py")
)
center = importlib.util.module_from_spec(spec)
spec.loader.exec_module(center)
a = center.align


class SetStyleTests(unittest.TestCase):
    def test_resting_heights_match_the_coordinated_set(self):
        for entry in json.loads((a.ASSETS / "catalog.json").read_text())["pieces"]:
            if not entry["faces"]:
                continue
            name = (
                "die"
                if entry["name"] == "Classic die"
                else entry["name"].split(" ")[0].lower()
            )
            _, points, _ = a.geometry(a.ASSETS / entry["src"])
            for face in entry["faces"]:
                with self.subTest(die=entry["name"], face=face["name"]):
                    height = (
                        np.ptp((points @ a.matrix(face["rotation"]).T)[:, 1])
                        * entry["scale"][0]
                        * 1000
                    )
                    self.assertAlmostEqual(height, HEIGHT_MM[name], delta=0.002)

    def test_all_print_has_physical_clearance_from_the_flat_face_edge(self):
        catalog = json.loads((a.ASSETS / "catalog.json").read_text())["pieces"]
        for name in center.NAMES:
            entry = next(e for e in catalog if e["name"] == name.upper())
            _, faces = center.face_uvs(name, True)
            image = Image.open(
                a.ASSETS / name / "centered" / f"{name}_diffuse.png"
            ).convert("RGB")
            labels = Image.fromarray(center.label_mask(image))
            for point, poly, normal, frame in faces:
                box, inside, _ = center.face_region(point, poly, image.size, 1.06)
                ink = np.asarray(labels.crop(box)) & inside
                y, x = np.nonzero(ink)
                xyz = (
                    np.c_[(np.c_[x, y] + box[:2] + 0.5) / image.size, np.ones(len(x))]
                    @ frame
                )
                polygon = np.c_[poly, np.ones(len(poly))] @ frame
                for start, end in zip(polygon, np.roll(polygon, -1, axis=0)):
                    inward = np.cross(normal, end - start)
                    inward /= np.linalg.norm(inward)
                    if np.dot(inward, polygon.mean(axis=0) - start) < 0:
                        inward *= -1
                    distance = np.min((xyz - start) @ inward) * entry["scale"][0] * 1000
                    with self.subTest(die=name):
                        # Sampling/threshold differences can shift a boundary by
                        # one texel; allow 0.08mm, not arbitrary per-die margins.
                        self.assertGreater(distance, LABEL_CLEARANCE_MM - 0.08)


if __name__ == "__main__":
    unittest.main()
