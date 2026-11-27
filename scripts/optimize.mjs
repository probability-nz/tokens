// Optimize catalog geometry in place, retaining resource names and shared buffers.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve, relative, posix } from "node:path";
import { fileURLToPath } from "node:url";
import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer";

const root = fileURLToPath(new URL("../", import.meta.url));
const assets = join(root, "src/assets");
const showcase = join(root, "showcase");
const readJson = async (path) => JSON.parse(await readFile(path));
const extension = "EXT_meshopt_compression";
const release = await readJson(join(showcase, "release.json"));
const records = new Map(release.files.map((file) => [file.path, file]));
const groups = new Map();
await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready]);

// Blank dice and colour variants can reference the same file. Decide for the
// entire group before writing anything, counting every model's extension cost.
for (const collection of ["classic", "cc0", "game-pieces"]) {
  const dir = collection === "classic" ? assets : join(assets, collection);
  for (const { src } of (await readJson(join(dir, "catalog.json"))).pieces) {
    assert(src.endsWith(".gltf"), src);
    const file = join(dir, src);
    const model = await readJson(file);
    if (model.buffers.length !== 1 || model.extensionsRequired?.includes(extension)) continue;
    const buffer = resolve(dirname(file), model.buffers[0].uri);
    const path = posix.join(collection, src);
    const published = records.has(path) ? path : path.replace(/^cc0\/shapes\//, "showcase/shapes/");
    assert(records.has(published), published);
    if (!groups.has(buffer)) groups.set(buffer, []);
    groups.get(buffer).push({ file, model, published });
  }
}

function encode(model, raw) {
  const result = structuredClone(model);
  const chunks = [];
  let offset = 0;
  for (const [i, view] of result.bufferViews.entries()) {
    const accessors = result.accessors.filter((a) => a.bufferView === i);
    const first = accessors[0];
    if (!first || view.buffer !== 0 || view.extensions) return;
    const index = view.target === 34963;
    const components = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };
    const size = { 5121: 1, 5123: 2, 5125: 4, 5126: 4 }[first.componentType];
    const stride = view.byteStride ?? components[first.type] * size;
    if (!stride || view.byteLength % stride || (!index && stride % 4)) return;
    const start = view.byteOffset ?? 0;
    const bytes = raw.subarray(start, start + view.byteLength);
    const count = bytes.length / stride;
    const mode = index ? "INDICES" : "ATTRIBUTES";
    const packed = MeshoptEncoder.encodeGltfBuffer(bytes, count, stride, mode, 0);
    const decoded = Buffer.alloc(bytes.length);
    MeshoptDecoder.decodeGltfBuffer(decoded, count, stride, packed, mode);
    assert(bytes.equals(decoded), "Lossless round trip failed");
    view.buffer = 1;
    view.extensions = {
      [extension]: {
        buffer: 0,
        byteOffset: offset,
        byteLength: packed.length,
        byteStride: stride,
        count,
        mode,
      },
    };
    chunks.push(packed);
    offset += packed.length;
  }
  result.buffers.push({ byteLength: raw.length, extensions: { [extension]: { fallback: true } } });
  result.buffers[0].byteLength = offset;
  for (const key of ["extensionsRequired", "extensionsUsed"]) {
    result[key] = [...new Set([...(result[key] ?? []), extension])];
  }
  return { binary: Buffer.concat(chunks), model: result };
}

async function publish(file, path, data) {
  await writeFile(file, data);
  // Some legacy showcase entries already ship their own optimized buffers.
  if (!path) return;
  assert(records.has(path), path);
  await writeFile(join(showcase, path), data);
  Object.assign(records.get(path), {
    bytes: data.length,
    sha256: createHash("sha256").update(data).digest("hex"),
  });
}
let saved = 0,
  optimized = 0;
for (const [file, entries] of groups) {
  const raw = await readFile(file);
  for (const { model } of entries) assert.equal(raw.length, model.buffers[0].byteLength, file);
  const candidates = entries.map(({ model }) => encode(model, raw));
  if (candidates.some((candidate) => !candidate)) continue;
  const [{ binary }] = candidates;
  assert(
    candidates.every((candidate) => candidate.binary.equals(binary)),
    "Shared buffer layouts disagree",
  );
  const overhead = entries.reduce(
    (sum, { model }, i) =>
      sum + JSON.stringify(candidates[i].model).length - JSON.stringify(model).length,
    0,
  );
  if (binary.length + overhead >= raw.length) continue;
  const first = entries[0];
  const bufferPath = posix.join(posix.dirname(first.published), first.model.buffers[0].uri);
  const publishShared = records.has(bufferPath);
  if (!publishShared) assert.equal(first.published, "classic/pawn/pawn.gltf");
  await publish(file, publishShared ? bufferPath : null, binary);
  for (const [i, entry] of entries.entries()) {
    const data = Buffer.from(JSON.stringify(candidates[i].model) + "\n");
    await publish(entry.file, publishShared ? entry.published : null, data);
  }
  saved += raw.length - binary.length;
  optimized += entries.length;
  console.log(relative(assets, file), raw.length, "→", binary.length);
}
await writeFile(join(showcase, "release.json"), JSON.stringify(release, null, 2) + "\n");
console.log(optimized + " models optimized, " + saved + " unique buffer bytes saved");
