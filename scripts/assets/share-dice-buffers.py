"""Share byte-identical published dice buffers, retaining self-contained bake inputs."""

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src/assets"
shared = {}
for name in ("die", "d4", "d6", "d8", "d12", "d20"):
    path = ROOT / name / f"{name}.gltf"
    doc = json.loads(path.read_text())
    for buffer in doc["buffers"]:
        source = (path.parent / buffer["uri"]).resolve()
        source.relative_to(ROOT)
        data = source.read_bytes()
        digest = hashlib.sha256(data).digest()
        target = shared.setdefault(digest, source)
        if source == target:
            continue
        assert data == target.read_bytes()
        buffer["uri"] = Path(os.path.relpath(target, path.parent)).as_posix()
        # Only remove this model's old private copy. Other models may already
        # reference a shared file elsewhere in the catalog.
        if source.parent == path.parent:
            source.unlink()
    path.write_text(json.dumps(doc, indent=2) + "\n")
