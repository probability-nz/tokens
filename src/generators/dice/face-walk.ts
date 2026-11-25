import { Matrix4, Quaternion, Vector3 } from 'three';
import { ringWalk } from './ring-walk';
import type { Face, Patch } from './shapes';

const up = new Vector3(0, 1, 0);

// Follow shared edges. Prefer counterclockwise steps near the highest unvisited
// latitude; triangular subdivisions sometimes require a short local reversal.
function spiralOrder(faces: Face[], neighbors: number[][]) {
  const axes = faces.map((f) => f.axis);
  // Axes through a face, an edge midpoint, or a corner expose different rings.
  // Intersect two edge-bisector planes to get a candidate corner direction.
  const first = axes[0];
  const adjacent = neighbors[0].map((i) => axes[i]);
  const poles = [up, first];
  for (const [i, a] of adjacent.entries()) {
    poles.push(first.clone().add(a).normalize());
    for (const b of adjacent.slice(i + 1)) {
      const corner = first
        .clone()
        .sub(a)
        .cross(first.clone().sub(b))
        .normalize();
      if (corner.dot(first) < 0) corner.negate();
      if (corner.lengthSq() > 0.9) poles.push(corner);
    }
  }
  let best: number[] | undefined,
    bestCost = Infinity,
    bestPole = up;
  let rings: { order: number[]; pole: Vector3; cost: number } | undefined;
  for (const pole of poles) {
    const latitude = axes.map((a) => pole.dot(a));
    const turn = (i: number, j: number) => {
      if (Math.abs(latitude[i]) > 0.999999 || Math.abs(latitude[j]) > 0.999999)
        return 0;
      return Math.atan2(
        pole.dot(axes[i].clone().cross(axes[j])),
        axes[i].dot(axes[j]) - latitude[i] * latitude[j],
      );
    };
    const steps = neighbors.map((row, i) =>
      row.map((j) => ({ j, angle: turn(i, j) })),
    );
    function pathCost(path: number[]) {
      let cost = 0;
      for (let n = 1; n < path.length; n++) {
        const a = path[n - 1],
          b = path[n];
        cost +=
          10 * Math.max(0, -turn(a, b)) +
          Math.max(0, latitude[b] - latitude[a]);
      }
      return cost;
    }
    function consider(path: number[]) {
      const cost = pathCost(path);
      if (cost < bestCost - 1e-8) {
        bestCost = cost;
        best = path.slice();
        bestPole = pole;
      }
    }
    const ranked = steps.map((row) =>
      row
        .map(({ j, angle }) => ({
          j,
          score:
            (angle < -1e-6 ? 10 : 0) -
            2 * latitude[j] -
            0.1 * Math.max(0, angle),
        }))
        .sort((a, b) => a.score - b.score || a.j - b.j)
        .map((step) => step.j),
    );
    const start = latitude.indexOf(Math.max(...latitude));
    const path = [start],
      used = new Uint8Array(faces.length);
    used[start] = 1;
    let budget = 2048;
    function visit(): boolean {
      if (path.length === faces.length) {
        consider(path);
        return true;
      }
      if (--budget < 0) return false;
      for (const j of ranked[path[path.length - 1]]) {
        if (used[j]) continue;
        used[j] = 1;
        path.push(j);
        // A remaining face with only one exit must terminate the path.
        let ends = 0;
        const viable = neighbors.every((row, i) => {
          if (used[i]) return true;
          let exits = 0;
          for (const n of row) if (!used[n] || n === j) exits++;
          return exits >= 2 || (exits === 1 && ++ends <= 1);
        });
        if (viable && visit()) return true;
        used[j] = 0;
        path.pop();
      }
      return false;
    }
    visit();
    if (bestCost < 1e-8) break;
    const lapOrder = ringWalk(latitude, neighbors, turn);
    if (lapOrder) {
      const cost = pathCost(lapOrder);
      if (cost < 1e-8) return { order: lapOrder, pole, circular: false };
      if (!rings || cost < rings.cost - 1e-8)
        rings = { order: lapOrder, pole, cost };
    }
  }
  if (bestCost > 1e-8 && rings)
    return { order: rings.order, pole: rings.pole, circular: true };
  if (!best)
    throw new Error(
      'No contiguous numbering walk for ' + faces.length + ' faces',
    );
  return { order: best, pole: bestPole, circular: false };
}

