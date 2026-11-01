"""Validate centering and preservation of complete labels, including 6/9 dots."""

import importlib.util
from pathlib import Path
import unittest
import json
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

                    def components(mask):
                        labels, _ = ndimage.label(mask)
                        sizes = np.bincount(labels.ravel())[1:]
                        return int((sizes > 8).sum())

                    self.assertEqual(components(before), components(after))
                    self.assertGreater(after.sum() / before.sum(), 0.7)
                    self.assertLess(after.sum() / before.sum(), 1.05)

    def test_all_labels_align_in_the_rendered_reading_frame(self):
        catalog = json.loads((center.ASSETS / "catalog.json").read_text())["pieces"]
        for name in center.NAMES:
            _, faces = center.face_uvs(name, True)
            entry = next(e for e in catalog if e["name"] == name.upper())
            for published in (False, True):
                path = (
                    center.ASSETS
                    / name
                    / (
                        f"{name}_diffuse.avif"
                        if published
                        else f"centered/{name}_diffuse.png"
                    )
                )
                image = Image.open(path).convert("RGB")
                labels = Image.fromarray(center.label_mask(image))
                heights = []
                for point, polygon, normal, frame in faces:
                    box, inside, _ = center.face_region(
                        point, polygon, image.size, 1.06
                    )
                    bits = np.asarray(labels.crop(box)) & inside
                    components, count = ndimage.label(bits)
                    sizes = np.bincount(components.ravel())
                    sizes[0] = 0
                    parts = (
                        [bits & (sizes[components] >= sizes.max() * 0.1)]
                        if name != "d4"
                        else [
                            components == i
                            for i in range(1, count + 1)
                            if sizes[i] > 20
                        ]
                    )
                    self.assertEqual(len(parts), 1 if name != "d4" else 3)
                    for part in parts:
                        y, x = np.nonzero(part)
                        uv = (np.c_[x, y] + box[:2] + 0.5) / image.size
                        world = np.c_[uv, np.ones(len(x))] @ frame
                        face_centre = np.r_[point, 1] @ frame
                        if name != "d4":
                            pose = max(
                                entry["faces"],
                                key=lambda f: (
                                    center.align.matrix(f["rotation"]) @ normal
                                )[1],
                            )
                            basis = center.align.matrix(pose["rotation"]).T[:, [0, 2]]
                            anchor = face_centre
                        else:
                            corner = polygon[
                                np.argmin(
                                    np.linalg.norm(polygon - uv.mean(axis=0), axis=1)
                                )
                            ]
                            corner_world = np.r_[corner, 1] @ frame
                            up = corner_world - face_centre
                            up /= np.linalg.norm(up)
                            basis = np.array([np.cross(up, normal), -up]).T
                            anchor = face_centre + 0.46 * (corner_world - face_centre)
                        projected = world @ basis
                        midpoint = (projected.min(axis=0) + projected.max(axis=0)) / 2
                        height = np.ptp(projected, axis=0)[1]
                        heights.append(height)
                        with self.subTest(die=name, published=published):
                            self.assertLess(
                                float(np.abs(midpoint - anchor @ basis).max() / height),
                                0.012,
                            )
                self.assertLess(np.ptp(heights) / np.mean(heights), 0.025)

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
