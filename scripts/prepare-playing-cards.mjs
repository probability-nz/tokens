import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const run = promisify(execFile);
const root = fileURLToPath(
  new URL('../src/assets/playing-cards/austin/', import.meta.url),
);
const sizeMm = [63.5, 88.9, 0.3];
const pixelsPerMm = 12;
const [width, height] = sizeMm.map((mm) => Math.round(mm * pixelsPerMm));
const suits = ['clubs', 'hearts', 'spades', 'diamonds'];
const ranks = [
  'ace',
  '2',
  '3',
  '4',
  '5',
  '6',
  '7',
  '8',
  '9',
  '10',
  'jack',
  'queen',
  'king',
];
const ids = [
  ...suits.flatMap((suit) => ranks.map((rank) => rank + '-' + suit)),
  'black-joker',
  'red-joker',
  'blank',
];
const template = JSON.parse(
  await readFile(join(root, 'source/card-template.json'), 'utf8'),
);
const work = await mkdtemp(join(tmpdir(), 'austin-cards-'));
try {
  const png = join(work, 'face.png');
  for (const id of [...ids, 'blue-back']) {
    if (id === 'blank') {
      await run('magick', ['-size', width + 'x' + height, 'xc:white', png]);
    } else {
      await run('inkscape', [
        join(root, 'source', id + '.svg'),
        '--export-width=' + width,
        '--export-height=' + height,
        '--export-background=#ffffff',
        '--export-background-opacity=1',
        '--export-filename=' + png,
      ]);
    }
    await run('magick', [
      png,
      '-strip',
      '-define',
      'heic:chroma=444',
      '-quality',
      '85',
      join(root, id + '.avif'),
    ]);
    if (id !== 'blue-back') {
      const model = structuredClone(template);
      model.images[0].uri = id + '.avif';
      await writeFile(join(root, id + '.gltf'), JSON.stringify(model) + '\n');
    }
  }
  const manifest = {
    sizeMm,
    pixelsPerMm,
    cards: Object.fromEntries(ids.map((id) => [id, id + '.gltf'])),
  };
  await writeFile(
    join(root, 'deck.json'),
    JSON.stringify(manifest, null, 2) + '\n',
  );
} finally {
  await rm(work, { recursive: true, force: true });
}
