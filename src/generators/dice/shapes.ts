import { Quaternion, Vector3 } from 'three';
import { orientFaceWalk } from './face-walk';

export const kinds = [
  'D3',
  'D4',
  'D6',
  'Classic die',
  'D8',
  'D10',
  'D12',
  'D16',
  'D20',
  'D24',
  'D48',
  'D100',
  'D120',
] as const;
export type Kind = (typeof kinds)[number];
export type Face = {
  name: string;
  pose: Quaternion;
  axis: Vector3;
  right: Vector3;
  down: Vector3;
  rim: Vector3[];
};
export type Sample = { point: Vector3; normal: Vector3 };
export type Patch = { samples: Sample[]; face?: number };
export type Shape = { faces: Face[]; patches: Patch[] };
const vec = (x: number, y: number, z: number) => new Vector3(x, y, z);
const Y = vec(0, 1, 0);
const tau = Math.PI * 2;
const phi = (1 + Math.sqrt(5)) / 2;
// Plane-to-center distances in mm. D3 uses the radius of the uncut sphere.
const radius: Record<Kind, number> = {
  D3: 8,
  D4: 5.63,
  D6: 8,
  'Classic die': 8,
  D8: 8.93,
  D10: 8,
  D12: 11.19,
  D16: 10.06,
  D20: 12.7,
  D24: 10.22,
  D48: 13.21,
  D100: 14.65,
  D120: 14.17,
};
const sum = (p: Vector3[]) => p.reduce((a, v) => a.add(v), new Vector3());
const unitSum = (p: Vector3[]) => sum(p).normalize();
const key = (p: Vector3) =>
  p
    .toArray()
    .map((x) => Math.round(x * 1e6))
    .join('/');
function ring(count: number, latitude: number, phase = 0) {
  const h = Math.cos(latitude);
  return Array.from({ length: count }, (_, i) => {
    const angle = phase + (tau * i) / count;
    return vec(h * Math.cos(angle), Math.sin(latitude), h * Math.sin(angle));
  });
}
function pairedRings(
  count: number,
  latitude: number,
  topPhase = 0,
  bottomPhase = topPhase,
) {
  return [
    ...ring(count, latitude, topPhase),
    ...ring(count, -latitude, bottomPhase),
  ];
}
const deg = (angle: number) => (angle * Math.PI) / 180;
const signedAxes = () =>
  [vec(1, 0, 0), vec(0, 1, 0), vec(0, 0, 1)].flatMap((v) => [
    v,
    v.clone().negate(),
  ]);
