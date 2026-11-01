"""Build all blank glTFs from numbered sources, sharing published mesh buffers."""

import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2] / "src/assets"
for name in ("d4", "d6", "d8", "d12", "d20"):
    regular = name in ("d4", "d12")
    source = ROOT / name / ("regular" if regular else "source")
    doc = json.loads((source / (name + ".gltf")).read_text())
    material = doc["materials"][0]
    material["pbrMetallicRoughness"].pop("baseColorTexture", None)
    material["pbrMetallicRoughness"]["baseColorFactor"] = [1, 1, 1, 1]
    texture = doc["textures"][material["normalTexture"]["index"]]
    material["normalTexture"] = {**material["normalTexture"], "index": 0}
    doc["images"] = [{"uri": name + "-blank-normal.png", "mimeType": "image/png"}]
    doc["textures"] = [{**texture, "source": 0}]
    for buffer in doc["buffers"]:
        filename = buffer["uri"]
        if Path(filename).name != filename:
            raise ValueError(f"{name}: expected a buffer beside the numbered source")
        published = ROOT / name / filename
        if published.read_bytes() != (source / filename).read_bytes():
            raise ValueError(
                f"{name}: prepare the numbered asset before syncing blanks"
            )
        buffer["uri"] = f"../{name}/{filename}"
    (ROOT / "blank-dice" / (name + "-blank.gltf")).write_text(
        json.dumps(doc, indent=2) + "\n"
    )
    if regular:
        shutil.copyfile(
            source / (name + "-blank-normal.png"),
            ROOT / "blank-dice" / (name + "-blank-normal.png"),
        )
