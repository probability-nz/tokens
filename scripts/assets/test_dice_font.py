"""The downloadable font must be the exact licensed source used by the renderer."""

import hashlib
import json
from pathlib import Path
import unittest
import subprocess
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[2]


class SharedFontTests(unittest.TestCase):
    def test_shared_font_provenance_and_distribution(self):
        subprocess.run(["node", "scripts/build-catalog.mjs"], cwd=ROOT, check=True)
        source = ROOT / "src/assets/fonts"
        metadata = json.loads((source / "source.json").read_text())
        font = source / "ComicNeue-Bold.ttf"
        self.assertEqual(
            hashlib.sha256(font.read_bytes()).hexdigest(), metadata["sha256"]
        )
        self.assertEqual(
            ImageFont.truetype(str(font), 32).getname(), ("Comic Neue", "Bold")
        )
        self.assertIn(
            "SIL OPEN FONT LICENSE Version 1.1", (source / "OFL.txt").read_text()
        )
        for path in source.iterdir():
            self.assertEqual(
                path.read_bytes(), (ROOT / "dist/fonts" / path.name).read_bytes()
            )
