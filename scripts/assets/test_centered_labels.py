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
    def test_rounded_groove_has_curved_sides_and_a_smooth_recessed_floor(self):
        # A 0.6 mm stroke at 100 px/mm: sample well inside the old 0.08 mm
        # rim to catch a regression back to a flat-bottomed outline.
        pixels = np.full((512, 512, 3), 255, dtype=np.uint8)
        pixels[180:332, 226:286] = 0
        normal = np.asarray(
            center.engraving_normal(
                Image.fromarray(pixels),
                Image.new("RGB", (512, 512), (128, 128, 255)),
                100,
            )
        ).astype(float)
        x = (normal[256, :, 0] - 127.5) / 127.5
        self.assertGreater(x[238], 0.25)
        self.assertLess(x[273], -0.25)
        self.assertGreater(x[238], x[249])
        self.assertLess(abs(x[255]), 0.06)
        self.assertLess(np.max(np.abs(np.diff(x[245:267]))), 0.08)
        np.testing.assert_array_equal(normal[256, 200], [128, 128, 255])

    def test_pip_floor_is_spherical_instead_of_flat(self):
        y, x = np.indices((512, 512))
        disk = (x - 256) ** 2 + (y - 256) ** 2 <= 50**2
        color = np.full((512, 512, 3), 255, dtype=np.uint8)
        color[disk] = 0
        normal = np.asarray(
            center.engraving_normal(
                Image.fromarray(color),
                Image.new("RGB", (512, 512), (128, 128, 255)),
                100,
                spherical_pips=True,
            )
        ).astype(float)
        # A ball-cut floor tilts progressively farther from the centre, in
        # both axes. The former stroke profile had an almost flat broad floor.
        nx = (normal[256, :, 0] - 127.5) / 127.5
        self.assertLess(abs(nx[256]), 0.01)
        self.assertGreater(nx[246], 0.15)
        self.assertGreater(nx[226], nx[246] * 2.5)
        self.assertAlmostEqual(nx[226], -nx[286], delta=0.01)
        self.assertAlmostEqual(normal[226, 256, 1], 255 - normal[256, 226, 0], delta=1)
        np.testing.assert_array_equal(normal[256, 190], [128, 128, 255])

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
                        return int(
                            (
                                sizes
                                > (max(8, sizes.max() * 0.05) if name == "d4" else 8)
                            ).sum()
                        )

                    self.assertEqual(components(before), components(after))
                    # Set-wide sizing intentionally changes the ink area. Keep
                    # every component, including disambiguation dots, legible.
                    self.assertGreater(int(after.sum()), 16)

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
        for name in ("die", *center.NAMES):
            with self.subTest(die=name):
                folder = center.ASSETS / name / "centered"
                color = Image.open(folder / f"{name}_diffuse.png").convert("RGB")
                normal = np.asarray(Image.open(folder / f"{name}_normal.png")).astype(
                    int
                )
                blank = np.asarray(
                    Image.open(center.ASSETS / "blank-dice" / "flat-normal.png")
                ).astype(int)
                # Allow the engraving lip around the ink plus two antialias pixels.
                radius = max(3, round(color.width / 160)) + 2
                near = ndimage.maximum_filter(
                    center.label_mask(color), size=2 * radius + 1
                )
                residual = np.abs(normal - blank).max(axis=2)
                self.assertLessEqual(int(residual[~near].max()), 2)

    def test_engraving_tracks_print_edges_and_points_into_the_die(self):
        # Check the actual saved maps, independent of the generation helper.
        for name in ("die", *center.NAMES):
            for published in (False, True):
                folder = center.ASSETS / name
                color = Image.open(
                    folder
                    / (
                        f"{name}_diffuse.avif"
                        if published
                        else f"centered/{name}_diffuse.png"
                    )
                ).convert("RGB")
                normal = Image.open(
                    folder
                    / (
                        f"{name}_normal.webp"
                        if published
                        else f"centered/{name}_normal.png"
                    )
                ).convert("RGB")
                blank = (
                    Image.open(center.ASSETS / "blank-dice" / "flat-normal.png")
                    .convert("RGB")
                    .resize(normal.size, Image.Resampling.LANCZOS)
                )
                ink = center.label_mask(
                    color.resize(normal.size, Image.Resampling.LANCZOS)
                )
                inward_y, inward_x = np.gradient(
                    ndimage.gaussian_filter(ink.astype(float), 1)
                )
                residual = np.asarray(normal).astype(float) - np.asarray(blank)
                edge = (inward_x * inward_x + inward_y * inward_y) > 0.02
                # Inset glyphs tilt toward their centre: +U follows image X,
                # but tangent +V opposes image rows. Reversed signs emboss them.
                dot = residual[..., 0] * inward_x - residual[..., 1] * inward_y
                with self.subTest(die=name, published=published):
                    self.assertGreater(np.mean(dot[edge] > 0), 0.97)
                    near_edge = ndimage.maximum_filter(edge, size=9)
                    changed = np.linalg.norm(residual, axis=-1) > 8
                    self.assertLess(np.mean(changed[~(near_edge | ink)]), 0.0001)

    def test_face_boundaries_have_white_filtering_padding(self):
        for name in ("die", *center.NAMES):
            _, faces = center.face_uvs(name)
            for published in (False, True):
                image = Image.open(
                    center.ASSETS
                    / name
                    / (
                        f"{name}_diffuse.avif"
                        if published
                        else f"centered/{name}_diffuse.png"
                    )
                ).convert("RGB")
                pixels = np.asarray(image)
                for _, polygon, _ in faces:
                    for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
                        for t in np.linspace(0, 1, 25):
                            x, y = np.rint(
                                ((1 - t) * a + t * b) * image.size - 0.5
                            ).astype(int)
                            patch = pixels[
                                max(0, y - 1) : min(image.height, y + 2),
                                max(0, x - 1) : min(image.width, x + 2),
                            ]
                            with self.subTest(die=name, published=published):
                                self.assertGreater(int(patch.min()), 240)

    def test_classic_pip_counts_match_every_roll_outcome(self):
        entry = next(
            e
            for e in json.loads((center.ASSETS / "catalog.json").read_text())["pieces"]
            if e["name"] == "Classic die"
        )
        _, faces = center.face_uvs("die")
        image = Image.open(center.ASSETS / "die/die_diffuse.avif").convert("RGB")
        ink = Image.fromarray(center.label_mask(image))
        for outcome in entry["faces"]:
            rotation = center.align.matrix(outcome["rotation"])
            point, polygon, _ = max(faces, key=lambda f: (rotation @ f[2])[1])
            box, inside, _ = center.face_region(point, polygon, image.size)
            labels, _ = ndimage.label(np.asarray(ink.crop(box)) & inside)
            sizes = np.bincount(labels.ravel())[1:]
            self.assertEqual(int(np.count_nonzero(sizes > 20)), int(outcome["name"]))

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
