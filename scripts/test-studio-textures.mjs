import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ImageLoader } from 'three';
import { preferredModelLoader } from '../src/preview/shared-textures.ts';

test('independent glTFs share decoded images and retain per-model samplers and WebP fallback', async (t) => {
  // Exercise the real glTF texture plugins without allocating a WebGL context.
  const previous = globalThis.self;
  globalThis.self = globalThis;
  t.after(() => {
    if (previous === undefined) delete globalThis.self;
    else globalThis.self = previous;
  });
  const loads = [];
  t.mock.method(ImageLoader.prototype, 'loadAsync', async (url) => {
    loads.push(url);
    if (url.endsWith('unsupported.avif')) throw Error('Unsupported format');
    return { width: 1, height: 1 };
  });
  async function texture(image, wrapS) {
    const model = {
      asset: { version: '2.0' },
      images: [{ uri: image }, { uri: 'preview.webp' }],
      textures: [{ sampler: 0, extensions: { EXT_texture_avif: { source: 0 }, EXT_texture_webp: { source: 1 } } }],
      samplers: [{ wrapS }],
      extensionsUsed: ['EXT_texture_avif', 'EXT_texture_webp'],
    };
    const { parser } = await preferredModelLoader.parseAsync(JSON.stringify(model), 'https://studio.invalid/');
    return parser.getDependency('texture', 0);
  }
  const [first, second] = await Promise.all([texture('shared.avif', 10497), texture('shared.avif', 33071)]);
  assert.deepEqual(loads, ['https://studio.invalid/shared.avif']);
  assert.equal(first.source, second.source);
  assert.notEqual(first.wrapS, second.wrapS);
  t.mock.method(console, 'error', () => {});
  const fallback = await texture('unsupported.avif', 10497);
  assert.equal(fallback.userData.mimeType, 'image/webp');
  assert.equal(loads.at(-1), 'https://studio.invalid/preview.webp');
});
