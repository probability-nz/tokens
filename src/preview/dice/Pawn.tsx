import type { Ref } from 'react';
import { tabletopMotion } from '../../generators/dice/tabletop-motion';
import {
  BufferGeometry,
  Float32BufferAttribute,
  Mesh,
  Quaternion,
  Vector3,
} from 'three';

import { generatePawn } from '../../generators/classic/generate-pawn';

export function createPawnResources() {
  const { positions, normals, indices } = generatePawn();
  const geometry = new BufferGeometry();
  geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new Float32BufferAttribute(normals, 3));
  geometry.setIndex(indices);
  geometry.computeBoundingBox();
  const pivot = geometry.boundingBox!.getCenter(new Vector3());
  const motion = tabletopMotion(
    geometry,
    [new Quaternion(), new Quaternion(1, 0, 0, 0)],
    pivot,
  );
  return { geometry, motion };
}

export function Pawn({
  ref,
  geometry,
}: {
  ref?: Ref<Mesh>;
  geometry: BufferGeometry;
}) {
  return (
    <mesh ref={ref} name="Pawn" geometry={geometry}>
      <meshStandardMaterial color={[0.8, 0.8, 0.8]} roughness={0.5} />
    </mesh>
  );
}
