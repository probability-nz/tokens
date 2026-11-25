import { Vector2, Vector3 } from 'three';
import { pipRadius, pipSpacing, pipLayout } from './markings';
import { generateShape, type Kind, type Patch } from './shapes';

export type Marking =
  | { type: 'pip'; x: number; y: number; radius: number }
  | {
      type: 'text';
      value: string;
      x: number;
      y: number;
      size: number;
      angle: number;
    };
type Chart = {
  center: Vector2;
  pixels: number;
  project: (point: Vector3) => Vector2;
};
// Only unpaired patch edges bound the printable surface. This also captures
// the notches between a sliced sphere's flats, which its convex hull misses.
function printBorders(patches: Patch[], count: number) {
  const borders = Array.from(
    { length: count },
    () => new Map<string, [Vector3, Vector3]>(),
  );
  const key = (p: Vector3) =>
    p
      .toArray()
      .map((v) => Math.round(v * 1e6))
      .join(',');
  for (const { face, samples } of patches) {
    if (face === undefined) continue;
    const edges = borders[face];
    for (let i = 0; i < samples.length; i++) {
      const a = samples[i].point,
        b = samples[(i + 1) % samples.length].point;
      const ka = key(a),
        kb = key(b);
      if (ka === kb) continue;
      const id = ka < kb ? ka + '|' + kb : kb + '|' + ka;
      if (!edges.delete(id)) edges.set(id, [a, b]);
    }
  }
  return borders;
}

