import { execFile } from 'node:child_process';
import { copyFile, readFile, writeFile } from 'node:fs/promises';
import { basename, dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const assets = join(root, 'src', 'assets');
const catalog = JSON.parse(
  await readFile(join(assets, 'catalog.json'), 'utf8'),
);
const run = promisify(execFile);
const TEXTURE_BOUNDS = '2048x2048>';
const PREVIEW_BOUNDS = '128x128>';

const assetError = (name, message) => new Error(`${name}: ${message}`);
const prettyJson = (value) => `${JSON.stringify(value, null, 2)}\n`;
const fileName = (resource, name, label) => {
  const uri = resource?.uri;
  if (typeof uri !== 'string' || uri === '' || basename(uri) !== uri) {
    throw assetError(name, `${label} must be a file beside the source glTF`);
  }
  return uri;
};
const textureSource = (gltf, textureInfo, name, label) => {
  if (!Number.isSafeInteger(textureInfo?.index)) {
    throw assetError(name, `${label} must reference a texture`);
  }
  const texture = gltf.textures?.[textureInfo.index];
  if (!Number.isSafeInteger(texture?.source)) {
    throw assetError(name, `${label} must use a core glTF image source`);
  }
  return {
    sampler: texture.sampler,
    uri: fileName(gltf.images?.[texture.source], name, label),
  };
};
const convert = (input, output, size, args) =>
  run('magick', [input, '-resize', size, '-strip', ...args, output]);
const webpTexture = (sampler, source) => ({
  ...(sampler === undefined ? {} : { sampler }),
  extensions: { EXT_texture_webp: { source } },
});

if (!Array.isArray(catalog.pieces)) {
  throw new Error('catalog.json must contain a pieces array');
}
for (const piece of catalog.pieces) {
  const modelPath = join(assets, piece.src);
  const directory = dirname(modelPath);
  const sourceDirectory = join(directory, 'source');
  const modelFile = basename(modelPath);
  const name = basename(modelFile, extname(modelFile));
  const gltf = JSON.parse(
    await readFile(join(sourceDirectory, modelFile), 'utf8'),
  );

  for (const [index, buffer] of (gltf.buffers ?? []).entries()) {
    const uri = fileName(buffer, name, `buffers[${index}]`);
    await copyFile(join(sourceDirectory, uri), join(directory, uri));
  }

  const materials = gltf.materials ?? [];
  if (!Array.isArray(materials) || materials.length > 1) {
    throw assetError(name, 'source glTF must contain at most one material');
  }
  const material = materials[0];
  const baseColorInfo = material?.pbrMetallicRoughness?.baseColorTexture;
  if (baseColorInfo === undefined) {
    for (const [index, image] of (gltf.images ?? []).entries()) {
      const uri = fileName(image, name, `images[${index}]`);
      await copyFile(join(sourceDirectory, uri), join(directory, uri));
    }
    await writeFile(modelPath, prettyJson(gltf));
    continue;
  }
  if (
    material.emissiveTexture !== undefined ||
    material.occlusionTexture !== undefined ||
    material.pbrMetallicRoughness.metallicRoughnessTexture !== undefined ||
    material.extensions !== undefined
  ) {
    throw assetError(name, 'only base-color and normal textures are supported');
  }

  const diffuse = textureSource(gltf, baseColorInfo, name, 'base color');
  const normal =
    material.normalTexture === undefined
      ? undefined
      : textureSource(gltf, material.normalTexture, name, 'normal');
  const diffuseName = `${name}_diffuse.avif`;
  const normalName = `${name}_normal.webp`;
  const previewName = `${name}_preview.webp`;
  const diffuseSource = join(sourceDirectory, diffuse.uri);

  const conversions = [
    convert(diffuseSource, join(directory, diffuseName), TEXTURE_BOUNDS, [
      '-define', 'heic:speed=6', '-quality', '85',
    ]),
    convert(diffuseSource, join(directory, previewName), PREVIEW_BOUNDS, [
      '-quality', '55',
    ]),
  ];
  if (normal !== undefined) {
    conversions.push(
      convert(
        join(sourceDirectory, normal.uri),
        join(directory, normalName),
        TEXTURE_BOUNDS,
        [
          '-depth', '8',
          '-define', 'webp:lossless=true',
          '-define', 'webp:method=6',
        ],
      ),
    );
  }
  await Promise.all(conversions);

  const preferred = structuredClone(material);
  const preview = structuredClone(material);
  preferred.name = `${name} preferred`;
  preferred.extensions = {
    ...preferred.extensions,
    MSFT_lod: { ids: [1] },
  };
  preferred.extras = {
    ...preferred.extras,
    MSFT_screencoverage: [0, 0],
  };
  const images = [];
  const textures = [];
  if (normal !== undefined) {
    preferred.normalTexture = {
      ...preferred.normalTexture,
      index: textures.length,
    };
    textures.push(webpTexture(normal.sampler, images.length));
    images.push({
      mimeType: 'image/webp', name: `${name} normal`, uri: normalName,
    });
  }
  const preferredImage = images.length;
  const previewImage = preferredImage + 1;
  preferred.pbrMetallicRoughness.baseColorTexture = {
    ...baseColorInfo,
    index: textures.length,
  };
  textures.push({
    ...(diffuse.sampler === undefined ? {} : { sampler: diffuse.sampler }),
    extensions: {
      EXT_texture_avif: { source: preferredImage },
      EXT_texture_webp: { source: previewImage },
    },
  });
  preview.name = `${name} preview`;
  delete preview.normalTexture;
  preview.pbrMetallicRoughness.baseColorTexture = {
    ...baseColorInfo,
    index: textures.length,
  };
  textures.push(
    webpTexture(diffuse.sampler, previewImage),
  );
  images.push(
    { mimeType: 'image/avif', name: `${name} preferred`, uri: diffuseName },
    { mimeType: 'image/webp', name: `${name} preview`, uri: previewName },
  );

  gltf.extensionsUsed = [
    ...new Set([
      ...(gltf.extensionsUsed ?? []),
      'EXT_texture_avif',
      'EXT_texture_webp',
      'MSFT_lod',
    ]),
  ];
  gltf.extensionsRequired = [
    ...new Set([...(gltf.extensionsRequired ?? []), 'EXT_texture_webp']),
  ];
  gltf.materials = [preferred, preview];
  gltf.textures = textures;
  gltf.images = images;
  await writeFile(modelPath, prettyJson(gltf));
}
