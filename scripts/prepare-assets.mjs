import { copyFile, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const assets = join(root, "src", "assets");
const texturedPieces = ["d4", "d6", "d8", "d12", "d20", "die"];

const convert = (input, output, args) => execFileSync(
  "magick",
  [input, "-resize", "2048x2048>", "-strip", ...args, output],
  { stdio: "inherit" },
);

for (const name of texturedPieces) {
  const directory = join(assets, name);
  const source = join(directory, "source");
  const normalSource = join(source, name === "die" ? "die_normals.png" : `${name}_normal.png`);
  const diffuseSource = join(source, `${name}_diffuse.png`);
  const normalName = `${name}_normal.png`;
  const previewName = `${name}_preview.webp`;
  const diffuseName = `${name}_diffuse.avif`;

  await copyFile(join(source, `${name}.bin`), join(directory, `${name}.bin`));
  convert(diffuseSource, join(directory, diffuseName), [
    "-define", "heic:speed=6",
    "-quality", "85",
  ]);
  execFileSync("magick", [
    diffuseSource,
    "-resize", "128x128>",
    "-strip",
    "-quality", "55",
    join(directory, previewName),
  ], { stdio: "inherit" });
  convert(normalSource, join(directory, normalName), [
    "-depth", "8",
    "-define", "png:compression-level=9",
    "-define", "png:compression-filter=5",
  ]);

  const gltf = JSON.parse(await readFile(join(source, `${name}.gltf`), "utf8"));
  const preferred = structuredClone(gltf.materials[0]);
  const preview = structuredClone(gltf.materials[0]);
  preferred.name = `${name} preferred`;
  preferred.extensions = {
    ...preferred.extensions,
    MSFT_lod: { ids: [1] },
  };
  preferred.extras = {
    ...preferred.extras,
    MSFT_screencoverage: [0, 0],
  };
  preferred.normalTexture = { ...preferred.normalTexture, index: 0 };
  preferred.pbrMetallicRoughness.baseColorTexture = {
    ...preferred.pbrMetallicRoughness.baseColorTexture,
    index: 1,
  };
  preview.name = `${name} preview`;
  delete preview.normalTexture;
  preview.pbrMetallicRoughness.baseColorTexture = {
    ...preview.pbrMetallicRoughness.baseColorTexture,
    index: 2,
  };

  gltf.extensionsUsed = ["EXT_texture_avif", "EXT_texture_webp", "MSFT_lod"];
  // WebP is the portable material source. Royal selects the authored AVIF when
  // supported and retains the authored preview material while it loads.
  gltf.extensionsRequired = ["EXT_texture_webp"];
  gltf.materials = [preferred, preview];
  gltf.textures = [
    { sampler: 0, source: 0 },
    {
      sampler: 0,
      extensions: {
        EXT_texture_avif: { source: 1 },
        EXT_texture_webp: { source: 2 },
      },
    },
    { sampler: 0, extensions: { EXT_texture_webp: { source: 2 } } },
  ];
  gltf.images = [
    { mimeType: "image/png", name: `${name} normal`, uri: normalName },
    { mimeType: "image/avif", name: `${name} preferred`, uri: diffuseName },
    { mimeType: "image/webp", name: `${name} preview`, uri: previewName },
  ];
  await writeFile(join(directory, `${name}.gltf`), JSON.stringify(gltf));
}

const pawn = join(assets, "pawn");
const pawnGltf = JSON.parse(await readFile(join(pawn, "source", "pawn.gltf"), "utf8"));
await writeFile(join(pawn, "pawn.gltf"), JSON.stringify(pawnGltf));
await copyFile(join(pawn, "source", "pawn.bin"), join(pawn, "pawn.bin"));
