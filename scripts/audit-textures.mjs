// Compare delivered AVIF bytes with the minimum native block payload at the same
// resolution. Headers and mip levels would increase native sizes further.
import { execFileSync } from "node:child_process";
import { readFile, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../showcase/", import.meta.url));
const catalog = JSON.parse(await readFile(join(root, "catalog.json")));
const seen = new Set();
let eligible = 0;
for (const piece of catalog.pieces) {
  const model = JSON.parse(await readFile(join(root, piece.src)));
  for (const { uri } of model.images ?? []) {
    const path = join(dirname(piece.src), uri);
    if (!uri.endsWith(".avif") || seen.has(path)) continue;
    seen.add(path);
    const file = join(root, path);
    const [w, h] = execFileSync("magick", ["identify", "-ping", "-format", "%w %h", file], {
      encoding: "utf8",
    })
      .split(" ")
      .map(Number);
    const bytes = (await stat(file)).size;
    const astc = Math.ceil(w / 12) * Math.ceil(h / 12) * 16;
    const etc2 = Math.ceil(w / 4) * Math.ceil(h / 4) * 8;
    if (Math.min(astc, etc2) <= 1.15 * bytes) eligible++;
    console.log(path, w + "×" + h, "AVIF", bytes, "ASTC ≥", astc, "ETC2 ≥", etc2);
  }
}
console.log(eligible + "/" + seen.size + " color maps eligible for a native-format trial at +15%");
