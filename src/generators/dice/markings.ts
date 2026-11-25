export const pipRadius = 0.133;
export const pipSpacing = 0.315;
export function pipLayout(n: number) {
  const dots: number[][] = [];
  if (n % 2) dots.push([0, 0]);
  if (n >= 2) dots.push([-1, -1], [1, 1]);
  if (n >= 4) dots.push([1, -1], [-1, 1]);
  if (n === 6) dots.push([-1, 0], [1, 0]);
  return dots;
}

export function pipBowlPixels(radius: number) {
  const size = Math.ceil(2 * radius);
  const data = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = (x + 0.5 - size / 2) / radius;
      const v = (y + 0.5 - size / 2) / radius;
      const z2 = 1 - u * u - v * v;
      if (z2 <= 0) continue;
      const i = (y * size + x) * 4;
      data[i] = 127.5 * (1 - u);
      data[i + 1] = 127.5 * (1 - v);
      data[i + 2] = 127.5 * (1 + Math.sqrt(z2));
      data[i + 3] = 255;
    }
  }
  return { size, data };
}
export function engravedNormals(
  height: Uint8ClampedArray,
  size: number,
  bevel: number,
) {
  const data = new Uint8ClampedArray(size * size * 4);
  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      const i = (row * size + col) * 4;
      const depth = (bevel * 1.5) / 255;
      const nx =
        col && col + 1 < size ? (height[i - 4] - height[i + 4]) * depth : 0;
      const ny =
        row && row + 1 < size
          ? (height[i - size * 4] - height[i + size * 4]) * depth
          : 0;
      const k = 127.5 / Math.sqrt(1 + nx * nx + ny * ny);
      data[i] = 127.5 + k * nx;
      data[i + 1] = 127.5 + k * ny;
      data[i + 2] = 127.5 + k;
      data[i + 3] = 255;
    }
  }
  return data;
}