export function orientFaceWalk(
  faces: Face[],
  patches: Patch[],
  neighbors: number[][],
  { firstValue, vertexUp }: { firstValue: number; vertexUp: boolean },
) {
  const { order, pole, circular } = spiralOrder(faces, neighbors);
  const ordered = order.map((i) => ({
    ...faces[i],
    pose: new Quaternion(),
    right: new Vector3(),
    down: new Vector3(),
  }));
  const nextIndex = new Map(order.map((old, i) => [old, i]));
  const numberedPatches = patches.map((patch) =>
    patch.face === undefined
      ? patch
      : { ...patch, face: nextIndex.get(patch.face)! },
  );
  // A printed baseline follows the tangent to a helix about the same pole
  // as the numbering walk. Estimate its pitch over the whole walk so a single
  // step between latitude bands cannot flip the lettering on that face.
  const latitude = ordered.map((f) =>
    Math.asin(Math.max(-1, Math.min(1, f.axis.dot(pole)))),
  );
  const east = ordered.map((f) => pole.clone().cross(f.axis));
  let sweep = 0;
  for (let i = 1; i < east.length; i++) {
    if (east[i - 1].lengthSq() > 1e-10 && east[i].lengthSq() > 1e-10) {
      sweep += Math.atan2(
        pole.dot(east[i - 1].clone().cross(east[i])),
        east[i - 1].dot(east[i]),
      );
    }
  }
  const pitch =
    !circular && sweep > 1e-6
      ? (latitude[0] - latitude[latitude.length - 1]) / sweep
      : 0;
  const baselines = ordered.map((face, i) => {
    if (east[i].lengthSq() < 1e-10) return null;
    const south = east[i].clone().cross(face.axis).normalize();
    return east[i].clone().addScaledVector(south, pitch).normalize();
  });
  const basis = new Matrix4();
  const cube = ordered.length === 6 && ordered.every((f) => f.rim.length === 4);
  for (const [i, face] of ordered.entries()) {
    face.name = String(firstValue + i);
    let baseline = baselines[i];
    if (!baseline) {
      // Longitude is undefined at a pole. Carry the neighboring baseline over
      // the shared edge so reaching the cap does not introduce a yaw turn.
      const j = i > 0 && baselines[i - 1] ? i - 1 : i + 1;
      baseline = baselines[j]!.clone().applyQuaternion(
        new Quaternion().setFromUnitVectors(ordered[j].axis, face.axis),
      );
    }
    if (cube && i === 0) {
      // Anchor the first marking to a real cube edge. Transporting this frame
      // across right-angle rolls keeps every numeral and pip grid square.
      const edge = face.rim[1].clone().sub(face.rim[0]).normalize();
      const across = face.axis.clone().cross(edge);
      const aligned =
        Math.abs(edge.dot(baseline)) >= Math.abs(across.dot(baseline))
          ? edge
          : across;
      baseline = aligned.dot(baseline) < 0 ? aligned.negate() : aligned;
    }
    if (i > 0) {
      // Near a pole, two close faces can have very different longitudes.
      // Approach the helix heading by at most the angle of the edge roll.
      const prev = ordered[i - 1];
      const roll = new Quaternion().setFromUnitVectors(prev.axis, face.axis);
      const carried = prev.right.clone().applyQuaternion(roll);
      const yaw = Math.atan2(
        face.axis.dot(carried.clone().cross(baseline)),
        carried.dot(baseline),
      );
      const limit = cube ? 0 : prev.axis.angleTo(face.axis);
      baseline = carried
        .applyAxisAngle(face.axis, Math.max(-limit, Math.min(limit, yaw)))
        .normalize();
    }
    const normal = face.axis.clone();
    // The tetrahedron presents a vertex with its indexed face on the table.
    if (vertexUp) normal.negate();
    face.right.copy(baseline);
    face.down.crossVectors(baseline, face.axis).normalize();
    basis.makeBasis(baseline, normal, baseline.clone().cross(normal));
    face.pose.setFromRotationMatrix(basis).invert().normalize();
  }
  return { faces: ordered, patches: numberedPatches };
}
