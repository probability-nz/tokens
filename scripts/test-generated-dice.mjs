import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const root = fileURLToPath(new URL('..', import.meta.url));
const json = async (file) => JSON.parse(await readFile(file, 'utf8'));
for (const collection of ['classic', 'cc0']) {
  test(
    collection + ' generated meshes match the published showcase',
    async () => {
      const dir = join(
        root,
        'src/assets',
        collection === 'classic' ? '' : collection,
      );
      const { pieces } = await json(join(dir, 'catalog.json'));
      const showcase = await json(join(root, 'showcase/catalog.json'));
      for (const piece of pieces.filter(
        (p) => p.name === 'Classic die' || /^D\d+( \(blank\))?$/.test(p.name),
      )) {
        const file = join(dir, piece.src),
          gltf = await json(file);
        const published = showcase.pieces.find(
          (p) => p.src === join(collection, piece.src),
        );
        assert.deepEqual(published.faces, piece.faces);
        assert.deepEqual(piece.rotation, piece.faces[0].rotation);
        const n =
          piece.name === 'Classic die' ? 6 : Number(piece.name.match(/\d+/)[0]);
        assert.deepEqual(
          piece.faces.map((f) => f.name),
          Array.from({ length: n }, (_, i) => String(i + (n === 10 ? 0 : 1))),
        );
        assert.deepEqual(
          await json(join(root, 'showcase', collection, piece.src)),
          gltf,
        );
        for (const asset of [...gltf.buffers, ...(gltf.images ?? [])]) {
          const data = await readFile(join(dirname(file), asset.uri));
          assert.deepEqual(
            await readFile(
              join(root, 'showcase', collection, dirname(piece.src), asset.uri),
            ),
            data,
          );
          if (asset.byteLength !== undefined)
            assert.equal(asset.byteLength, data.length);
        }
        if (piece.name.endsWith(' (blank)')) {
          const numbered = pieces.find(
            (p) => p.name + ' (blank)' === piece.name,
          );
          const original = await json(join(dir, numbered.src));
          assert.deepEqual(piece.faces, numbered.faces);
          assert.deepEqual(gltf.accessors, original.accessors);
          assert.equal(
            join(dirname(piece.src), gltf.buffers[0].uri),
            join(dirname(numbered.src), original.buffers[0].uri),
          );
          assert.equal(gltf.images, undefined);
        } else {
          assert.ok(gltf.materials[0].normalTexture);
        }
      }
    },
  );
}