// The first intersection between an expanding glyph and a face boundary.
function glyphLimit(
  outline: readonly Vector2[],
  edges: readonly Vector2[][],
  anchor: Vector2,
  angle: number,
) {
  let limit = Infinity;
  const cos = Math.cos(angle),
    sin = Math.sin(angle);
  for (const [a, b] of edges) {
    const ax = a.x - anchor.x,
      ay = a.y - anchor.y;
    const dx = b.x - a.x,
      dy = b.y - a.y;
    const numerator = ax * dy - ay * dx;
    for (const point of outline) {
      const x = cos * point.x - sin * point.y,
        y = sin * point.x + cos * point.y;
      const det = x * dy - y * dx;
      if (!det) continue;
      const along = (ax * y - ay * x) / det;
      const scale = numerator / det;
      if (along >= 0 && along <= 1 && scale > 0) limit = Math.min(limit, scale);
    }
  }
  return limit;
}
// Both variants share one generated geometry, including UVs and the ordered face poses.
export function generateDie(
  kind: Kind,
  outlines: ReadonlyMap<string, readonly Vector2[]>,
  { faces, patches } = generateShape(kind),
) {
  const cols = Math.ceil(Math.sqrt(faces.length)),
    rows = Math.ceil(faces.length / cols);
  const small = 8,
    extra = patches.filter((p) => p.face === undefined).length;
  let side = Math.min(288, Math.floor(1920 / cols));
  while (
    rows * side + Math.ceil(extra / Math.floor((cols * side) / small)) * small >
    2048
  )
    side--;
  const width = cols * side;
  const height =
    rows * side + Math.ceil(extra / Math.floor(width / small)) * small;
  const markings: Marking[] = [];
  const borders = printBorders(patches, faces.length);
  const charts: Chart[] = faces.map((f, i) => {
    const project = (p: Vector3) => new Vector2(p.dot(f.right), p.dot(f.down));
    const outline = f.rim.map(project);
    const span = Math.max(
      ...outline.flatMap((p) => [Math.abs(p.x), Math.abs(p.y)]),
    );
    const pixels = (side / 2 - 6) / span;
    return {
      project,
      pixels,
      center: new Vector2(
        ((i % cols) + 0.5) * side,
        (Math.floor(i / cols) + 0.5) * side,
      ),
    };
  });
  let typeSize = Infinity;
  for (const [i, f] of faces.entries()) {
    const { pixels, center, project } = charts[i];
    const edges = Array.from(borders[i].values(), ([a, b]) => [
      project(a),
      project(b),
    ]);
    function addText(value: string, anchor: Vector2, angle = 0) {
      typeSize = Math.min(
        typeSize,
        glyphLimit(outlines.get(value)!, edges, anchor, angle),
      );
      const pixel = anchor.clone().multiplyScalar(pixels).add(center);
      markings.push({
        type: 'text',
        value,
        x: pixel.x,
        y: pixel.y,
        size: pixels,
        angle,
      });
    }
    if (kind === 'D4') {
      // A tetrahedron rests on a face. Its upper vertex reads the same on all three adjacent faces.
      for (const p of f.rim) {
        const top = faces.reduce((best, g) =>
          g.axis.dot(p) < best.axis.dot(p) ? g : best,
        );
        const vertex = project(p);
        addText(
          top.name,
          vertex.clone().multiplyScalar(0.57),
          Math.atan2(vertex.x, -vertex.y),
        );
      }
    } else if (kind === 'Classic die') {
      for (const [x, y] of pipLayout(Number(f.name))) {
        markings.push({
          type: 'pip',
          x: center.x + x * side * pipSpacing,
          y: center.y + y * side * pipSpacing,
          radius: side * pipRadius,
        });
      }
    } else {
      // The face pose maps these axes onto the same table axes at every stop.
      // Their origin is above the die pivot even for asymmetric faces.
      addText(f.name, new Vector2());
    }
  }
  // One physical font size per die, with clearance for antialiasing and engraving.
  // Keep the D10 at its established size on its broad kite-shaped faces.
  const labelFill: Partial<Record<Kind, number>> = {
    D4: 0.92,
    D6: 0.92,
    D8: 0.92,
    D10: 0.78,
  };
  const fill = labelFill[kind] ?? 0.97;
  for (const mark of markings) {
    if (mark.type === 'text') mark.size *= typeSize * fill;
  }
  const pos: number[] = [],
    norm: number[] = [],
    uv: number[] = [];
  let smallIndex = 0;
  for (const patch of patches) {
    const samples = patch.samples;
    let chart: Vector2[];
    if (patch.face !== undefined) {
      const { project, pixels, center } = charts[patch.face];
      chart = samples.map((s) =>
        project(s.point).multiplyScalar(pixels).add(center),
      );
    } else {
      const t = samples[1].point.clone().sub(samples[0].point).normalize();
      const plane = t
        .clone()
        .cross(samples[2].point.clone().sub(samples[0].point))
        .normalize();
      const b = t.clone().cross(plane);
      const xy = samples.map(
        (s) => new Vector2(s.point.dot(t), s.point.dot(b)),
      );
      const min = new Vector2(
        Math.min(...xy.map((p) => p.x)),
        Math.min(...xy.map((p) => p.y)),
      );
      const span = Math.max(
        ...xy.flatMap((p) => [p.x - min.x, p.y - min.y]),
        1e-10,
      );
      const perRow = Math.floor(width / small);
      const base = new Vector2(
        small * (smallIndex % perRow) + 1,
        rows * side + small * Math.floor(smallIndex / perRow) + 1,
      );
      chart = xy.map((p) =>
        p
          .sub(min)
          .multiplyScalar((small - 2) / span)
          .add(base),
      );
      smallIndex++;
    }
    for (let j = 1; j < samples.length - 1; j++) {
      const a = samples[0],
        b = samples[j],
        c = samples[j + 1];
      const cross = b.point
        .clone()
        .sub(a.point)
        .cross(c.point.clone().sub(a.point));
      if (cross.lengthSq() < 1e-18) continue;
      const order =
        cross.dot(a.normal.clone().add(b.normal).add(c.normal)) > 0
          ? [0, j, j + 1]
          : [0, j + 1, j];
      for (const k of order) {
        pos.push(...samples[k].point.toArray());
        norm.push(...samples[k].normal.toArray());
        uv.push(chart[k].x / width, chart[k].y / height);
      }
    }
  }
  return {
    kind,
    faces,
    pos,
    norm,
    uv,
    atlas: { width, height, side, cols, markings },
  };
}
