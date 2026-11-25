import {
  BufferGeometry,
  Vector2,
  Float32BufferAttribute,
  MeshStandardMaterial,
  CanvasTexture,
  SRGBColorSpace,
} from 'three';
import { tabletopMotion } from './tabletop-motion';
import { generateDie } from './generate-die';
import { generateShape, type Kind } from './shapes';
import { markingNormals } from './marking-normals';
function rasterize(ctx: CanvasRenderingContext2D, value: string, size: number) {
  const font = '700 ' + size + 'px Comfortaa';
  ctx.font = font;
  const m = ctx.measureText(value);
  const width =
    Math.ceil(m.actualBoundingBoxLeft + m.actualBoundingBoxRight) + 10;
  const height =
    Math.ceil(m.actualBoundingBoxAscent + m.actualBoundingBoxDescent) + 10;
  ctx.canvas.width = width;
  ctx.canvas.height = height;
  ctx.font = font;
  ctx.fillStyle = '#222';
  ctx.fillText(
    value,
    (width + m.actualBoundingBoxLeft - m.actualBoundingBoxRight) / 2,
    (height + m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2,
  );
  return ctx.getImageData(0, 0, width, height);
}

// Sample the visible glyph outline in ems, relative to its ink center.
function glyphOutline(ctx: CanvasRenderingContext2D, value: string) {
  const em = 100;
  const { width, height, data } = rasterize(ctx, value, em);
  const points: Vector2[] = [];
  const neighbors = [4, -4, width * 4, -width * 4];
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const alpha = (y * width + x) * 4 + 3;
      if (data[alpha] > 16 && neighbors.some((d) => data[alpha + d] <= 16))
        points.push(
          new Vector2((x + 0.5 - width / 2) / em, (y + 0.5 - height / 2) / em),
        );
    }
  }
  return points;
}

export function createDieResources(kind: Kind) {
  const shape = generateShape(kind);
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  const stamp = document
    .createElement('canvas')
    .getContext('2d', { willReadFrequently: true })!;
  const outlines = new Map<string, Vector2[]>();
  if (kind !== 'Classic die') {
    for (const face of shape.faces) {
      outlines.set(face.name, glyphOutline(stamp, face.name));
    }
  }
  const { faces, pos, norm, uv, atlas } = generateDie(kind, outlines, shape);
  const { width, height, cols, side, markings } = atlas;
  canvas.width = width;
  canvas.height = height;
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#222';
  for (const mark of markings) {
    if (mark.type === 'text') {
      // Canvas metrics can differ from the hinted pixels at the final font size.
      // Center the rendered ink before rotating the label into its face.
      const { width, height, data } = rasterize(stamp, mark.value, mark.size);
      let left = width,
        right = 0,
        top = height,
        bottom = 0;
      for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
          if (data[(y * width + x) * 4 + 3] < 64) continue;
          left = Math.min(left, x);
          right = Math.max(right, x);
          top = Math.min(top, y);
          bottom = Math.max(bottom, y);
        }
      }
      ctx.save();
      ctx.translate(mark.x, mark.y);
      ctx.rotate(mark.angle);
      ctx.drawImage(
        stamp.canvas,
        -(left + right + 1) / 2,
        -(top + bottom + 1) / 2,
      );
      ctx.restore();
    } else {
      ctx.beginPath();
      ctx.arc(mark.x, mark.y, mark.radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute('position', new Float32BufferAttribute(pos, 3));
  geometry.setAttribute('normal', new Float32BufferAttribute(norm, 3));
  geometry.setAttribute('uv', new Float32BufferAttribute(uv, 2));
  const texture = new CanvasTexture(canvas);
  texture.flipY = false;
  texture.colorSpace = SRGBColorSpace;
  texture.anisotropy = 4;
  const normalMap = markingNormals(
    canvas,
    side,
    cols,
    faces.map((f) => f.name),
    kind === 'Classic die',
  );
  const marked = new MeshStandardMaterial({
    map: texture,
    normalMap,
    roughness: 0.48,
  });
  const blank = new MeshStandardMaterial({ color: 0xffffff, roughness: 0.48 });
  const motion = tabletopMotion(
    geometry,
    faces.map((f) => f.pose),
  );
  return {
    kind,
    geometry,
    marked,
    blank,
    faces,
    motion,
    dispose() {
      geometry.dispose();
      texture.dispose();
      normalMap.dispose();
      marked.dispose();
      blank.dispose();
    },
  };
}
export type Die = ReturnType<typeof createDieResources>;
