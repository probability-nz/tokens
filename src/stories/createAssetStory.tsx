import type { Meta, StoryObj } from '@storybook/react';
import React from 'react';
import { Canvas } from '@react-three/fiber';
import { Stage, Gltf, OrbitControls } from '@react-three/drei';
import { Suspense } from 'react';
import prettyStringify from 'json-stringify-pretty-compact';
import { dissoc } from 'ramda';

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

function Scene({ asset, rotation }: { asset: any; rotation: [number, number, number] }) {
  return (
    <div style={{ width: '400px', height: '400px', border: '1px solid grey', borderRadius: '8px' }}>
      <Suspense fallback={<span>Loading...</span>}>
        <Canvas camera={{ position: [2, 2, 2], fov: 40 }}>
            <Stage adjustCamera={false}>
              <group rotation={rotation}>
                <Gltf src={asset.src} />
              </group>
            </Stage>
          <OrbitControls enablePan={false} minDistance={1} maxDistance={10} />
        </Canvas>
      </Suspense>
    </div>
  );
}

export function createAssetStory(asset: any, assetName: string): StoryObj {
  const faceOptions = ['None', ...((asset.faces ?? []).map((f: any) => f.name))];
  return {
    argTypes: {
      face: { control: 'select', options: faceOptions }
    },
    args: { face: 'None' },
    render: (args: any) => {
      const face = asset.faces?.find((f: any) => f.name === args.face);
      const rotation = (face
        ? face.rotation.map((d: number) => (d * Math.PI) / 180)
        : [0, 0, 0]) as [number, number, number];
      return (
        <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
          <Scene asset={asset} rotation={rotation} />
          <div>
            <h2>{asset.name}</h2>
            <p>
              To use this asset, add{' '}
              <code>{`{ "template": "@garbo-succus/tokens/${assetName}" }`}</code> to your game.
            </p>
            <h4>Defaults:</h4>
            <pre style={{ 
              padding: '10px', 
              borderRadius: '4px', 
              border: '1px solid grey'
            }}>
              {prettyStringify(dissoc('src', asset))}
            </pre>
          </div>
        </div>
      );
    }
  };
}