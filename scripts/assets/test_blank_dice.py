"""Verify originals are preserved; compares the original token meshes with their blank variants."""
import base64
import json
from pathlib import Path
import unittest
from PIL import Image, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'src/assets/blank-dice'
SOURCE = ROOT / 'src/assets'
NAMES = ('d4', 'd6', 'd8', 'd12', 'd20', 'd10')

class BlankDiceTests(unittest.TestCase):
    def test_blank_variants_are_last_and_retain_catalog_metadata(self):
        catalog = json.loads((SOURCE / 'catalog.json').read_text())['pieces']
        names = ['Classic die', 'D4', 'D6', 'D8', 'D12', 'D20']
        self.assertEqual([p['name'] for p in catalog], names + ['Pawn'] + [n + ' (blank)' for n in names[1:]] + ['D10', 'D10 (blank)'])
        for original in (p for p in catalog if p["name"].lower() in NAMES):
            blank = next(p for p in catalog if p["name"] == original["name"] + " (blank)")
            for key in ('scale', 'rotation', 'faces'):
                self.assertEqual(blank[key], original[key])
            self.assertTrue((SOURCE / blank['src']).is_file())

    def test_original_mesh_buffers_and_material_settings_are_preserved(self):
        self.assertEqual({p.stem for p in ASSETS.glob('*.gltf')}, {f'{n}-blank' for n in NAMES})
        for name in NAMES:
            with self.subTest(name=name):
                folder = SOURCE / name / 'source'
                source = json.loads((folder / f'{name}.gltf').read_text())
                blank = json.loads((ASSETS / f'{name}-blank.gltf').read_text())
                for key in ('meshes','nodes','accessors','bufferViews','scenes','samplers'):
                    self.assertEqual(blank.get(key), source.get(key), key)
                for original, output in zip(source['buffers'], blank['buffers']):
                    self.assertEqual((folder / original['uri']).read_bytes(), base64.b64decode(output['uri'].split(',')[1]))
                material = blank['materials'][0]
                self.assertNotIn('baseColorTexture', material['pbrMetallicRoughness'])
                self.assertEqual(material['pbrMetallicRoughness']['baseColorFactor'], [1,1,1,1])
                self.assertEqual(material['pbrMetallicRoughness']['roughnessFactor'], source['materials'][0]['pbrMetallicRoughness']['roughnessFactor'])
                self.assertIn('normalTexture', material)
                with Image.open(ASSETS / blank['images'][0]['uri']) as texture:
                    numbered = Image.open(SOURCE / name / f'{name}_normal.webp').convert('RGB')
                    albedo = Image.open(folder / f'{name}_diffuse.png').convert('L')
                    ink = albedo.point(lambda value: 255 if value < 220 else 0)
                    ink = ink.filter(ImageFilter.MaxFilter(21))
                    self.assertEqual(texture.size, numbered.size)
                    delta = ImageChops.difference(texture.convert('RGB'), numbered)
                    self.assertIsNotNone(delta.getbbox(), 'engraving must be removed')
                    delta.paste((0, 0, 0), mask=ink)
                    self.assertIsNone(delta.getbbox(), 'shading changed outside the engraving')

if __name__ == '__main__':
    unittest.main()