function icosahedron(mirror: boolean) {
  const points: Vector3[] = [];
  for (const s of [-1, 1])
    for (const t of [-1, 1]) {
      const a = mirror ? phi * s : s,
        b = mirror ? t : phi * t;
      points.push(
        vec(0, a, b).normalize(),
        vec(b, 0, a).normalize(),
        vec(a, b, 0).normalize(),
      );
    }
  return points;
}
function symmetryPlanes(count: number) {
  const vertices = count === 120 ? icosahedron(false) : signedAxes();
  const edge = Math.min(
    ...vertices.slice(1).map((v) => vertices[0].distanceTo(v)),
  );
  const adjacent = (a: Vector3, b: Vector3) =>
    Math.abs(a.distanceTo(b) - edge) < 1e-6;
  const axes: Vector3[] = [];
  for (let i = 0; i < vertices.length; i++)
    for (let j = i + 1; j < vertices.length; j++) {
      for (let k = j + 1; k < vertices.length; k++) {
        const tri = [vertices[i], vertices[j], vertices[k]];
        if (!tri.every((v, n) => adjacent(v, tri[(n + 1) % 3]))) continue;
        const c = unitSum(tri);
        for (let n = 0; n < 3; n++) {
          const a = tri[n],
            b = tri[(n + 1) % 3];
          if (count === 24) {
            // Isosceles faces of an augmented octahedron.
            const tip = c
              .clone()
              .multiplyScalar((Math.sqrt(3) * (Math.sqrt(13) - 1)) / 6);
            const axis = b.clone().sub(a).cross(tip.sub(a)).normalize();
            axes.push(axis.dot(c) > 0 ? axis : axis.negate());
          } else {
            const mid = unitSum([a, b]);
            for (const corner of [a, b]) {
              const points = [corner, mid, c];
              const weights = points.map((_, i) =>
                points[(i + 1) % 3]
                  .clone()
                  .cross(points[(i + 2) % 3])
                  .length(),
              );
              axes.push(
                unitSum(
                  points.map((v, i) => v.clone().multiplyScalar(weights[i])),
                ),
              );
            }
          }
        }
      }
    }
  return axes;
}
function planeAxes(kind: Kind): Vector3[] {
  switch (kind) {
    case 'D3':
      return ring(3, 0, Math.PI / 3); // Numbered bands opposite the three cuts.
    case 'D4':
      return [Y.clone().negate(), ...ring(3, Math.asin(1 / 3), Math.PI / 2)];
    case 'Classic die':
    case 'D6':
      return signedAxes();
    case 'D8':
      return pairedRings(4, deg(35.54));
    case 'D10':
      return pairedRings(5, Math.asin(1 / Math.sqrt(3)), 0, Math.PI / 5);
    case 'D12':
      return icosahedron(true);
    case 'D16':
      return pairedRings(
        8,
        Math.atan(Math.cos(Math.PI / 8) / 1.15),
        Math.PI / 8,
      );
    case 'D20': {
      // The face centers of an icosahedron are the vertices of its dual.
      const latitude = Math.atan(0.5);
      const upper = ring(5, latitude);
      const lower = ring(5, -latitude, Math.PI / 5);
      const northCenter = unitSum([Y, upper[0], upper[1]]);
      const beltCenter = unitSum([upper[0], upper[1], lower[0]]);
      const angles = [Math.asin(northCenter.y), Math.asin(beltCenter.y)];
      return [...angles, -angles[1], -angles[0]].flatMap((lat, i) =>
        ring(5, lat, i < 2 ? Math.PI / 5 : 0),
      );
    }
    case 'D24':
    case 'D48':
    case 'D120':
      return symmetryPlanes(Number(kind.slice(1)));
    case 'D100': {
      // A tangent-plane approximation of a sphere, with staggered antipodal rings.
      // Distribute each hemisphere's 49 nonpolar faces in proportion to
      // ring circumference, then mirror the staggered northern rings.
      const beltCount = 4;
      const step = Math.PI / (2 * beltCount + 1);
      const weights = Array.from({ length: beltCount }, (_, i) =>
        Math.sin((i + 1) * step),
      );
      const total = weights.reduce((a, b) => a + b, 0);
      const counts = [
        1,
        ...weights.map((w) => Math.round(((100 / 2 - 1) * w) / total)),
      ];
      return [...counts, ...counts.slice().reverse()].flatMap((count, i) => {
        const northIndex = Math.min(i, 2 * counts.length - 1 - i);
        const halfStep =
          ((northIndex % 2) + (i >= counts.length ? count % 2 : 0)) % 2;
        return ring(
          count,
          Math.PI / 2 - i * step,
          count === 1 ? 0 : (halfStep * Math.PI) / count,
        );
      });
    }
  }
}
// Clip a convex polygon to the inside of a plane.
function clip(poly: Vector3[], axis: Vector3, distance: number) {
  const result: Vector3[] = [];
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i],
      b = poly[(i + 1) % poly.length],
      da = a.dot(axis) - distance,
      db = b.dot(axis) - distance;
    if (da <= 1e-9) result.push(a);
    if ((da < -1e-9 && db > 1e-9) || (da > 1e-9 && db < -1e-9))
      result.push(a.clone().lerp(b, da / (da - db)));
  }
  return result;
}
function unmarkedFaces(kind: Kind): Face[] {
  return planeAxes(kind).map((axis) => {
    const right = (Math.abs(axis.y) < 0.9 ? Y.clone() : vec(1, 0, 0))
      .cross(axis)
      .normalize();
    return {
      axis,
      right,
      down: right.clone().cross(axis),
      name: '',
      pose: new Quaternion(),
      rim: [],
    };
  });
}
const sample = (point: Vector3, normal: Vector3): Sample => ({ point, normal });
function polyhedron(kind: Kind) {
  const faces = unmarkedFaces(kind);
  const neighbors: number[][] = faces.map(() => []);
  const faceIndex = new Map(faces.map((face, i) => [face.axis, i]));
  const h = radius[kind],
    bevel = kind === 'Classic die' ? 1.65 : 0.65;
  const inset = 1 - bevel / h,
    patches: Patch[] = [];
  const corners = new Map<string, { p: Vector3; normals: Vector3[] }>();
  const edges = new Map<
    string,
    { a: Vector3; b: Vector3; normals: Vector3[] }
  >();
  const rounded = (v: Vector3, n: Vector3) =>
    sample(v.clone().multiplyScalar(inset).addScaledVector(n, bevel), n);
  for (const [face, f] of faces.entries()) {
    const center = f.axis.clone().multiplyScalar(h);
    let poly = [
      [-1, -1],
      [-1, 1],
      [1, 1],
      [1, -1],
    ].map(([x, y]) =>
      center
        .clone()
        .addScaledVector(f.right, x * h * 8)
        .addScaledVector(f.down, y * h * 8),
    );
    for (const g of faces) if (g !== f) poly = clip(poly, g.axis, h);
    poly = poly.filter((v, i) => key(v) !== key(poly[(i + 1) % poly.length]));
    if (poly.length < 3) throw Error('Empty procedural plane: ' + kind);
    const rim = poly.map((v) => rounded(v, f.axis));
    f.rim = rim.map((s) => s.point);
    for (let i = 0; i < rim.length; i++) {
      const j = (i + 1) % rim.length,
        a = poly[i],
        b = poly[j];
      patches.push({ face, samples: [sample(center, f.axis), rim[i], rim[j]] });
      const k = key(a),
        ek = [k, key(b)].sort().join(':');
      if (!corners.has(k)) corners.set(k, { p: a, normals: [] });
      corners.get(k)!.normals.push(f.axis);
      if (!edges.has(ek)) edges.set(ek, { a, b, normals: [] });
      edges.get(ek)!.normals.push(f.axis);
    }
  }
  // Slight crown with continuous analytical normals, without dense tessellation.
  const bend = 0.035,
    bendSample = (s: Sample) => {
      const r = s.point.length(),
        direction = s.point.clone().divideScalar(r);
      const b = (bend * h) / r;
      const normal = s.normal
        .clone()
        .addScaledVector(direction, (b * s.normal.dot(direction)) / (1 - bend))
        .normalize();
      return sample(s.point.clone().multiplyScalar(1 - bend + b), normal);
    };

  for (const edge of edges.values()) {
    if (edge.normals.length !== 2) throw Error('Open procedural edge: ' + kind);
    const [n, m] = edge.normals,
      mid = unitSum([n, m]);
    const first = faceIndex.get(n)!,
      second = faceIndex.get(m)!;
    neighbors[first].push(second);
    neighbors[second].push(first);
    for (const [u, v] of [
      [n, mid],
      [mid, m],
    ])
      patches.push({
        samples: [
          rounded(edge.a, u),
          rounded(edge.b, u),
          rounded(edge.b, v),
          rounded(edge.a, v),
        ],
      });
  }
  for (const c of corners.values()) {
    const axis = unitSum(c.normals),
      t = c.normals[0].clone().projectOnPlane(axis).normalize(),
      b = axis.clone().cross(t);
    const angle = (n: Vector3) => Math.atan2(n.dot(b), n.dot(t));
    c.normals.sort((a, b) => angle(a) - angle(b));
    for (let i = 0; i < c.normals.length; i++) {
      const n = c.normals[i],
        m = c.normals[(i + 1) % c.normals.length],
        mid = unitSum([n, m]);
      for (const [u, v] of [
        [n, mid],
        [mid, m],
      ])
        patches.push({
          samples: [rounded(c.p, axis), rounded(c.p, u), rounded(c.p, v)],
        });
    }
  }
  for (const patch of patches) patch.samples = patch.samples.map(bendSample);
  return { faces, patches, neighbors };
}
function slicedSphere() {
  const faces = unmarkedFaces('D3');
  const neighbors = faces.map((_, i) => [
    (i + 1) % faces.length,
    (i + faces.length - 1) % faces.length,
  ]);
  const r = radius.D3,
    cut = 0.745 * r,
    cuts = faces.map((f) => f.axis.clone().negate());
  const patches: Patch[] = [],
    borders = cuts.map(() => new Map<string, Vector3>());
  const sphere = (i: number, j: number) => {
    const a = (tau * (i % 36)) / 36,
      b = (Math.PI * j) / 16 - Math.PI / 2;
    return vec(
      Math.cos(a) * Math.cos(b),
      Math.sin(b),
      Math.sin(a) * Math.cos(b),
    ).multiplyScalar(r);
  };
  function curved(points: Vector3[]) {
    for (const n of cuts) points = clip(points, n, cut);
    if (points.length < 3) return;
    const samples = points.map((p) => {
      const normal = p.clone().normalize();
      cuts.forEach((n, i) => {
        const distance = cut - p.dot(n);
        if (Math.abs(distance) < 1e-6) borders[i].set(key(p), p);
        normal
          .lerp(n, 0.5 * Math.max(0, 1 - distance / (r * 0.06)))
          .normalize();
      });
      return sample(p, normal);
    });
    const center = unitSum(points),
      scores = faces.map((f) => f.axis.dot(center)),
      i = scores.indexOf(Math.max(...scores));
    const face = scores[i] > 0.48 ? i : undefined;
    if (face !== undefined) faces[face].rim.push(...points);
    patches.push({ samples, face });
  }
  for (let i = 0; i < 36; i++)
    for (let j = 0; j < 16; j++) {
      const a = sphere(i, j),
        b = sphere(i + 1, j),
        c = sphere(i + 1, j + 1),
        d = sphere(i, j + 1);
      if (j > 0) curved([a, b, c]);
      if (j < 15) curved([a, c, d]);
    }
  cuts.forEach((n, i) => {
    const center = n.clone().multiplyScalar(cut),
      t = Y.clone().cross(n);
    const border = [...borders[i].values()].sort(
      (a, b) => Math.atan2(a.y, a.dot(t)) - Math.atan2(b.y, b.dot(t)),
    );
    for (let j = 0; j < border.length; j++) {
      const p = border[j],
        q = border[(j + 1) % border.length];
      const a = sample(center.clone().lerp(p, 0.95), n),
        b = sample(center.clone().lerp(q, 0.95), n);
      patches.push(
        { samples: [sample(center, n), a, b] },
        {
          samples: [
            a,
            b,
            sample(q, unitSum([q.clone().normalize(), n])),
            sample(p, unitSum([p.clone().normalize(), n])),
          ],
        },
      );
    }
  });
  return { faces, patches, neighbors };
}
export function generateShape(kind: Kind): Shape {
  const { faces, patches, neighbors } =
    kind === 'D3' ? slicedSphere() : polyhedron(kind);
  return orientFaceWalk(faces, patches, neighbors, {
    firstValue: kind === 'D10' ? 0 : 1,
    vertexUp: kind === 'D4',
  });
}
