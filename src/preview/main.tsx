import { MapControls } from '@react-three/drei';
import { Canvas, useLoader, useThree } from '@react-three/fiber';
import { Suspense, useLayoutEffect, useMemo } from 'react';
import { createRoot } from 'react-dom/client';
import { Box3, Group, OrthographicCamera, Vector3 } from 'three';
import collection from '../../showcase/catalog.json';
import { preferredModelLoader } from './shared-textures';
import './studio.css';

type Piece = (typeof collection.pieces)[number];
function Model({ piece }: { piece: Piece }) {
  const { scene } = useLoader(preferredModelLoader, '/showcase/' + piece.src);
  const display = useMemo(() => {
    const model = new Group();
    model.add(scene.clone());
    model.rotation.set(piece.rotation[0], piece.rotation[1], piece.rotation[2]);
    model.scale.fromArray(piece.scale);
    const angled = new Group();
    angled.rotation.set(0.95, -0.22, 0);
    angled.add(model);
    const bounds = new Box3().setFromObject(angled, true);
    const size = bounds.getSize(new Vector3());
    const scale = 0.85 / Math.max(size.x, size.y);
    angled.scale.setScalar(scale);
    angled.position.copy(bounds.getCenter(new Vector3())).multiplyScalar(-scale);
    return angled;
  }, [scene, piece]);
  return <primitive object={display} />;
}

function Collection() {
  const { size, camera, invalidate } = useThree();
  const pieces = collection.pieces;
  const columns = Math.max(1, Math.min(pieces.length, Math.round(Math.sqrt(pieces.length * size.width / size.height))));
  const rows = Math.ceil(pieces.length / columns);
  const fit = Math.min(size.width / (columns + 0.5), size.height / (rows + 0.5));
  useLayoutEffect(() => {
    if (camera instanceof OrthographicCamera) {
      camera.zoom = fit;
      camera.updateProjectionMatrix();
      invalidate();
    }
  }, [camera, fit, invalidate]);
  return <>
    <MapControls screenSpacePanning enableRotate={false} zoomToCursor minZoom={fit / 2} maxZoom={fit * 24} />
    {pieces.map((piece, i) =>
      <group key={piece.src} position={[i % columns - (columns - 1) / 2, (rows - 1) / 2 - Math.floor(i / columns), 0]}>
        <Suspense fallback={null}><Model piece={piece} /></Suspense>
      </group>)}
  </>;
}

function Studio() {
  return <main aria-label="All game pieces. Drag to pan and scroll or pinch to zoom.">
    <Canvas orthographic camera={{ position: [0, 0, 20], near: 0.01, far: 100 }} frameloop="demand">
      <color attach="background" args={['#dfe3dd']} />
      <ambientLight intensity={1.65} />
      <directionalLight position={[3, 5, 6]} intensity={2.5} />
      <Collection />
    </Canvas>
  </main>;
}

createRoot(document.getElementById('root')!).render(<Studio />);
