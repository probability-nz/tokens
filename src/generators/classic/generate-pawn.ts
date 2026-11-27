import { Vector2 } from 'three';
// Profile coordinates are (radius, height) in tabletop millimetres.
export function generatePawn() {
  const sides = 20;
  const foot = new Vector2(11.5, 5.75);
  const shoulder = new Vector2(4.46, 28.41);
  const cone = shoulder.clone().sub(foot);
  const coneNormal = new Vector2(cone.y, -cone.x).normalize();
  const rings: { point: Vector2; normal: Vector2 }[] = [];
  function ring(
    radius: number,
    height: number,
    outward: number,
    upward: number,
  ) {
    rings.push({
      point: new Vector2(radius, height),
      normal: new Vector2(outward, upward).normalize(),
    });
  }

  // Quarter ellipse from the flat underside to the vertical base wall.
  const baseRadius = 11.75,
    bevelWidth = 0.65,
    bevelHeight = 1.17;
  for (let i = 0; i <= 2; i++) {
    const angle = ((i / 2 - 1) * Math.PI) / 2;
    const c = Math.cos(angle),
      s = Math.sin(angle);
    ring(
      baseRadius - bevelWidth + bevelWidth * c,
      bevelHeight * (1 + s),
      c / bevelWidth,
      s / bevelHeight,
    );
  }
  ring(baseRadius, 4.62, 1, 0);
  for (const t of [0, 0.5, 1]) {
    const point = foot.clone().lerp(shoulder, t);
    ring(point.x, point.y, coneNormal.x, coneNormal.y);
  }

  const radius = 7.34,
    height = 7.7,
    center = 35.86;
  const lower = Math.asin((29.91 - center) / height);
  const upper = Math.acos(2.04 / radius);
  // Join the cone and ellipse with a tangent-matched quadratic Bézier.
  const headStart = new Vector2(
    radius * Math.cos(lower),
    center + height * Math.sin(lower),
  );
  const headTangent = new Vector2(
    -radius * Math.sin(lower),
    height * Math.cos(lower),
  );
  const offset = headStart.clone().sub(shoulder);
  const control = shoulder
    .clone()
    .addScaledVector(cone, offset.cross(headTangent) / cone.cross(headTangent));
  const neck = shoulder
    .clone()
    .lerp(control, 0.5)
    .lerp(control.clone().lerp(headStart, 0.5), 0.5);
  ring(neck.x, neck.y, offset.y, -offset.x);
  for (let i = 0; i <= 7; i++) {
    const angle = lower + ((upper - lower) * i) / 7;
    const c = Math.cos(angle),
      s = Math.sin(angle);
    ring(radius * c, center + height * s, c / radius, s / height);
  }

  const positions: number[] = [],
    normals: number[] = [],
    indices: number[] = [];
  for (const [row, { point, normal }] of rings.entries()) {
    for (let i = 0; i < sides; i++) {
      const angle = (i * 2 * Math.PI) / sides;
      const x = Math.sin(angle),
        z = Math.cos(angle);
      positions.push(point.x * x, point.y, point.x * z);
      normals.push(normal.x * x, normal.y, normal.x * z);
      if (row > 0) {
        const a = (row - 1) * sides + i;
        const b = (row - 1) * sides + ((i + 1) % sides);
        indices.push(a, b, a + sides, b + sides, a + sides, b);
      }
    }
  }
  // A separate rim gives each flat cap its own vertical normals.
  for (const row of [0, rings.length - 1]) {
    const sign = row === 0 ? -1 : 1;
    const centerIndex = positions.length / 3;
    positions.push(0, rings[row].point.y, 0);
    normals.push(0, sign, 0);
    for (let i = 0; i < sides; i++) {
      const p = (row * sides + i) * 3;
      positions.push(positions[p], positions[p + 1], positions[p + 2]);
      normals.push(0, sign, 0);
      const a = centerIndex + 1 + i,
        b = centerIndex + 1 + ((i + 1) % sides);
      indices.push(centerIndex, sign > 0 ? a : b, sign > 0 ? b : a);
    }
  }
  return { positions, normals, indices };
}
