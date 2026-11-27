// SPDX-License-Identifier: CC0-1.0
// Build into scratch space before updating the published catalog and Play game.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { MeshoptEncoder } from "meshoptimizer";
import { generateBoardArt } from "./board-art.mjs";
import { generateCheckers } from "./checkers.mjs";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const families = {
  boards: null,
  dominoes: "dominoes.py",
  "poker-chips": "poker_chips.py",
  checkers: null,
};
const family = process.argv[2];
if (!Object.hasOwn(families, family))
  throw new Error("Expected boards, dominoes, poker-chips or checkers");
const collection = family === "checkers" ? "game-pieces" : "cc0";
const scratch = await mkdtemp(join(tmpdir(), "tokens-tabletop-"));
const output = join(scratch, "output");
const sha = (data) => createHash("sha256").update(data).digest("hex");
const json = async (path) => JSON.parse(await readFile(path, "utf8"));

async function packMesh(slug, recipe) {
  const domino = family === "dominoes";
  const raw = await readFile(join(scratch, slug + ".raw"));
  const { counts, bounds, images, material, name } = recipe;
  const buffers = [],
    bufferViews = [],
    accessors = [];
  const groups = domino ? [[], []] : [[]];
  const offsets = groups.map(() => 0);
  let offset = 0;
  for (const [i, stride] of [12, 12, 8, 16, 2].entries()) {
    const count = counts[i],
      length = count * stride,
      index = i === 4;
    const mode = index ? "INDICES" : "ATTRIBUTES";
    const group = domino && i === 2 ? 1 : 0; // Only the atlas coordinates vary by domino.
    const bytes = MeshoptEncoder.encodeGltfBuffer(
      raw.subarray(offset, offset + length),
      count,
      stride,
      mode,
      0,
    );
    groups[group].push(bytes);
    bufferViews.push({
      buffer: groups.length,
      byteOffset: offset,
      byteLength: length,
      target: index ? 34963 : 34962,
      extensions: {
        EXT_meshopt_compression: {
          buffer: group,
          byteOffset: offsets[group],
          byteLength: bytes.length,
          byteStride: stride,
          count,
          mode,
        },
      },
    });
    accessors.push({
      bufferView: i,
      componentType: index ? 5123 : 5126,
      count,
      type: index ? "SCALAR" : "VEC" + stride / 4,
    });
    offsets[group] += bytes.length;
    offset += length;
  }
  if (offset !== raw.length) throw new Error("Incorrect stream lengths for " + slug);
  for (const chunks of groups) {
    const binary = Buffer.concat(chunks);
    const uri = sha(binary).slice(0, 20) + ".bin";
    await writeFile(join(output, uri), binary);
    buffers.push({ uri, byteLength: binary.length });
  }
  buffers.push({
    byteLength: raw.length,
    extensions: { EXT_meshopt_compression: { fallback: true } },
  });
  Object.assign(accessors[0], { min: bounds[0], max: bounds[1] });
  for (const image of images) await cp(join(scratch, image), join(output, image));
  const extensions = ["EXT_texture_avif", "EXT_texture_webp", "EXT_meshopt_compression"];
  const model = {
    asset: { version: "2.0", copyright: "CC0-1.0" },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ name, mesh: 0 }],
    meshes: [
      {
        primitives: [
          {
            attributes: { POSITION: 0, NORMAL: 1, TEXCOORD_0: 2, TANGENT: 3 },
            indices: 4,
            material: 0,
          },
        ],
      },
    ],
    materials: [material],
    buffers,
    bufferViews,
    accessors,
    images: images.map((uri) => ({ uri, mimeType: "image/" + uri.split(".").at(-1) })),
    textures: images.map((_, i) => ({ extensions: { [extensions[i]]: { source: i } } })),
    extensionsUsed: extensions,
    extensionsRequired: extensions,
  };
  await writeFile(join(output, slug + ".gltf"), JSON.stringify(model) + "\n");
}

async function publish() {
  const dest = join(root, "src/assets", collection, family);
  await mkdir(dest, { recursive: true });
  const showcase = join(root, "showcase");
  const releasePath = join(showcase, "release.json");
  const release = await json(releasePath);
  const records = new Map(release.files.map((file) => [file.path, file]));
  const mime = {
    bin: "application/octet-stream",
    gltf: "model/gltf+json",
    avif: "image/avif",
    webp: "image/webp",
  };
  const generated = await readdir(output);
  for (const entry of generated) {
    if (entry === "source") {
      await cp(join(output, entry), join(dest, entry), { recursive: true });
      continue;
    }
    let bytes = await readFile(join(output, entry));
    const extension = entry.split(".").at(-1);
    const target = join(dest, entry);
    // Preserve the existing serialization when it represents the generated model.
    if (extension === "gltf") {
      const existing = await readFile(target).catch((error) => {
        if (error.code !== "ENOENT") throw error;
      });
      if (existing && isDeepStrictEqual(JSON.parse(existing), JSON.parse(bytes))) bytes = existing;
    }
    const path = [collection, family, entry].join("/");
    await mkdir(dirname(join(showcase, path)), { recursive: true });
    await writeFile(target, bytes);
    await writeFile(join(showcase, path), bytes);
    records.set(path, {
      path,
      mediaType: mime[extension],
      bytes: bytes.length,
      sha256: sha(bytes),
    });
  }
  // Retire old content-addressed resources only inside this fully rebuilt family.
  for (const entry of await readdir(dest)) {
    if (!/^[a-f0-9]{20}\.(avif|webp|bin)$/.test(entry) || generated.includes(entry)) continue;
    const path = [collection, family, entry].join("/");
    if (!records.has(path)) continue;
    records.delete(path);
    await rm(join(dest, entry));
    await rm(join(showcase, path), { force: true });
  }
  release.files = [...records.values()].sort((a, b) =>
    a.path < b.path ? -1 : a.path > b.path ? 1 : 0,
  );
  await writeFile(releasePath, JSON.stringify(release, null, 2) + "\n");
}

try {
  await mkdir(output);
  if (family === "boards")
    await generateBoardArt(join(root, "src/assets/cc0/boards"), output, scratch);
  else if (family === "checkers") generateCheckers(output);
  else {
    execFileSync(
      "python3",
      ["-B", join(root, "src/generators/tabletop", families[family]), scratch],
      {
        stdio: "inherit",
      },
    );
    await MeshoptEncoder.ready;
    for (const file of (await readdir(scratch)).filter((file) => file.endsWith(".json"))) {
      await packMesh(file.slice(0, -5), await json(join(scratch, file)));
    }
    await cp(join(scratch, "source"), join(output, "source"), { recursive: true });
  }
  await publish();
} finally {
  await rm(scratch, { recursive: true, force: true });
}
