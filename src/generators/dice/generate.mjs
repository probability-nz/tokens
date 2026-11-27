// Regenerate checked-in catalog assets one die at a time. Ordinary builds consume the published files.
import settings from "../texture-settings.json" with { type: "json" };
import { chromium } from 'playwright-core';
import { createServer } from 'vite';
import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import {
  cp,
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, dirname, extname, join, posix, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const assets = join(root, 'src/assets');
const readJson = async (path) => JSON.parse(await readFile(path, 'utf8'));
const writeJson = (path, data) =>
  writeFile(path, JSON.stringify(data, null, 2) + '\n');
const run = promisify(execFile);
const scratch = await mkdtemp(join(tmpdir(), 'tokens-dice-'));
const output = join(scratch, 'generated');
const showcase = join(output, 'showcase');
const collections = await Promise.all(
  ['classic', 'cc0'].map(async (key) => {
    const dir = key === 'classic' ? assets : join(assets, key);
    return {
      key,
      dir: join(output, relative(root, dir)),
      catalog: await readJson(join(dir, 'catalog.json')),
    };
  }),
);
const combined = await readJson(join(root, 'showcase/catalog.json'));
const release = await readJson(join(root, 'showcase/release.json'));
const records = new Map(release.files.map((f) => [f.path, f]));
const mime = {
  '.gltf': 'model/gltf+json',
  '.bin': 'application/octet-stream',
  '.avif': 'image/avif',
  '.webp': 'image/webp',
  '.json': 'application/json',
};

async function record(path) {
  const data = await readFile(join(showcase, path));
  records.set(path, {
    path,
    mediaType: mime[extname(path)],
    bytes: data.length,
    sha256: createHash('sha256').update(data).digest('hex'),
  });
}
async function publish(collection, path) {
  const dest = posix.join(collection.key, path);
  await mkdir(dirname(join(showcase, dest)), { recursive: true });
  await copyFile(join(collection.dir, path), join(showcase, dest));
  await record(dest);
}
function packMesh(mesh, scale) {
  // Index all attributes together, preserving UV and normal seams.
  const unique = new Map(),
    positions = [],
    normals = [],
    uvs = [],
    indices = [];
  for (let i = 0; i < mesh.position.length / 3; i++) {
    const p = mesh.position
      .slice(i * 3, i * 3 + 3)
      .map((n, k) => Math.fround(n / (1000 * scale[k])));
    const n = mesh.normal.slice(i * 3, i * 3 + 3),
      uv = mesh.uv.slice(i * 2, i * 2 + 2);
    const key = [...p, ...n, ...uv].join(',');
    let index = unique.get(key);
    if (index === undefined) {
      index = unique.size;
      unique.set(key, index);
      positions.push(...p);
      normals.push(...n);
      uvs.push(...uv);
    }
    indices.push(index);
  }
  const arrays = [
    new Float32Array(positions),
    new Float32Array(normals),
    new Float32Array(uvs),
    unique.size > 65535 ? new Uint32Array(indices) : new Uint16Array(indices),
  ];
  let byteOffset = 0;
  const bufferViews = arrays.map((a, i) => {
    const view = {
      buffer: 0,
      byteOffset,
      byteLength: a.byteLength,
      target: i === 3 ? 34963 : 34962,
    };
    byteOffset += a.byteLength;
    return view;
  });
  const min = [Infinity, Infinity, Infinity],
    max = min.map(() => -Infinity);
  positions.forEach((v, i) => {
    min[i % 3] = Math.min(min[i % 3], v);
    max[i % 3] = Math.max(max[i % 3], v);
  });
  const accessors = arrays.map((a, i) => ({
    bufferView: i,
    componentType: i === 3 ? (a.BYTES_PER_ELEMENT === 2 ? 5123 : 5125) : 5126,
    count: i === 3 ? indices.length : unique.size,
    type: ['VEC3', 'VEC3', 'VEC2', 'SCALAR'][i],
    ...(i === 0 ? { min, max } : {}),
  }));
  return {
    data: Buffer.concat(arrays.map((a) => Buffer.from(a.buffer))),
    accessors,
    bufferViews,
    size: max.map((v, i) => (v - min[i]) * scale[i]),
  };
}

async function generate(page, kind) {
  const collection = collections.find((c) =>
    c.catalog.pieces.some((p) => p.name === kind),
  );
  const piece = collection.catalog.pieces.find((p) => p.name === kind);
  const mesh = await page.evaluate(
    async (kind) =>
      (await import('/src/generators/dice/export-die.ts')).exportDie(kind),
    kind,
  );
  const file = join(collection.dir, piece.src),
    dir = dirname(file),
    stem = basename(file, '.gltf');
  // Output names are part of the existing public catalog ABI.
  const binary = stem + (kind === 'D100' ? '-rounded.bin' : '.bin');
  const color =
    stem +
    (kind === 'D100'
      ? '-color.avif'
      : collection.key === 'classic'
        ? '_diffuse.avif'
        : '.avif');
  const preview =
    stem +
    (collection.key === 'classic' || kind === 'D100'
      ? '_preview.webp'
      : '.webp');
  await mkdir(dir, { recursive: true });
  const normal = stem + '_normal.webp';
  const { data, bufferViews, accessors, size } = packMesh(mesh, piece.scale);
  await writeFile(join(dir, binary), data);
  await writeFile(
    join(scratch, 'color.png'),
    Buffer.from(mesh.color, 'base64'),
  );
  await writeFile(
    join(scratch, 'normal.png'),
    Buffer.from(mesh.relief, 'base64'),
  );
  async function convert(source, options, destination) {
    await run('magick', [
      '-limit',
      'thread',
      '1',
      join(scratch, source),
      '-strip',
      ...options,
      join(dir, destination),
    ]);
  }
  await convert(
    'color.png',
    ['-define', 'heic:speed=6', '-quality', String(settings.avifQuality)],
    color,
  );
  await convert(
    'color.png',
    ['-resize', '128x128>', '-quality', String(settings.previewQuality)],
    preview,
  );
  await convert(
    'normal.png',
    ['-depth', '8', '-define', 'webp:lossless=true'],
    normal,
  );
  const pbr = {
    baseColorFactor: [1, 1, 1, 1],
    metallicFactor: 0,
    roughnessFactor: 0.48,
  };
  const base = {
    asset: { version: '2.0', generator: 'tokens procedural dice' },
    extras: { probability: { faces: mesh.faces } },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0, name: kind }],
    meshes: [
      {
        primitives: [
          {
            attributes: { POSITION: 0, NORMAL: 1, TEXCOORD_0: 2 },
            indices: 3,
            material: 0,
          },
        ],
      },
    ],
    buffers: [{ uri: binary, byteLength: data.length }],
    bufferViews,
    accessors,
  };
  const webp = (source) => ({ extensions: { EXT_texture_webp: { source } } });
  const gltf = {
    ...base,
    images: [
      { uri: color, mimeType: 'image/avif' },
      { uri: preview, mimeType: 'image/webp' },
      { uri: normal, mimeType: 'image/webp' },
    ],
    textures: [
      {
        extensions: {
          EXT_texture_avif: { source: 0 },
          EXT_texture_webp: { source: 1 },
        },
      },
      webp(1),
      webp(2),
    ],
    extensionsUsed: ['EXT_texture_avif', 'EXT_texture_webp', 'MSFT_lod'],
    extensionsRequired: ['EXT_texture_webp'],
    materials: [
      {
        pbrMetallicRoughness: { ...pbr, baseColorTexture: { index: 0 } },
        normalTexture: { index: 2 },
        extensions: { MSFT_lod: { ids: [1] } },
        extras: { MSFT_screencoverage: [0, 0] },
      },
      { pbrMetallicRoughness: { ...pbr, baseColorTexture: { index: 1 } } },
    ],
  };
  await writeJson(file, gltf);
  for (const resource of [binary, color, normal, preview])
    await publish(collection, posix.join(posix.dirname(piece.src), resource));
  const blank = collection.catalog.pieces.find(
    (p) => p.name === kind + ' (blank)',
  );
  if (blank) {
    const target = join(collection.dir, blank.src);
    await mkdir(dirname(target), { recursive: true });
    await writeJson(target, {
      ...base,
      buffers: [
        {
          uri: relative(dirname(target), join(dir, binary)).split(sep).join('/'),
          byteLength: data.length,
        },
      ],
      materials: [{ pbrMetallicRoughness: pbr }],
    });
  }
  for (const entry of [piece, ...(blank ? [blank] : [])]) {
    entry.faces = mesh.faces;
    entry.rotation = mesh.faces[0].rotation;
    const src = posix.join(collection.key, entry.src);
    const shared = combined.pieces.find((p) => p.src === src);
    Object.assign(shared, { rotation: entry.rotation, faces: entry.faces });
    for (const token of release.game.children.filter((t) => t.src === src))
      Object.assign(token, { rotation: entry.rotation, size });
    await publish(collection, entry.src);
  }
  console.log(kind);
}
let browser, server;
try {
  server = await createServer({
    root,
    logLevel: 'error',
    server: { host: '127.0.0.1', port: 0, watch: null },
    plugins: [
      {
        name: 'export-entry',
        configureServer(s) {
          s.middlewares.use('/__dice_export', (_req, res) => {
            res.setHeader('Content-Type', 'text/html');
            res.end('<!doctype html><title>Dice exporter</title>');
          });
        },
      },
    ],
  });
  await server.listen();
  browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(server.resolvedUrls.local[0] + '__dice_export');
  const kinds = await page.evaluate(async () => {
    await (await import('/src/generators/dice/export-die.ts')).loadExportFont();
    return (await import('/src/generators/dice/shapes.ts')).kinds;
  });
  for (const kind of kinds) await generate(page, kind);
  for (const c of collections)
    await writeJson(join(c.dir, 'catalog.json'), c.catalog);
  await writeJson(join(showcase, 'catalog.json'), combined);
  await record('catalog.json');
  release.files = [...records.values()].sort((a, b) =>
    a.path < b.path ? -1 : a.path > b.path ? 1 : 0,
  );
  await writeJson(join(showcase, 'release.json'), release);
  // Leave the published catalog intact if rendering or conversion fails.
  await cp(output, root, { recursive: true });
} finally {
  await browser?.close();
  await server?.close();
  await rm(scratch, { recursive: true, force: true });
}
