"""Validate centering and preservation of complete labels, including 6/9 dots."""

import importlib.util
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
from scipy import ndimage

spec = importlib.util.spec_from_file_location(
    "center", Path(__file__).with_name("center-dice-labels.py")
)
center = importlib.util.module_from_spec(spec)
spec.loader.exec_module(center)


class CenteredLabelsTests(unittest.TestCase):
    def test_every_label_is_centered_and_keeps_its_components(self):
        for name in center.NAMES:
            folder, faces = center.face_uvs(name)
            output = Image.open(
                center.ASSETS / name / "centered" / f"{name}_diffuse.png"
            ).convert("RGB")
            original = (
                Image.open(folder / f"{name}_diffuse.png")
                .convert("RGB")
                .resize(output.size, Image.Resampling.LANCZOS)
            )
            original_labels = Image.fromarray(center.label_mask(original))
            output_labels = Image.fromarray(center.label_mask(output))
            self.assertEqual(len(faces), int(name[1:]))
            for index, (point, polygon, _) in enumerate(faces):
                with self.subTest(die=name, face=index):
                    box, inside, target = center.face_region(
                        point, polygon, output.size, 1.06
                    )
                    before = np.asarray(original_labels.crop(box)) & inside
                    after = np.asarray(output_labels.crop(box)) & inside
                    y, x = np.nonzero(after)
                    midpoint = np.array(
                        [(x.min() + x.max()) / 2, (y.min() + y.max()) / 2]
                    )
                    self.assertLessEqual(float(np.abs(midpoint - target).max()), 1.0)

                    def components(mask):
                        labels, _ = ndimage.label(mask)
                        sizes = np.bincount(labels.ravel())[1:]
                        return int((sizes > 8).sum())

                    self.assertEqual(components(before), components(after))
                    self.assertGreater(after.sum() / before.sum(), 0.7)
                    self.assertLess(after.sum() / before.sum(), 1.05)


if __name__ == "__main__":
    unittest.main()
