import type { Meta, StoryObj } from '@storybook/react';
import React, { Suspense, useLayoutEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { Center, Gltf, OrbitControls } from '@react-three/drei';
import prettyStringify from 'json-stringify-pretty-compact';

export function createAssetMeta(asset: any, assetName: string, displayName: string): Meta {
  return {
    title: `Assets/${displayName}`,
    parameters: {
      docs: {
        description: {
          component: `
# ${asset.name}

## Properties
- **Scale**: ${asset.scale.join(' × ')}
- **Faces**: ${asset.faces?.length || 'N/A'} faces
- **Format**: GLTF with textures
          `
        }
      }
    }
  };
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

function Scene({
  asset,
  rotation,
  view
}: {
  asset: any;
  rotation: [number, number, number];
  view: 'Perspective' | 'Top';
}) {
  const topView = view === 'Top';

  return (
    <div style={{ width: '500px', height: '420px', border: '1px solid grey', borderRadius: '8px' }}>
      <Suspense fallback={<span>Loading...</span>}>
        <Canvas
          camera={{ position: [3, 2.5, 3], fov: 35 }}
          shadows="percentage"
        >
          <CameraController view={view} />
          <ambientLight intensity={1.5} />
          <directionalLight position={[3, 5, 2]} intensity={3} castShadow />
          <Center top cacheKey={rotation.join(',')}>
            <group rotation={rotation}>
              <Gltf src={asset.src} castShadow />
            </group>
          </Center>
          <gridHelper args={[6, 12, '#777777', '#cccccc']} position={[0, -0.002, 0]} />
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.004, 0]} receiveShadow>
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
    </div>
  );
}

export function createAssetStory(asset: any): StoryObj {
  const faceOptions = [...((asset.faces ?? []).map((f: any) => f.name)), 'None'];
  const defaultFace = asset.faces?.[0]?.name ?? 'None';
  return {
    argTypes: {
      face: {
        control: 'select',
        options: faceOptions
      },
      view: {
        control: 'inline-radio',
        options: ['Perspective', 'Top']
      }
    },
    args: { face: defaultFace, view: 'Perspective' },
    render: (args: any) => {
      const face = asset.faces?.find((f: any) => f.name === args.face);
      const rotation = (face?.rotation ?? asset.rotation ?? [0, 0, 0])
        .map((degrees: number) => (degrees * Math.PI) / 180) as [number, number, number];
      return (
        <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
          <Scene asset={asset} rotation={rotation} view={args.view} />
          <div>
            <h2>{asset.name}</h2>
            <h4>Defaults:</h4>
            <pre style={{ 
              padding: '10px', 
              borderRadius: '4px', 
              border: '1px solid grey'
            }}>
              {prettyStringify((({ src, ...rest }: any) => rest)(asset))}
            </pre>
          </div>
        </div>
      );
    }
  };
}
