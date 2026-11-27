import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import { posix, join, relative, sep } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { MeshoptDecoder } from "meshoptimizer";

const root = fileURLToPath(new URL("../showcase/", import.meta.url));
test("showcase models load from verified external resources", async () => {
  const release = JSON.parse(await readFile(join(root, "release.json")));
  const catalog = JSON.parse(await readFile(join(root, "catalog.json")));
  const resources = new Map();
  for (const file of release.files) {
    const bytes = await readFile(join(root, file.path));
    assert.equal(bytes.length, file.bytes, file.path);
    assert.equal(createHash("sha256").update(bytes).digest("hex"), file.sha256, file.path);
    resources.set(file.path, bytes);
  }
  assert.equal(resources.size, release.files.length, "Duplicate manifest paths");
  const published = (await readdir(root, { recursive: true, withFileTypes: true }))
    .filter((entry) => entry.isFile())
    .map((entry) => relative(root, join(entry.parentPath, entry.name)).split(sep).join("/"));
  assert.deepEqual(new Set(published), new Set([
    ...resources.keys(), "CC0-LICENSE.txt", "CREDITS.txt", "package.json", "release.json",
  ]));
  const paths = catalog.pieces.map((p) => p.src);
  assert.equal(new Set(paths).size, paths.length, "Duplicate catalog models");
  assert.deepEqual(release.game.children.map((p) => p.src).sort(), paths.sort());
  await MeshoptDecoder.ready;
  for (const { src } of catalog.pieces) {
    assert(src.endsWith(".gltf"), src);
    const model = JSON.parse(resources.get(src));
    const notice = model.asset.copyright;
    if (src.startsWith("classic/")) {
      assert.match(notice, /Garbo Succus.*Misha Tsyatsko.*CC-BY-4\.0/, src);
    } else if (src.startsWith("game-pieces/")) {
      assert.match(notice, /Jarlan Perez.*CC BY 3\.0/, src);
    } else {
      assert.match(notice, /CC0[- ]1\.0/, src);
    }
    const resource = (uri) => {
      assert(uri && !uri.startsWith("data:"), src);
      const bytes = resources.get(posix.join(posix.dirname(src), uri));
      assert(bytes, src + " missing " + uri);
      return bytes;
    };
    for (const image of model.images ?? []) resource(image.uri);
    const buffers = model.buffers.map((buffer) => {
      if (!buffer.uri) {
        assert.equal(buffer.extensions?.EXT_meshopt_compression?.fallback, true, src);
        return;
      }
      const bytes = resource(buffer.uri);
      assert.equal(bytes.length, buffer.byteLength, src);
      return bytes;
    });
    for (const view of model.bufferViews) {
      const packed = view.extensions?.EXT_meshopt_compression;
      if (!packed) continue;
      const offset = packed.byteOffset ?? 0;
      const bytes = buffers[packed.buffer].subarray(offset, offset + packed.byteLength);
      assert.equal(bytes.length, packed.byteLength, src);
      assert.equal(view.byteLength, packed.count * packed.byteStride, src);
      MeshoptDecoder.decodeGltfBuffer(
        new Uint8Array(view.byteLength),
        packed.count,
        packed.byteStride,
        bytes,
        packed.mode,
        packed.filter,
      );
    }
  }
});
