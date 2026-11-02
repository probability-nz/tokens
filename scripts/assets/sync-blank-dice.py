"""Build all blank glTFs from numbered sources, sharing published mesh buffers."""

import json
import os
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2] / "src/assets"
# All blanks share one neutral texel; curved shading comes from the meshes.
Image.new("RGB", (1, 1), (128, 128, 255)).save(ROOT / "blank-dice/flat-normal.png")
for name in ("d4", "d6", "d8", "d12", "d20"):
    source = ROOT / name / "regular"
    doc = json.loads((source / (name + ".gltf")).read_text())
    numbered = json.loads((ROOT / name / (name + ".gltf")).read_text())
    material = doc["materials"][0]
    material["pbrMetallicRoughness"].pop("baseColorTexture", None)
    material["pbrMetallicRoughness"]["baseColorFactor"] = [1, 1, 1, 1]
    texture = doc["textures"][material["normalTexture"]["index"]]
    material["normalTexture"] = {**material["normalTexture"], "index": 0}
    doc["images"] = [{"uri": "flat-normal.png", "mimeType": "image/png"}]
    doc["textures"] = [{**texture, "source": 0}]
    for index, buffer in enumerate(doc["buffers"]):
        filename = buffer["uri"]
        if Path(filename).name != filename:
            raise ValueError(f"{name}: expected a buffer beside the numbered source")
        published = (ROOT / name / numbered["buffers"][index]["uri"]).resolve()
        published.relative_to(ROOT)
        if published.read_bytes() != (source / filename).read_bytes():
            raise ValueError(
                f"{name}: prepare the numbered asset before syncing blanks"
            )
        buffer["uri"] = Path(os.path.relpath(published, ROOT / "blank-dice")).as_posix()
    (ROOT / "blank-dice" / (name + "-blank.gltf")).write_text(
        json.dumps(doc, indent=2) + "\n"
    )
