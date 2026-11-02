"""Verify numbered and blank dice share the rounded mesh and neutral shading."""

import json
from pathlib import Path
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "src/assets/blank-dice"
SOURCE = ROOT / "src/assets"
NAMES = ("d4", "d6", "d8", "d12", "d20")


class BlankDiceTests(unittest.TestCase):
    def test_classic_and_d6_reuse_the_same_published_buffer(self):
        paths = []
        for name in ("die", "d6"):
            doc = json.loads((SOURCE / name / f"{name}.gltf").read_text())
            paths.append((SOURCE / name / doc["buffers"][0]["uri"]).resolve())
        self.assertEqual(paths[0], paths[1])
        self.assertFalse((SOURCE / "d6/d6.bin").exists())

    def test_blank_variants_are_last_and_retain_catalog_metadata(self):
        catalog = json.loads((SOURCE / "catalog.json").read_text())["pieces"]
        names = ["Classic die", "D4", "D6", "D8", "D12", "D20"]
        self.assertEqual(
            [p["name"] for p in catalog],
            names + ["Pawn"] + [n + " (blank)" for n in names[1:]],
        )
        for original, blank in zip(catalog[1:6], catalog[-5:]):
            for key in ("scale", "rotation", "faces"):
                self.assertEqual(blank[key], original[key])
            self.assertTrue((SOURCE / blank["src"]).is_file())

    def test_rounded_mesh_buffers_and_material_settings_are_shared(self):
        self.assertEqual(
            {p.stem for p in ASSETS.glob("*.gltf")}, {f"{n}-blank" for n in NAMES}
        )
        for name in NAMES:
            with self.subTest(name=name):
                folder = SOURCE / name / "regular"
                source = json.loads((folder / f"{name}.gltf").read_text())
                blank = json.loads((ASSETS / f"{name}-blank.gltf").read_text())
                numbered = json.loads((SOURCE / name / f"{name}.gltf").read_text())
                for key in (
                    "meshes",
                    "nodes",
                    "accessors",
                    "bufferViews",
                    "scenes",
                    "samplers",
                ):
                    self.assertEqual(blank.get(key), source.get(key), key)
                    self.assertEqual(blank.get(key), numbered.get(key), key)
                self.assertEqual(len(source["buffers"]), len(blank["buffers"]))
                for index, (original, output) in enumerate(
                    zip(source["buffers"], blank["buffers"])
                ):
                    shared = (ASSETS / output["uri"]).resolve()
                    expected = (
                        SOURCE / name / numbered["buffers"][index]["uri"]
                    ).resolve()
                    self.assertEqual(
                        shared,
                        expected,
                        "numbered and blank must share the same buffer URL",
                    )
                    self.assertEqual(
                        (folder / original["uri"]).read_bytes(), shared.read_bytes()
                    )
                material = blank["materials"][0]
                self.assertNotIn("baseColorTexture", material["pbrMetallicRoughness"])
                self.assertEqual(
                    material["pbrMetallicRoughness"]["baseColorFactor"], [1, 1, 1, 1]
                )
                self.assertEqual(
                    material["pbrMetallicRoughness"]["roughnessFactor"],
                    source["materials"][0]["pbrMetallicRoughness"]["roughnessFactor"],
                )
                self.assertIn("normalTexture", material)
                original_sampler = source["textures"][
                    source["materials"][0]["normalTexture"]["index"]
                ].get("sampler")
                blank_sampler = blank["textures"][
                    material["normalTexture"]["index"]
                ].get("sampler")
                self.assertEqual(blank_sampler, original_sampler)
                with Image.open(ASSETS / blank["images"][0]["uri"]) as texture:
                    if name in NAMES:
                        self.assertEqual(
                            texture.convert("RGB").getcolors(
                                texture.width * texture.height
                            ),
                            [(texture.width * texture.height, (128, 128, 255))],
                        )
                    elif name in ("d8", "d20"):
                        self.assertGreater(
                            len(texture.getcolors(texture.width * texture.height)), 100
                        )  # baked bevel shading remains


if __name__ == "__main__":
    unittest.main()
