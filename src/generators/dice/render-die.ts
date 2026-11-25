import {
  BufferGeometry,
  Float32BufferAttribute,
  MeshStandardMaterial,
  CanvasTexture,
  SRGBColorSpace,
} from 'three';
import { tabletopMotion } from './tabletop-motion';
import { generateDie, faceLabel } from './generate-die';
import { generateShape, type Kind } from './shapes';
import { markingNormals } from './marking-normals';
function print(
  ctx: CanvasRenderingContext2D,
  value: string,
  x: number,
  y: number,
  size: number,
  angle = 0,
) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.font = '700 ' + size + 'px Comfortaa';
  const m = ctx.measureText(value);
  ctx.fillText(
    value,
    (m.actualBoundingBoxLeft - m.actualBoundingBoxRight) / 2,
    (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2,
  );
  ctx.restore();
}

export function createDieResources(kind: Kind) {
  const shape = generateShape(kind);
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  ctx.font = '700 100px Comfortaa';
  const metrics = shape.faces.map((f) =>
    ctx.measureText(faceLabel(kind, f.name)),
  );
  const ink = {
    halfWidth:
      Math.max(
        ...metrics.map(
          (m) => m.actualBoundingBoxLeft + m.actualBoundingBoxRight,
        ),
      ) / 200,
    halfHeight:
      Math.max(
        ...metrics.map(
          (m) => m.actualBoundingBoxAscent + m.actualBoundingBoxDescent,
        ),
      ) / 200,
  };
  const { faces, pos, norm, uv, atlas } = generateDie(kind, ink, shape);
  const { width, height, cols, side, markings } = atlas;
  canvas.width = width;
  canvas.height = height;
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#222';
  for (const mark of markings) {
    if (mark.type === 'text')
      print(ctx, mark.value, mark.x, mark.y, mark.size, mark.angle);
    else {
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
