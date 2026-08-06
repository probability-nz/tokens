import { Center, Gltf, OrbitControls } from '@react-three/drei';
import { Canvas, useThree } from '@react-three/fiber';
import { Suspense, use, useLayoutEffect } from 'react';
import type { CatalogPiece } from '../catalog';
import { preferredGltfSource } from './preferred-gltf';

export type PreviewQuality = 'High' | 'Preview';

function PreviewModel({
  piece,
  quality,
}: {
  piece: CatalogPiece;
  quality: PreviewQuality;
}) {
  const source =
    quality === 'High' ? use(preferredGltfSource(piece.src)) : piece.src;
  return <Gltf src={source} castShadow />;
}

function CameraController({ view }: { view: 'Perspective' | 'Top' }) {
  const { camera, invalidate } = useThree();

  useLayoutEffect(() => {
    if (view === 'Top') {
      camera.position.set(0, 4, 0);
      camera.up.set(0, 0, -1);
    } else {
      camera.position.set(3, 2.5, 3);
      camera.up.set(0, 1, 0);
    }

    camera.lookAt(0, 0.7, 0);
    camera.updateProjectionMatrix();
    invalidate();
  }, [camera, invalidate, view]);

  return null;
}

export function PiecePreview({
  face,
  piece,
  quality,
  view,
}: {
  face: string;
  piece: CatalogPiece;
  quality: PreviewQuality;
  view: 'Perspective' | 'Top';
}) {
  const topView = view === 'Top';
  const [rotationX, rotationY, rotationZ] =
    piece.faces.find((candidate) => candidate.name === face)?.rotation ??
    piece.rotation;
  const data = Object.fromEntries(
    Object.entries(piece).filter(([key]) => key !== 'src'),
  );

  return (
    <div style={{ alignItems: 'flex-start', display: 'flex', gap: '20px' }}>
      <Suspense fallback={<span>Loading...</span>}>
        <Canvas
          camera={{ position: [3, 2.5, 3], fov: 35 }}
          shadows="percentage"
          style={{ height: '420px', width: '500px' }}
        >
          <CameraController view={view} />
          <ambientLight intensity={1.5} />
          <directionalLight position={[3, 5, 2]} intensity={3} castShadow />
          <Center top cacheKey={piece.src}>
            <group rotation={[rotationX, rotationY, rotationZ]}>
              <PreviewModel piece={piece} quality={quality} />
            </group>
          </Center>
          <gridHelper
            args={[6, 12, '#777777', '#cccccc']}
            position={[0, -0.002, 0]}
          />
          <mesh
            position={[0, -0.004, 0]}
            receiveShadow
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <planeGeometry args={[6, 6]} />
            <shadowMaterial transparent opacity={0.2} />
          </mesh>
          <OrbitControls
            enablePan={false}
            enableRotate={!topView}
            minDistance={2}
            maxDistance={10}
            target={[0, 0.7, 0]}
          />
        </Canvas>
      </Suspense>
      <div>
        <h2>{piece.name}</h2>
        <pre style={{ border: '1px solid grey', padding: '10px' }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    </div>
  );
}
