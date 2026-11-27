import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { notices } from './asset-notices.mjs';
import { zipSync } from 'fflate';

const root = fileURLToPath(new URL('../', import.meta.url));
const read = (name) => readFile(join(root, 'showcase', name));
const entries = Object.create(null);
for (const name of ['package.json', 'release.json', 'CC0-LICENSE.txt', 'CREDITS.txt']) {
  entries[name] = await read(name);
}
for (const { path, bytes, sha256 } of JSON.parse(entries['release.json']).files) {
  assert(!Object.hasOwn(entries, path), path);
  const data = await read(path);
  assert.equal(data.length, bytes, path);
  assert.equal(createHash('sha256').update(data).digest('hex'), sha256, path);
  entries[path] = data;
}
for (const { showcase, source } of notices) {
  assert.deepEqual(entries[showcase], await readFile(join(root, 'src/assets', source)), showcase);
}
const archive = zipSync(entries, { level: 6, mtime: new Date(2000, 0, 1) });
await mkdir(join(root, 'dist'), { recursive: true });
await writeFile(join(root, 'dist/tokens-showcase.zip'), archive);
