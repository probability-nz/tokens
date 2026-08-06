import { copyFile, mkdir, readFile, rm } from 'node:fs/promises';
import { dirname, isAbsolute, join, normalize, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const assets = join(root, 'src', 'assets');
const output = join(root, 'dist');
const catalogPath = join(assets, 'catalog.json');
const catalog = JSON.parse(await readFile(catalogPath, 'utf8'));

const record = (value) =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const onlyKeys = (value, keys) =>
  Object.keys(value).every((key) => keys.includes(key));

const tuple = (value, label, positive = false) => {
  if (
    !Array.isArray(value) ||
    value.length !== 3 ||
    value.some((part) => !Number.isFinite(part) || (positive && part <= 0))
  ) {
    throw new Error(
      `${label} must be a finite three-number tuple${positive ? ' of positive values' : ''}`,
    );
  }
};
const relativeFile = (value, label, extension, base = assets) => {
  if (
    typeof value !== 'string' ||
    value === '' ||
    /[?#\\]/u.test(value) ||
    /^[a-z]+:/iu.test(value) ||
    isAbsolute(value) ||
    (extension !== undefined && !value.endsWith(extension))
  ) {
    throw new Error(
      `${label} must be a relative${extension === undefined ? '' : ` ${extension}`} path`,
    );
  }
  const resolved = normalize(join(base, value));
  const location = relative(assets, resolved);
  if (location === '..' || location.startsWith(`..${sep}`))
    throw new Error(`${label} escapes the catalog root`);
  return resolved;
};

if (
  !record(catalog) ||
  !onlyKeys(catalog, ['attribution', 'license', 'pieces', 'version']) ||
  catalog.version !== 1 ||
  typeof catalog.attribution !== 'string' ||
  catalog.attribution.trim() === '' ||
  typeof catalog.license !== 'string' ||
  catalog.license.trim() === '' ||
  !Array.isArray(catalog.pieces)
) {
  throw new Error('catalog.json must contain a version 1 pieces array');
}
const names = new Set();
const sources = new Set();
const files = new Set([catalogPath]);
for (const [index, piece] of catalog.pieces.entries()) {
  if (
    !record(piece) ||
    !onlyKeys(piece, ['faces', 'name', 'rotation', 'scale', 'src']) ||
    typeof piece.name !== 'string' ||
    piece.name.trim() === '' ||
    names.has(piece.name)
  ) {
    throw new Error(`pieces[${index}].name must be unique and non-empty`);
  }
  if (!Array.isArray(piece.faces))
    throw new Error(`pieces[${index}].faces must be an array`);
  const gltfPath = relativeFile(piece.src, `pieces[${index}].src`, '.gltf');
  if (sources.has(gltfPath))
    throw new Error(`pieces[${index}].src must be unique`);
  tuple(piece.scale, `pieces[${index}].scale`, true);
  tuple(piece.rotation, `pieces[${index}].rotation`);
  const faceNames = new Set();
  for (const [faceIndex, face] of piece.faces.entries()) {
    if (
      !record(face) ||
      !onlyKeys(face, ['name', 'rotation']) ||
      typeof face.name !== 'string' ||
      face.name.trim() === '' ||
      faceNames.has(face.name)
    ) {
      throw new Error(
        `pieces[${index}].faces[${faceIndex}].name must be unique and non-empty`,
      );
    }
    tuple(
      face.rotation,
      `pieces[${index}].faces[${faceIndex}].rotation`,
    );
    faceNames.add(face.name);
  }
  names.add(piece.name);
  sources.add(gltfPath);
  files.add(gltfPath);

  const gltf = JSON.parse(await readFile(gltfPath, 'utf8'));
  for (const [resourceIndex, resource] of [
    ...(gltf.buffers ?? []).map((buffer, resourceIndex) => [
      resourceIndex,
      buffer,
    ]),
    ...(gltf.images ?? []).map((image, resourceIndex) => [
      resourceIndex,
      image,
    ]),
  ]) {
    if (!record(resource))
      throw new Error(`${piece.src} resource ${resourceIndex} is invalid`);
    if (resource.uri === undefined) continue;
    if (typeof resource.uri !== 'string')
      throw new Error(`${piece.src} resource ${resourceIndex} URI is invalid`);
    if (resource.uri.startsWith('data:')) continue;
    const resourcePath = relativeFile(
      resource.uri,
      `${piece.src} resource ${resourceIndex}`,
      undefined,
      dirname(gltfPath),
    );
    files.add(resourcePath);
  }
}

await rm(output, { force: true, recursive: true });
for (const source of files) {
  const destination = join(output, relative(assets, source));
  await mkdir(dirname(destination), { recursive: true });
  await copyFile(source, destination);
}
