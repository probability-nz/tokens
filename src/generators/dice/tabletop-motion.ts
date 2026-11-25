import { BufferGeometry, Quaternion, Vector3 } from 'three';

// A piece supplies its resting orientations. Its mesh determines where it
// touches the table throughout the rotation, including between those poses.
export function tabletopMotion(
  geometry: BufferGeometry,
  poses: readonly Quaternion[],
  pivot = new Vector3(),
) {
  const center = pivot.clone();
  const rotations = poses.map((pose) => pose.clone());
  const positions = geometry.getAttribute('position');
  const unique = new Map<string, Vector3>();
  for (let i = 0; i < positions.count; i++) {
    const p = new Vector3().fromBufferAttribute(positions, i);
    unique.set(p.toArray().join(','), p);
  }
  const supports = [...unique.values()];
  const radius = Math.sqrt(
    supports.reduce((max, p) => Math.max(max, p.distanceToSquared(center)), 0),
  );
  const transitions = rotations.map((to, i) => {
    const from = rotations[(i + rotations.length - 1) % rotations.length];
    // At exactly half a turn there are two equally short arcs. Choose a
    // consistent axis direction, including when the pawn flips back upright.
    const delta = from.clone().invert().multiply(to).normalize();
    const vector = new Vector3(delta.x, delta.y, delta.z);
    const length = vector.length();
    const axis = length ? vector.divideScalar(length) : new Vector3(1, 0, 0);
    let angle = 2 * Math.atan2(length, delta.w);
    if (Math.abs(delta.w) < 1e-8) {
      const dominant = [axis.x, axis.y, axis.z].reduce((a, b) =>
        Math.abs(a) >= Math.abs(b) ? a : b,
      );
      if (dominant < 0) axis.negate();
      angle = Math.PI;
    } else if (angle > Math.PI) angle -= Math.PI * 2;
    return { from, axis, angle };
  });
  function sample(index: number, progress: number) {
    const rotation = new Quaternion();
    if (index === 0 || progress === 1)
      rotation.copy(rotations[index % rotations.length]);
    else {
      const { from, axis, angle } = transitions[index % rotations.length];
      rotation.setFromAxisAngle(axis, angle * progress).premultiply(from);
    }
    const localUp = new Vector3(0, 1, 0).applyQuaternion(
      rotation.clone().invert(),
    );
    let floor = Infinity;
    for (const p of supports) floor = Math.min(floor, localUp.dot(p));
    const position = center
      .clone()
      .applyQuaternion(rotation)
      .negate()
      .add(center);
    position.y = -floor;
    return { rotation, position };
  }
  return { sample, radius };
}
