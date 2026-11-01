"""Validate centering and preservation of complete labels, including 6/9 dots."""

import importlib.util
from pathlib import Path
import unittest
import shutil
import tempfile
from unittest.mock import patch
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

    def test_published_compressed_textures_keep_labels_centered(self):
        for name in center.NAMES:
            _, faces = center.face_uvs(name)
            image = Image.open(center.ASSETS / name / f"{name}_diffuse.avif").convert(
                "RGB"
            )
            labels = Image.fromarray(center.label_mask(image))
            for index, (point, polygon, _) in enumerate(faces):
                with self.subTest(die=name, face=index):
                    box, inside, target = center.face_region(
                        point, polygon, image.size, 1.06
                    )
                    y, x = np.nonzero(np.asarray(labels.crop(box)) & inside)
                    midpoint = np.array(
                        [(x.min() + x.max()) / 2, (y.min() + y.max()) / 2]
                    )
                    self.assertLessEqual(float(np.abs(midpoint - target).max()), 1.5)

    def test_no_old_engraving_remains_away_from_centered_labels(self):
        for name in center.NAMES:
            with self.subTest(die=name):
                folder = center.ASSETS / name / "centered"
                color = Image.open(folder / f"{name}_diffuse.png").convert("RGB")
                normal = np.asarray(Image.open(folder / f"{name}_normal.png")).astype(
                    int
                )
                blank = np.asarray(
                    Image.open(
                        center.ASSETS / "blank-dice" / f"{name}-blank-normal.png"
                    )
                ).astype(int)
                # Allow the engraving lip around the ink plus two antialias pixels.
                radius = max(3, round(color.width / 160)) + 2
                near = ndimage.maximum_filter(
                    center.label_mask(color), size=2 * radius + 1
                )
                residual = np.abs(normal - blank).max(axis=2)
                self.assertLessEqual(int(residual[~near].max()), 2)

    def test_d12_rebuild_does_not_depend_on_published_blank_copy(self):
        original = center.ASSETS
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory)
            shutil.copytree(original / "d12" / "regular", assets / "d12" / "regular")
            shutil.copyfile(original / "catalog.json", assets / "catalog.json")
            # No blank-dice directory: the matching freshly baked map is authoritative.
            with patch.object(center, "ASSETS", assets):
                center.center("d12")
            for kind in ("diffuse", "normal"):
                filename = f"d12_{kind}.png"
                np.testing.assert_array_equal(
                    np.asarray(Image.open(assets / "d12" / "centered" / filename)),
                    np.asarray(Image.open(original / "d12" / "centered" / filename)),
                )


if __name__ == "__main__":
    unittest.main()
