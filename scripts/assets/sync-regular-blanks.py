"""Keep rebuilt numbered and blank geometry, UVs and tangents identical."""

import base64
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2] / "src/assets"
for name in ("d4", "d12"):
    source = ROOT / name / "regular"
    doc = json.loads((source / (name + ".gltf")).read_text())
    material = doc["materials"][0]
    material["pbrMetallicRoughness"].pop("baseColorTexture", None)
    material["pbrMetallicRoughness"]["baseColorFactor"] = [1, 1, 1, 1]
    texture = doc["textures"][material["normalTexture"]["index"]]
    material["normalTexture"] = {**material["normalTexture"], "index": 0}
    doc["images"] = [{"uri": name + "-blank-normal.png", "mimeType": "image/png"}]
    doc["textures"] = [{**texture, "source": 0}]
    for buffer in doc["buffers"]:
        buffer["uri"] = (
            "data:application/octet-stream;base64,"
            + base64.b64encode((source / buffer["uri"]).read_bytes()).decode()
        )
    (ROOT / "blank-dice" / (name + "-blank.gltf")).write_text(
        json.dumps(doc, indent=2) + "\n"
    )
    shutil.copyfile(
        source / (name + "-blank-normal.png"),
        ROOT / "blank-dice" / (name + "-blank-normal.png"),
    )
