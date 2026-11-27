import React, { useEffect, useLayoutEffect, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { CanvasTexture, Group, Mesh, MeshBasicMaterial } from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Pawn, createPawnResources } from './Pawn';
import type { Die } from '../../generators/dice/render-die';

const ROLL_DURATION_MS = 145;

export function createContactShadow() {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, 'rgba(36,45,48,.43)');
  gradient.addColorStop(0.36, 'rgba(36,45,48,.31)');
  gradient.addColorStop(0.66, 'rgba(36,45,48,.10)');
  gradient.addColorStop(1, 'rgba(36,45,48,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);
  const map = new CanvasTexture(canvas);
  return new MeshBasicMaterial({ map, transparent: true, depthWrite: false });
}

type SceneProps = {
  dice: readonly Die[];
  animate: boolean;
  pawn: ReturnType<typeof createPawnResources>;
  shadow: MeshBasicMaterial;
};

function Collection({ dice, animate, pawn, shadow }: SceneProps) {
  const { size, camera, gl, invalidate } = useThree();
  const groups = useRef<(Group | null)[]>([]);
  const pawnMesh = useRef<Mesh>(null);
  const tick = useRef({ index: 0, start: 0 });
  const pitch = 42,
    pairGap = 35,
    bandPitch = 81;
  const slots = dice.length + 1;
  const fit = (columns: number) =>
    Math.min(
      size.width / (columns * pitch + 14),
      size.height / (Math.ceil(slots / columns) * bandPitch + 22),
    );
  let columns = 1;
  for (let n = 2; n <= slots; n++) if (fit(n) > fit(columns)) columns = n;
  const pawnBounds = pawn.geometry.boundingBox!;
  const pawnFootprint =
    Math.max(
      pawnBounds.max.x - pawnBounds.min.x,
      pawnBounds.max.z - pawnBounds.min.z,
    ) * 1.36;
  const bands = Math.ceil(slots / columns);
  const zoom = fit(columns);
  const columnX = (i: number) => ((i % columns) - (columns - 1) / 2) * pitch;
  const bandZ = (i: number) =>
    (Math.floor(i / columns) - (bands - 1) / 2) * bandPitch;
  const controls = useRef<OrbitControls | null>(null);
  useEffect(() => {
    const orbit = new OrbitControls(camera, gl.domElement);
    orbit.target.set(0, 7, 0);
    orbit.minDistance = 120;
    orbit.maxDistance = 1500;
    orbit.minPolarAngle = 0.02;
    orbit.maxPolarAngle = Math.PI * 0.485;
    orbit.enableDamping = true;
    orbit.dampingFactor = 0.12;
    orbit.zoomSpeed = 0.8;
    orbit.minZoom = 0.4;
    orbit.maxZoom = 30;
    orbit.addEventListener('change', () => invalidate());
    controls.current = orbit;
    orbit.update();
    return () => {
      orbit.dispose();
      controls.current = null;
    };
  }, [camera, gl, invalidate]);
  useLayoutEffect(() => {
    // Orthographic camera units are millimetres. Refit only when the viewport changes.
    camera.zoom = zoom;
    camera.updateProjectionMatrix();
    invalidate();
  }, [zoom, camera, invalidate]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!document.hidden) {
        tick.current = {
          index: tick.current.index + 1,
          start: performance.now(),
        };
        invalidate();
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, [invalidate]);
  useLayoutEffect(() => {
    tick.current.start = -Infinity;
    invalidate();
  }, [animate, invalidate]);
  const rendered = useRef({ index: -1, ease: -1, dice });
  useFrame(() => {
    controls.current?.update();
    const { index, start } = tick.current;
    const elapsed = performance.now() - start;
    const t = animate ? Math.min(1, elapsed / ROLL_DURATION_MS) : 1;
    const ease = t * t * (3 - 2 * t);
    if (t < 1) invalidate();
    if (
      rendered.current.index === index &&
      rendered.current.ease === ease &&
      rendered.current.dice === dice
    )
      return;
    rendered.current = { index, ease, dice };
    dice.forEach((die, k) => {
      const pose = die.motion.sample(index, ease);
      for (let v = 0; v < 2; v++) {
        const group = groups.current[k * 2 + v];
        if (group) {
          group.quaternion.copy(pose.rotation);
          group.position.copy(pose.position);
        }
      }
    });
    if (pawnMesh.current) {
      const pose = pawn.motion.sample(index, ease);
      pawnMesh.current.quaternion.copy(pose.rotation);
      pawnMesh.current.position.copy(pose.position);
    }
  });
  return (
    <>
      <color attach="background" args={['#aebdc1']} />
      <hemisphereLight args={['#fffaf2', '#a1b0bf', 1.4]} />
      <directionalLight
        position={[-75, 130, 80]}
        intensity={2.2}
        color="#fff3dd"
      />
      <directionalLight
        position={[65, 60, -90]}
        intensity={1.1}
        color="#dfedff"
      />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.12, 0]}>
        <planeGeometry args={[6000, 6000]} />
        <meshStandardMaterial color="#aab9bd" roughness={0.93} />
      </mesh>
      {dice.map((die, i) => {
        const footprint = die.motion.radius * 2.35;
        return [die.marked, die.blank].map((material, v) => (
          <group
            key={die.kind + v}
            position={[columnX(i), 0, bandZ(i) + (v - 0.5) * pairGap]}
          >
            <mesh rotation={[-Math.PI / 2, 0, 0]} material={shadow}>
              <planeGeometry args={[footprint, footprint]} />
            </mesh>
            <group
              ref={(g) => {
                groups.current[i * 2 + v] = g;
              }}
            >
              <mesh
                name={die.kind + (v ? ' blank' : '')}
                geometry={die.geometry}
                material={material}
                dispose={null}
              />
            </group>
          </group>
        ));
      })}
      <group position={[columnX(dice.length), 0, bandZ(dice.length)]}>
        <mesh rotation={[-Math.PI / 2, 0, 0]} material={shadow}>
          <planeGeometry args={[pawnFootprint, pawnFootprint]} />
        </mesh>
        <Pawn ref={pawnMesh} geometry={pawn.geometry} />
      </group>
    </>
  );
}

export function DiceScene(props: SceneProps) {
  return (
    <Canvas
      orthographic
      frameloop="demand"
      dpr={[1, 1.75]}
      camera={{ position: [0, 265, 128], near: 0.1, far: 3000 }}
      gl={{ antialias: true, alpha: false }}
    >
      <Collection {...props} />
    </Canvas>
  );
}
