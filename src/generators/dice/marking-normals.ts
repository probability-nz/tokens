import { CanvasTexture } from 'three';

import {
  pipRadius,
  pipSpacing,
  pipLayout,
  pipBowlPixels,
  engravedNormals,
} from './markings';
// Recess a hemisphere slightly wider than the ink, as in the handmade pip map.
function pipBowl(radius: number) {
  const bowl = document.createElement('canvas');
  const { size, data } = pipBowlPixels(radius);
  bowl.width = bowl.height = size;
  const ctx = bowl.getContext('2d')!;
  const image = new ImageData(data, size, size);
  ctx.putImageData(image, 0, 0);
  return bowl;
}

export function markingNormals(
  color: HTMLCanvasElement,
  side: number,
  cols: number,
  names: string[],
  pipped: boolean,
) {
  // Keep dense normal atlases within a two-megapixel working budget.
  let scale = 1;
  while (color.width * color.height * scale * scale > 2_000_000) scale /= 2;
  const atlas = document.createElement('canvas');
  atlas.width = Math.ceil(color.width * scale);
  atlas.height = Math.ceil(color.height * scale);
  const output = atlas.getContext('2d')!;
  output.scale(atlas.width / color.width, atlas.height / color.height);
  output.fillStyle = '#8080ff';
  output.fillRect(0, 0, color.width, color.height);

  const tile = document.createElement('canvas');
  const size = Math.ceil(side * scale);
  tile.width = tile.height = size;
  const ctx = tile.getContext('2d', { willReadFrequently: true })!;
  const bowl = pipped ? pipBowl(side * pipRadius * 1.08) : null;
  const bevel = Math.max(0.9, size * 0.009);
  for (const [index, name] of names.entries()) {
    const x = (index % cols) * side,
      y = Math.floor(index / cols) * side;
    if (bowl) {
      for (const [dx, dy] of pipLayout(Number(name))) {
        output.drawImage(
          bowl,
          x + side * (0.5 + dx * pipSpacing) - bowl.width / 2,
          y + side * (0.5 + dy * pipSpacing) - bowl.height / 2,
        );
      }
      continue;
    }
    // Dark ink is the floor of each engraved stroke. Its softened boundary
    // gives an inward slope in the atlas's positive-down UV coordinates.
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, size, size);
    ctx.filter = 'blur(' + bevel + 'px)';
    ctx.drawImage(color, x, y, side, side, 0, 0, size, size);
    ctx.filter = 'none';
    const height = ctx.getImageData(0, 0, size, size).data;
    const normal = new ImageData(
      engravedNormals(height, size, bevel),
      size,
      size,
    );
    ctx.putImageData(normal, 0, 0);
    output.drawImage(tile, x, y, side, side);
  }
  const texture = new CanvasTexture(atlas);
  texture.flipY = false;
  texture.anisotropy = 4;
  return texture;
}
